"""
Gemini Live API service for audio-to-audio interview.
Handles initialization and configuration for Live session.
"""

import logging

# Removed: import google.generativeai as genai (Fixes F401 error)
from django.conf import settings

logger = logging.getLogger(__name__)


class GeminiLiveService:
    """
    Service for initializing and configuring Gemini Live sessions
    for behavioral + resume interviews.
    """

    def __init__(self):
        """Initialize Gemini Live API (NOW NON-BLOCKING)"""
        # Configuration is handled in consumers.py inside a threadpool.
        if not settings.GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not configured")

    def build_system_prompt(
        self, company_name, resume_text, behavioral_document_text, user_type="swe_ng"
    ):
        """
        Build the system prompt for the live interview.
        This function is pure logic (string manipulation).
        """
        # Truncate behavioral document to stay within token budget (max 3000 chars)
        behavioral_context = (
            behavioral_document_text[:3000]
            if behavioral_document_text
            else "No company-specific questions available."
        )

        # Truncate resume to key sections (max 2000 chars)
        resume_excerpt = resume_text[:2000] if resume_text else "No resume available."

        # Role-specific guidance
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
3. Use the candidate's resume to tailor questions (ask about their specific experiences, projects, roles)
4. Draw inspiration from the company's behavioral question bank above
5. Ask follow-up questions based on candidate responses to probe deeper
6. Keep the interview conversational and natural
7. After asking 2 questions and receiving 2 answers, you MUST:
    - Thank the candidate
    - Generate a comprehensive FINAL SUMMARY in TEXT format (not audio)
    - The summary should include:
      * Overall assessment of the candidate
      * Key strengths demonstrated
      * Areas for improvement
      * Notable responses
      * Recommendation for next steps

AUDIO GUIDELINES:
- Speak naturally and professionally
- Keep questions clear and concise
- Allow the candidate time to think and respond
- Be encouraging and supportive

IMPORTANT: After the 2nd question-answer exchange, output a final summary in TEXT (not audio) and end the session.
"""
        return prompt

    def get_model_config(self):
        """
        Get the configuration for Gemini Live model.

        Returns:
            dict: Model configuration
        """
        return {
            "model": "gemini-2.5-flash-native-audio-preview-09-2025",
            "generation_config": {
                "response_modalities": ["audio"],  # Audio output for Q/A
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": "Puck"  # Professional voice
                        }
                    }
                },
            },
        }
