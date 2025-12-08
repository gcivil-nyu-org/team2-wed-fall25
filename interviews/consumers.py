# consumers.py
"""
WebSocket consumers for live interview features.
This version moves blocking/third-party SDK calls off the event loop
(using run_in_executor) to avoid "You cannot call this from an async context"
errors and similar issues.
"""

import asyncio
import json
import logging
from functools import partial

import google.generativeai as genai

# Removed unused import: from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


class BehavioralResumeLiveConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for behavioral + resume live interview.
    Relays audio between browser and Gemini Live API.
    """

    async def connect(self):
        """Handle WebSocket connection"""
        # Get user from scope (added by AuthMiddlewareStack)
        self.user = self.scope.get("user")

        if not self.user or isinstance(self.user, AnonymousUser):
            logger.warning("Unauthorized WebSocket connection attempt")
            await self.close(code=4001)
            return

        # Accept the connection
        await self.accept()

        logger.info(f"WebSocket connected for user: {self.user.username}")

        # Initialize session variables
        self.session = None
        self.live_session = None
        self.question_count = 0
        self.max_questions = 2  # Reduced for testing
        self.final_summary = ""
        self.session_ended = False
        self.initialized = False

        # Load interview session and initialize Gemini Live
        try:
            await self.initialize_interview()
        except Exception as e:
            logger.exception("Failed to initialize interview")
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": f"Failed to initialize interview: {str(e)}",
                    }
                )
            )
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        logger.info(
            f"WebSocket disconnected for user: {self.user.username if hasattr(self, 'user') else 'Unknown'}"
        )

        # If any cleanup for live session is necessary, do it here.
        if hasattr(self, "live_session") and self.live_session:
            try:
                # Example if SDK had a close: await self.run_blocking(self.live_session.close)
                pass
            except Exception:
                logger.exception("Error during live_session cleanup")

    async def receive(self, text_data=None, bytes_data=None):
        """
        Receive data from WebSocket.
        Handles text commands and text answers only (no audio upload).
        """
        try:
            if text_data:
                # Handle text commands and answers
                data = json.loads(text_data)
                message_type = data.get("type")

                if message_type == "start":
                    await self.start_interview()
                elif message_type == "end":
                    await self.end_interview()
                elif message_type == "answer":
                    await self.handle_text_answer(data.get("text", ""))
                elif message_type == "ping":
                    await self.send(text_data=json.dumps({"type": "pong"}))
                else:
                    logger.warning(f"Unknown message type: {message_type}")

        except Exception:
            logger.exception("Error in receive")
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Internal server error"}
                )
            )

    @database_sync_to_async
    def get_interview_session(self):
        """Get active interview session for user"""
        from .models import InterviewSession

        try:
            return InterviewSession.objects.filter(
                user=self.user, status="active"
            ).first()
        except Exception:
            logger.exception("Error fetching interview session")
            return None

    @database_sync_to_async
    def get_resume_text(self):
        """Extract resume text from user's resume"""
        from .gemini_service import GeminiAnalyzer

        try:
            if hasattr(self.user, "resume") and self.user.resume:
                analyzer = GeminiAnalyzer()
                # Assuming extract_text_from_pdf is a synchronous, blocking operation
                return analyzer.extract_text_from_pdf(self.user.resume)
            return "No resume available."
        except Exception:
            logger.exception("Error extracting resume")
            return "Resume could not be extracted."

    @database_sync_to_async
    def get_behavioral_document(self, company_slug):
        """Get one random behavioral document for company"""
        from .rag_service import RAGService

        try:
            # RAG retrieval is likely blocking I/O (database, file, or network),
            # so it must be run in a sync context.
            rag = RAGService()
            return rag.retrieve_behavioral_question(company_slug)
        except Exception:
            logger.exception("Error retrieving behavioral document")
            return None

    @database_sync_to_async
    def save_final_summary(self, summary):
        """
        Save final summary to interview session safely.
        Important: re-fetch the session inside this sync function to avoid
        touching model instances created in a different thread/async context.
        """
        from .models import InterviewSession

        try:
            if not getattr(self, "session", None):
                logger.warning("save_final_summary called but self.session is None")
                return

            session = InterviewSession.objects.get(id=self.session.id)
            session.behavioral_resume_summary = summary
            session.behavioral_resume_completed = True
            session.save()
            logger.info(f"Saved final summary for session {session.id}")
        except InterviewSession.DoesNotExist:
            logger.exception("InterviewSession not found when saving summary")
        except Exception:
            logger.exception("Unexpected error saving final summary")

    # ---------------------
    # Helpers to run blocking code in a threadpool
    # ---------------------
    async def run_blocking(self, func, *args, **kwargs):
        """
        Runs a blocking function in the default ThreadPoolExecutor.
        Use this for any blocking I/O or sync SDK calls.
        """
        loop = asyncio.get_running_loop()
        bound = partial(func, *args, **kwargs)
        return await loop.run_in_executor(None, bound)

    # ---------------------
    # Gemini (blocking) wrappers
    # ---------------------
    def _configure_genai(self):
        """Sync wrapper to configure the genai SDK (blocking)."""
        genai.configure(api_key=settings.GEMINI_API_KEY)

    def _generate_question_sync(self, context):
        """Blocking call to generate a question via the Gemini SDK."""
        self._configure_genai()
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(context)
        # many SDKs return .text or .result; adapt if needed
        return getattr(response, "text", str(response)).strip()

    def _generate_summary_sync(self, prompt):
        """Blocking call to generate summary via Gemini SDK."""
        self._configure_genai()
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return getattr(response, "text", str(response)).strip()

    # ---------------------
    # Initialization & Interview Flow
    # ---------------------
    async def initialize_interview(self):
        """Initialize interview session and Gemini Live (non-blocking from event loop)."""
        # Load interview session (DB access via database_sync_to_async)
        self.session = await self.get_interview_session()

        if not self.session:
            raise Exception("No active interview session found")

        # Get resume text and behavioral doc (also via DB/service wrappers)
        resume_text = await self.get_resume_text()
        behavioral_document_text = await self.get_behavioral_document(
            self.session.company
        )

        if not behavioral_document_text:
            logger.warning(f"No behavioral document found for {self.session.company}")
            behavioral_document_text = (
                "Tell me about a time when you faced a challenging problem at work.\n"
                "Describe a situation where you had to work with a difficult team member.\n"
                "Give an example of when you showed leadership."
            )

        # Build system prompt via your service
        from .gemini_live_service import GeminiLiveService

        # FIX: __init__ is now safe (non-blocking) and can be called directly.
        live_service = GeminiLiveService()

        # FIX: build_system_prompt is pure logic and is called directly
        # (no need for run_blocking wrapper).
        system_prompt = live_service.build_system_prompt(
            company_name=self.session.get_company_display(),
            resume_text=resume_text,
            behavioral_document_text=behavioral_document_text,
            user_type=self.user.user_type,
        )

        # Store initialization data
        self.system_prompt = system_prompt
        self.initialized = True

        # Send ready signal to client
        await self.send(
            text_data=json.dumps(
                {
                    "type": "ready",
                    "message": "Interview initialized. Ready to start.",
                    "company": self.session.get_company_display(),
                }
            )
        )

        logger.info(
            f"Interview initialized for user {self.user.username}, company {self.session.company}"
        )

    async def start_interview(self):
        """Start the Gemini Live interview session"""
        try:
            # Configure Gemini SDK (blocking) in a thread (this is where the call belongs)
            await self.run_blocking(self._configure_genai)

            # Initialize conversation history
            self.conversation_history = []
            self.is_interview_active = True

            # Send started signal
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "started",
                        "message": "Interview started. Asking first question...",
                        "question_count": 0,
                        "max_questions": self.max_questions,
                    }
                )
            )

            # Ask the first question immediately
            await self.ask_next_question()

            logger.info(f"Interview started for user {self.user.username}")

        except Exception:
            logger.exception("Error starting interview")
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Failed to start interview"}
                )
            )

    async def ask_next_question(self):
        """Generate and send the next interview question using Gemini"""
        try:
            if self.question_count >= self.max_questions:
                await self.request_final_summary()
                return

            # Build context for Gemini
            context = f"{self.system_prompt}\n\n"
            if self.conversation_history:
                context += "Previous conversation:\n"
                for entry in self.conversation_history:
                    context += f"Q: {entry['question']}\nA: {entry['answer']}\n\n"

            context += f"\nGenerate interview question #{self.question_count + 1}. Keep it concise and relevant to the candidate's resume and company culture. Only output the question text, nothing else."

            # Call Gemini on the threadpool
            question_text = await self.run_blocking(
                self._generate_question_sync, context
            )

            # Store current question
            self.current_question = question_text
            self.question_count += 1

            # Send question as text to client (client will use speech synthesis)
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "question",
                        "question": question_text,
                        "question_number": self.question_count,
                        "max_questions": self.max_questions,
                    }
                )
            )

            logger.info(f"Asked question {self.question_count}: {question_text}")

        except Exception:
            logger.exception("Error generating question")
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Failed to generate question"}
                )
            )

    async def handle_text_answer(self, answer_text):
        """
        Handle incoming text answer from client.
        Answer can be typed or transcribed from speech on client side.
        """
        try:
            if not self.is_interview_active or not hasattr(self, "current_question"):
                logger.warning(
                    "Received answer but interview not active or no question pending"
                )
                await self.send(
                    text_data=json.dumps(
                        {"type": "error", "message": "No active question to answer"}
                    )
                )
                return

            # Validate answer
            answer_text = (answer_text or "").strip()
            if not answer_text:
                await self.send(
                    text_data=json.dumps(
                        {"type": "error", "message": "Answer cannot be empty"}
                    )
                )
                return

            # Store Q&A in history
            self.conversation_history.append(
                {"question": self.current_question, "answer": answer_text}
            )

            logger.info(f"Answer received (text): {answer_text[:100]}...")

            # Send acknowledgment
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "answer_received",
                        "answer": answer_text,
                        "question_count": self.question_count,
                        "max_questions": self.max_questions,
                    }
                )
            )

            # Ask next question or end interview
            if self.question_count >= self.max_questions:
                await asyncio.sleep(0.5)
                await self.request_final_summary()
            else:
                # Small delay before next question
                await asyncio.sleep(1)
                await self.ask_next_question()

        except Exception:
            logger.exception("Error handling text answer")
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Error processing answer"}
                )
            )

    async def request_final_summary(self):
        """Request final summary from Gemini"""
        try:
            self.session_ended = True
            self.is_interview_active = False

            # Build full conversation context
            conversation_text = ""
            for i, entry in enumerate(self.conversation_history, 1):
                conversation_text += f"\nQuestion {i}: {entry['question']}\n"
                conversation_text += f"Answer {i}: {entry['answer']}\n"

            # Generate comprehensive summary using Gemini (blocking) on threadpool
            summary_prompt = f"""Based on this behavioral interview for a position at {self.session.get_company_display()}, provide a comprehensive summary.

Interview Transcript:
{conversation_text}

Please provide a structured summary including:
1. Overall Assessment (2-3 sentences about the candidate's performance)
2. Key Strengths (3-4 bullet points highlighting what the candidate did well)
3. Areas for Improvement (2-3 bullet points on what could be better)
4. Notable Responses (mention 1-2 standout answers)
5. Recommendation (hire/no hire/further evaluation and why)

Format the summary professionally but concisely."""

            summary = await self.run_blocking(
                self._generate_summary_sync, summary_prompt
            )

            # Save summary to database
            await self.save_final_summary(summary)

            # Send summary to client
            await self.send(
                text_data=json.dumps(
                    {"type": "summary", "summary": summary, "completed": True}
                )
            )

            logger.info(
                f"Final summary generated and saved for user {self.user.username}"
            )

        except Exception:
            logger.exception("Error generating summary")
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Failed to generate summary"}
                )
            )

    async def end_interview(self):
        """End the interview session"""
        try:
            if not self.session_ended:
                await self.request_final_summary()

            await self.send(
                text_data=json.dumps(
                    {"type": "ended", "message": "Interview ended successfully."}
                )
            )

            # Close the WebSocket connection
            await self.close()

        except Exception:
            logger.exception("Error ending interview")
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Error ending interview"}
                )
            )
