import asyncio
import json
import logging

from asgiref.sync import sync_to_async
import google.generativeai as genai
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
        self.user = self.scope.get("user")

        if not self.user or isinstance(self.user, AnonymousUser):
            logger.warning("Unauthorized WebSocket connection attempt")
            await self.close(code=4001)
            return

        await self.accept()
        logger.info(f"WebSocket connected for user: {self.user.username}")

        self.session = None
        self.system_prompt = None
        self.initialized = False
        self.conversation_history = []
        self.is_interview_active = False
        self.current_question = None
        self.question_count = 0
        self.max_questions = 2
        self.session_ended = False

        try:
            await self.initialize_interview()
        except Exception as e:
            logger.error(f"Failed to initialize interview: {str(e)}")
            await self.send(
                text_data=json.dumps({"type": "error", "message": f"Failed to initialize interview: {str(e)}"})
            )
            await self.close()

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected for user: {getattr(self.user, 'username', 'Unknown')}")
        # Cleanup if needed
        if hasattr(self, "live_session") and self.live_session:
            try:
                pass  # Gemini SDK handles cleanup
            except Exception as e:
                logger.error(f"Error closing live session: {str(e)}")

    async def receive(self, text_data=None, bytes_data=None):
        try:
            if text_data:
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

        except Exception as e:
            logger.error(f"Error in receive: {str(e)}")
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    @database_sync_to_async
    def get_interview_session(self):
        from .models import InterviewSession
        return InterviewSession.objects.filter(user=self.user, status="active").first()

    @database_sync_to_async
    def get_behavioral_document(self, company_slug):
        from .rag_service import RAGService
        rag = RAGService()
        return rag.retrieve_behavioral_question(company_slug)

    @database_sync_to_async
    def save_final_summary(self, summary):
        if self.session:
            self.session.behavioral_resume_summary = summary
            self.session.behavioral_resume_completed = True
            self.session.save()
            logger.info(f"Saved final summary for session {self.session.id}")

    async def initialize_interview(self):
        self.session = await self.get_interview_session()
        if not self.session:
            raise Exception("No active interview session found")

        # Wrap model attribute access
        company_display = await sync_to_async(self.session.get_company_display)()
        resume_file = await sync_to_async(lambda: getattr(self.user, 'resume', None))()
        user_type = await sync_to_async(lambda: getattr(self.user, 'user_type', None))()

        # Extract resume text
        resume_text = "No resume available."
        if resume_file:
            from .gemini_service import GeminiAnalyzer
            analyzer = GeminiAnalyzer()
            resume_text = await sync_to_async(analyzer.extract_text_from_pdf)(resume_file)

        behavioral_document_text = await self.get_behavioral_document(self.session.company)
        if not behavioral_document_text:
            behavioral_document_text = (
                """Tell me about a time when you faced a challenging problem at work.
Describe a situation where you had to work with a difficult team member.
Give an example of when you showed leadership."""
            )

        # Import inside function to avoid circular import
        from .gemini_live_service import GeminiLiveService
        live_service = GeminiLiveService()
        system_prompt = live_service.build_system_prompt(
            company_name=company_display,
            resume_text=resume_text,
            behavioral_document_text=behavioral_document_text,
            user_type=user_type,
        )

        self.system_prompt = system_prompt
        self.initialized = True

        await self.send(
            text_data=json.dumps({
                "type": "ready",
                "message": "Interview initialized. Ready to start.",
                "company": company_display,
            })
        )
        logger.info(f"Interview initialized for user {self.user.username}, company {self.session.company}")

    async def start_interview(self):
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.conversation_history = []
            self.is_interview_active = True

            await self.send(
                text_data=json.dumps({
                    "type": "started",
                    "message": "Interview started. Asking first question...",
                    "question_count": 0,
                    "max_questions": self.max_questions,
                })
            )

            await self.ask_next_question()
            logger.info(f"Interview started for user {self.user.username}")

        except Exception as e:
            logger.error(f"Error starting interview: {str(e)}")
            await self.send(text_data=json.dumps({"type": "error", "message": f"Failed to start interview: {str(e)}"}))

    async def ask_next_question(self):
        try:
            if self.question_count >= self.max_questions:
                await self.request_final_summary()
                return

            context = f"{self.system_prompt}\n\n"
            if self.conversation_history:
                context += "Previous conversation:\n"
                for entry in self.conversation_history:
                    context += f"Q: {entry['question']}\nA: {entry['answer']}\n\n"

            context += (
                f"\nGenerate interview question #{self.question_count + 1}. Keep it concise and relevant to the candidate's resume and company culture. Only output the question text, nothing else."
            )

            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(context)
            question_text = response.text.strip()

            self.current_question = question_text
            self.question_count += 1

            await self.send(
                text_data=json.dumps({
                    "type": "question",
                    "question": question_text,
                    "question_number": self.question_count,
                    "max_questions": self.max_questions,
                })
            )
            logger.info(f"Asked question {self.question_count}: {question_text}")

        except Exception as e:
            logger.error(f"Error generating question: {str(e)}")
            await self.send(text_data=json.dumps({"type": "error", "message": f"Failed to generate question: {str(e)}"}))

    async def handle_text_answer(self, answer_text):
        try:
            if not self.is_interview_active or not self.current_question:
                await self.send(text_data=json.dumps({"type": "error", "message": "No active question to answer"}))
                return

            answer_text = answer_text.strip()
            if not answer_text:
                await self.send(text_data=json.dumps({"type": "error", "message": "Answer cannot be empty"}))
                return

            self.conversation_history.append({"question": self.current_question, "answer": answer_text})

            await self.send(
                text_data=json.dumps({
                    "type": "answer_received",
                    "answer": answer_text,
                    "question_count": self.question_count,
                    "max_questions": self.max_questions,
                })
            )

            if self.question_count >= self.max_questions:
                await asyncio.sleep(0.5)
                await self.request_final_summary()
            else:
                await asyncio.sleep(1)
                await self.ask_next_question()

        except Exception as e:
            logger.error(f"Error handling text answer: {str(e)}")
            await self.send(text_data=json.dumps({"type": "error", "message": f"Error processing answer: {str(e)}"}))

    async def request_final_summary(self):
        try:
            self.session_ended = True
            self.is_interview_active = False

            conversation_text = ""
            for i, entry in enumerate(self.conversation_history, 1):
                conversation_text += f"\nQuestion {i}: {entry['question']}\n"
                conversation_text += f"Answer {i}: {entry['answer']}\n"

            summary_prompt = (
                f"Based on this behavioral interview for a position at {await sync_to_async(self.session.get_company_display)()}, provide a comprehensive summary.\n\n"
                f"Interview Transcript:\n{conversation_text}\n\n"
                "Please provide a structured summary including:\n"
                "1. Overall Assessment (2-3 sentences about the candidate's performance)\n"
                "2. Key Strengths (3-4 bullet points highlighting what the candidate did well)\n"
                "3. Areas for Improvement (2-3 bullet points on what could be better)\n"
                "4. Notable Responses (mention 1-2 standout answers)\n"
                "5. Recommendation (hire/no hire/further evaluation and why)\n\n"
                "Format the summary professionally but concisely."
            )

            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(summary_prompt)
            summary = response.text.strip()

            await self.save_final_summary(summary)

            await self.send(text_data=json.dumps({"type": "summary", "summary": summary, "completed": True}))
            logger.info(f"Final summary generated and saved for user {self.user.username}")

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            await self.send(text_data=json.dumps({"type": "error", "message": f"Failed to generate summary: {str(e)}"}))

    async def end_interview(self):
        try:
            if not self.session_ended:
                await self.request_final_summary()

            await self.send(text_data=json.dumps({"type": "ended", "message": "Interview ended successfully."}))
            await self.close()

        except Exception as e:
            logger.error(f"Error ending interview: {str(e)}")
            await self.send(text_data=json.dumps({"type": "error", "message": f"Error ending interview: {str(e)}"}))
