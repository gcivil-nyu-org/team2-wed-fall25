"""
Service wrapper for Gemini Live API.
"""

import google.generativeai as genai
from django.conf import settings


class GeminiLiveService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        genai.configure(api_key=self.api_key)

    def build_system_prompt(
        self, company_name, resume_text, behavioral_document_text, user_type
    ):
        """Build a system prompt combining resume, behavioral doc, and role type"""
        if not resume_text:
            resume_text = "No resume available."
        if not behavioral_document_text:
            behavioral_document_text = "No company-specific questions available."

        # Truncate long inputs
        resume_text = resume_text[:2000]
        behavioral_document_text = behavioral_document_text[:3000]

        role_section = ""
        if user_type == "pm_ng":
            role_section = "You are interviewing a candidate for a Product Manager position. FOCUS AREAS FOR PM INTERVIEWS."
        else:
            role_section = "You are interviewing a candidate for a Software Engineering position. FOCUS AREAS FOR SWE INTERVIEWS."

        system_prompt = f"""
Company: {company_name}

Resume:
{resume_text}

Behavioral Document:
{behavioral_document_text}

Role-specific instructions:
{role_section}
"""
        return system_prompt

    def get_model_config(self):
        """Return Gemini Live model config"""
        return {
            "model": "gemini-2.5-flash",
            "generation_config": {
                "response_modalities": ["audio"],
                "speech_config": {
                    "voice_config": {"prebuilt_voice_config": {"voice_name": "Puck"}}
                },
            },
        }
