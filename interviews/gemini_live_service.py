import pytest
from unittest import mock
from django.conf import settings
from interviews.gemini_live_service import GeminiLiveService


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    # Ensure GEMINI_API_KEY is set to something for most tests
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "dummy_key")


def test_init_logs_error_if_no_api_key(monkeypatch, caplog):
    # Remove API key
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    with caplog.at_level("ERROR"):
        service = GeminiLiveService()
    assert "GEMINI_API_KEY not configured" in caplog.text


def test_init_sets_api_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test_key")
    service = GeminiLiveService()
    assert service.api_key == "test_key"


@pytest.mark.parametrize("user_type", ["swe_ng", "pm_ng"])
def test_build_system_prompt_contains_inputs(user_type):
    service = GeminiLiveService()
    company_name = "Acme Corp"
    resume_text = "Candidate resume here"
    behavioral_text = "Behavioral Qs here"

    prompt = service.build_system_prompt(
        company_name, resume_text, behavioral_text, user_type=user_type
    )

    # Check that the inputs appear in the prompt
    assert company_name in prompt
    assert resume_text in prompt
    assert behavioral_text in prompt

    # Check role-specific text is included
    if user_type == "pm_ng":
        assert "Product Manager position" in prompt
        assert "FOCUS AREAS FOR PM INTERVIEWS" in prompt
    else:
        assert "Software Engineering position" in prompt
        assert "FOCUS AREAS FOR SWE INTERVIEWS" in prompt


def test_build_system_prompt_handles_empty_inputs():
    service = GeminiLiveService()
    prompt = service.build_system_prompt("", "", "")
    assert "No resume available." in prompt
    assert "No company-specific questions available." in prompt


def test_build_system_prompt_truncates_long_inputs():
    service = GeminiLiveService()
    long_resume = "R" * 5000
    long_behavioral = "B" * 5000

    prompt = service.build_system_prompt("X", long_resume, long_behavioral)
    # Resume truncated to 2000 chars, behavioral to 3000
    assert "R" * 2000 in prompt
    assert "B" * 3000 in prompt


def test_get_model_config_returns_expected_dict():
    service = GeminiLiveService()
    config = service.get_model_config()
    assert isinstance(config, dict)
    assert config["model"].startswith("gemini-2.5")
    assert "generation_config" in config
    gen_config = config["generation_config"]
    assert "response_modalities" in gen_config
    assert gen_config["response_modalities"] == ["audio"]
    assert "speech_config" in gen_config
    voice_name = gen_config["speech_config"]["voice_config"]["prebuilt_voice_config"]["voice_name"]
    assert voice_name == "Puck"
