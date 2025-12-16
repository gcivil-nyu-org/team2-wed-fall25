from accounts.models import User, user_resume_upload_path


def test_user_resume_upload_path():
    class Itt:
        username = "alice"

    assert user_resume_upload_path(Itt(), "resume.pdf") == "resumes/alice/resume.pdf"


def test_user_str_and_has_resume():
    u = User(username="bob")
    u.resume = None
    assert "bob" in str(u)
    assert u.has_resume is False
    u.resume = object()
    assert u.has_resume is True
