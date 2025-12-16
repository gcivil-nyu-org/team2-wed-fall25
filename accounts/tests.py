import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from accounts.forms import (CustomAuthenticationForm, CustomUserCreationForm,
                            ResumeUpdateForm)

# Ensure MEDIA_ROOT exists for file uploads in tests
settings.MEDIA_ROOT = getattr(settings, "MEDIA_ROOT", tempfile.mkdtemp())

User = get_user_model()


class TestCustomUserCreationForm(TestCase):
    def get_pdf(self, name="resume.pdf", size=1024, content_type="application/pdf"):
        """Return a dummy PDF file for testing"""
        return SimpleUploadedFile(
            name=name,
            content=b"x" * size,
            content_type=content_type,
        )

    def test_form_valid_without_resume(self):
        """Test creating a user without uploading a resume"""
        form = CustomUserCreationForm(
            data={
                "username": "john",
                "email": "john@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "user_type": "swe_ng",  # must match USER_TYPES
                "password1": "pass12345!",
                "password2": "pass12345!",
            }
        )
        if not form.is_valid():
            print(form.errors)
        self.assertTrue(form.is_valid())

    def test_form_save_saves_resume(self):
        """Test creating a user with a resume upload"""
        pdf = self.get_pdf()
        form = CustomUserCreationForm(
            data={
                "username": "john3",
                "email": "john3@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "user_type": "swe_ng",  # must match USER_TYPES
                "password1": "pass12345!",
                "password2": "pass12345!",
            },
            files={"resume": pdf},
        )
        if not form.is_valid():
            print(form.errors)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertTrue(user.resume)  # resume should be saved

    def test_resume_validation_fails_file_too_big(self):
        """Test validation fails when uploaded resume is too large (>5MB)"""
        pdf = self.get_pdf(size=6 * 1024 * 1024)  # 6MB
        form = CustomUserCreationForm(
            data={
                "username": "john2",
                "email": "john2@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "user_type": "swe_ng",
                "password1": "pass12345!",
                "password2": "pass12345!",
            },
            files={"resume": pdf},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("File size must be under 5MB.", str(form.errors))

    def test_resume_validation_fails_wrong_extension(self):
        """Test validation fails for wrong file extension"""
        file = SimpleUploadedFile("file.txt", b"x", content_type="application/pdf")
        form = CustomUserCreationForm(
            data={
                "username": "userx",
                "email": "userx@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "user_type": "swe_ng",
                "password1": "pass12345!",
                "password2": "pass12345!",
            },
            files={"resume": file},
        )
        self.assertFalse(form.is_valid())

    def test_resume_validation_fails_wrong_mime(self):
        """Test validation fails if file MIME type is incorrect"""
        pdf = self.get_pdf(content_type="text/plain")
        pdf.name = "resume.pdf"
        form = CustomUserCreationForm(
            data={
                "username": "u3",
                "email": "u3@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "user_type": "swe_ng",
                "password1": "pass12345!",
                "password2": "pass12345!",
            },
            files={"resume": pdf},
        )
        self.assertFalse(form.is_valid())


class TestResumeUpdateForm(TestCase):
    def test_resume_update_valid(self):
        """Test updating an existing user's resume"""
        user = User.objects.create(username="x")
        pdf = SimpleUploadedFile("resume.pdf", b"123", content_type="application/pdf")
        form = ResumeUpdateForm(data={}, files={"resume": pdf}, instance=user)
        self.assertTrue(form.is_valid())


class TestCustomAuthenticationForm(TestCase):
    def test_placeholders_set(self):
        """Test placeholder attributes in the login form"""
        form = CustomAuthenticationForm()
        self.assertEqual(
            form.fields["username"].widget.attrs["placeholder"], "Username or Email"
        )
        self.assertEqual(
            form.fields["password"].widget.attrs["placeholder"], "Password"
        )
