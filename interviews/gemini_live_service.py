"""
Gemini Live API service for audio-to-audio interview.
Handles initialization and configuration for Live session.
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class GeminiLiveService:
    """
    Service for initializing and configuring Gemini Live sessions
    for behavioral + resume interviews.
    """

    def __init__(self):
        """
        Initialize Gemini Live API (now non-blocking).
        Logs an error if GEMINI_API_KEY is not set.
        """
        self.api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not self.api_key:
            logger.error("GEMINI_API_KEY not configured")

    def build_system_prompt(
        self, company_name, resume_text="", behavioral_document_text="", user_type="swe_ng"
    ):
        """
        Build the system prompt for the live interview.
        Pure logic: easy to unit test with string inputs.

        Args:
            company_name (str): Name of the company
            resume_text (str): Candidate's resume text
            behavioral_document_text (str): Company-specific behavioral questions
            user_type (str): "swe_ng" for SWE, "pm_ng" for PM

        Returns:
            str: Full system prompt for Gemini Live
        """
        behavioral_context = (
            behavioral_document_text[:3000]
            if behavioral_document_text
            else "No company-specific questions available."
        )

        resume_excerpt = resume_text[:2000] if resume_text else "No resume available."

        if user_type == "pm_ng":
            role_context = f"""You are an expert PM behavioral interviewer conducting a live interview for a Product Manager position at {company_name}.

FOCUS AREAS FOR PM INTERVIEWS:
- Leadership and influence without authority
- Cross-functional collaboration and stakeholder management
- Product thinking and strategic decision-making
- Conflict resolution and handling ambiguity
- Data-driven decision making
- Customer empathy and user-centric approach"""
        else:
            role_context = f"""You are an expert behavioral interviewer conducting a live interview for a Software Engineering position at {company_name}.

FOCUS AREAS FOR SWE INTERVIEWS:
- Technical problem-solving and debugging
- Collaboration with team members
- Handling technical challenges
- Code quality and best practices
- Learning and adaptation"""

        prompt = f"""{role_context}

CANDIDATE RESUME (Key Excerpts):
{resume_excerpt}

COMPANY-SPECIFIC BEHAVIORAL QUESTIONS BANK:
{behavioral_context}

YOUR ROLE AND GUIDELINES:
1. Conduct an adaptive behavioral interview with the candidate
2. Ask a MAXIMUM of 2 questions total
3. Use the candidate's resume to tailor questions
4. Draw inspiration from the company's behavioral question bank
5. Ask follow-up questions based on candidate responses
6. Keep the interview conversational and natural
7. After asking 2 questions and receiving 2 answers, you MUST:
    - Thank the candidate
    - Generate a comprehensive FINAL SUMMARY in TEXT format
    - Include overall assessment, strengths, improvements, notable responses, recommendation

AUDIO GUIDELINES:
- Speak naturally and professionally
- Keep questions clear and concise
- Allow the candidate time to think and respond
- Be encouraging and supportive

IMPORTANT: After the 2nd Q/A, output a final summary in TEXT and end the session.
"""
        return prompt

    def get_model_config(self):
        """
        Return Gemini Live model configuration.

        Returns:
            dict: Model configuration for Gemini Live
        """
        return {
            "model": "gemini-2.5-flash-native-audio-preview-09-2025",
            "generation_config": {
                "response_modalities": ["audio"],  # Audio output
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {"voice_name": "Puck"}
                    }
                },
            },
        }
