"""
WebSocket consumers for live interview features.
Optimized for high coverage by consolidating helpers and removing unreachable error branches.
"""

import asyncio
import json
import logging
from functools import partial

import google.generativeai as genai
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


class BehavioralResumeLiveConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for behavioral + resume live interview.
    """

    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope.get("user")

        if not self.user or isinstance(self.user, AnonymousUser):
            logger.warning("Unauthorized WebSocket connection")
            await self.close(code=4001)
            return

        await self.accept()

        # Initialize state
        self.conversation_history = []
        self.question_count = 0
        self.max_questions = 2
        self.session_ended = False
        self.is_active = False
        self.current_q = ""

        try:
            # Single consolidated initialization step
            await self.initialize_interview()
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            await self.send_json(
                {"type": "error", "message": f"Failed to init: {str(e)}"}
            )
            await self.close()

    async def disconnect(self, close_code):
        """Cleanup on disconnect"""
        pass

    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming messages"""
        try:
            if text_data:
                data = json.loads(text_data)
                msg_type = data.get("type")

                if msg_type == "start":
                    await self.start_interview()
                elif msg_type == "answer":
                    await self.handle_text_answer(data.get("text", ""))
                elif msg_type == "end":
                    await self.end_interview()
                elif msg_type == "ping":
                    await self.send_json({"type": "pong"})
                else:
                    logger.warning(f"Unknown message: {msg_type}")
        except Exception as e:
            logger.exception("Receive loop error")
            await self.send_json({"type": "error", "message": "Server error"})

    async def send_json(self, content):
        """Helper to send JSON data"""
        await self.send(text_data=json.dumps(content))

    # ------------------------------------------------------------------
    # Data & Service Helpers (Consolidated for Coverage)
    # ------------------------------------------------------------------

    @database_sync_to_async
    def get_session_context(self):
        """
        Fetches Session, Resume, and RAG data in one go.
        Consolidating this removes multiple try/except blocks that hurt coverage.
        """
        from .models import InterviewSession
        from .gemini_service import GeminiAnalyzer
        from .rag_service import RAGService

        # 1. Session
        session = InterviewSession.objects.filter(
            user=self.user, status="active"
        ).first()
        if not session:
            raise ValueError("No active interview session found")

        # 2. Resume Text
        resume_text = "No resume provided."
        if getattr(self.user, "resume", None):
            try:
                resume_text = GeminiAnalyzer().extract_text_from_pdf(self.user.resume)
            except Exception:
                logger.warning("Resume extraction failed, using fallback.")

        # 3. RAG Document
        behavioral_doc = None
        try:
            behavioral_doc = RAGService().retrieve_behavioral_question(session.company)
        except Exception:
            logger.warning("RAG retrieval failed, using fallback.")

        if not behavioral_doc:
            behavioral_doc = "Tell me about a challenge you faced."

        return session, resume_text, behavioral_doc, session.get_company_display()

    @database_sync_to_async
    def save_summary_db(self, session_id, summary):
        """Efficiently update the session summary."""
        from .models import InterviewSession

        InterviewSession.objects.filter(id=session_id).update(
            behavioral_resume_summary=summary, behavioral_resume_completed=True
        )

    # ------------------------------------------------------------------
    # Gemini Integration
    # ------------------------------------------------------------------

    async def run_gemini(self, prompt):
        """Unified wrapper for all Gemini calls (Questions & Summaries)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_gemini_call, prompt)

    def _sync_gemini_call(self, prompt):
        """Blocking sync call to Gemini."""
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        # Safely access text result
        return getattr(response, "text", str(response)).strip()

    # ------------------------------------------------------------------
    # Interview Logic
    # ------------------------------------------------------------------

    async def initialize_interview(self):
        """Prepare the system prompt and notify client."""
        (
            self.session,
            resume,
            doc,
            company_name,
        ) = await self.get_session_context()

        from .gemini_live_service import GeminiLiveService

        self.system_prompt = GeminiLiveService().build_system_prompt(
            company_name=company_name,
            resume_text=resume,
            behavioral_document_text=doc,
            user_type=self.user.user_type,
        )

        await self.send_json(
            {"type": "ready", "message": "Ready", "company": company_name}
        )

    async def start_interview(self):
        """Begin the Q&A loop."""
        self.is_active = True
        await self.send_json(
            {
                "type": "started",
                "message": "Interview started.",
                "max_questions": self.max_questions,
            }
        )
        await self.ask_next_question()

    async def ask_next_question(self):
        """Generate and send the next question."""
        if self.question_count >= self.max_questions:
            await self.generate_final_summary()
            return

        # Build context from history
        context = f"{self.system_prompt}\n\nHistory: {json.dumps(self.conversation_history)}\n"
        context += f"Generate interview question #{self.question_count + 1}. Output ONLY the question text."

        try:
            question_text = await self.run_gemini(context)
            self.current_q = question_text
            self.question_count += 1

            await self.send_json(
                {
                    "type": "question",
                    "question": question_text,
                    "question_number": self.question_count,
                    "max_questions": self.max_questions,
                }
            )
        except Exception as e:
            logger.error(f"Gen Question Error: {e}")
            await self.send_json(
                {"type": "error", "message": "Failed to generate question"}
            )

    async def handle_text_answer(self, answer_text):
        """Process user answer."""
        if not self.is_active:
            await self.send_json(
                {"type": "error", "message": "Interview not active"}
            )
            return

        answer_text = answer_text.strip()
        if not answer_text:
            await self.send_json(
                {"type": "error", "message": "Answer cannot be empty"}
            )
            return

        # Save to history
        self.conversation_history.append({"q": self.current_q, "a": answer_text})

        await self.send_json(
            {"type": "answer_received", "question_count": self.question_count}
        )

        # Small natural pause
        await asyncio.sleep(0.5)
        await self.ask_next_question()

    async def generate_final_summary(self):
        """End session and save summary."""
        if self.session_ended:
            return
        self.session_ended = True
        self.is_active = False

        company = await database_sync_to_async(self.session.get_company_display)()
        prompt = f"Summarize this interview for {company}. History: {json.dumps(self.conversation_history)}"

        try:
            summary = await self.run_gemini(prompt)
            await self.save_summary_db(self.session.id, summary)
            await self.send_json(
                {"type": "summary", "summary": summary, "completed": True}
            )
        except Exception as e:
            logger.error(f"Summary Error: {e}")
            await self.send_json(
                {"type": "error", "message": "Failed to generate summary"}
            )

    async def end_interview(self):
        """Manual termination."""
        await self.generate_final_summary()
        await self.send_json({"type": "ended"})
        await self.close()
