from django.contrib.auth.models import AbstractUser
from django.db import models


def user_resume_upload_path(instance, filename):
    """Generate upload path for user resumes"""
    return f"resumes/{instance.username}/{filename}"


class User(AbstractUser):
    USER_TYPES = (
        ("swe_ng", "Software Engineer New Grad"),
        ("pm_ng", "Product Manager New Grad"),
    )

    user_type = models.CharField(max_length=10, choices=USER_TYPES, default="swe_ng")
    resume = models.FileField(
        upload_to=user_resume_upload_path,
        null=True,
        blank=True,
        help_text="Upload your resume (PDF format recommended)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"

    @property
    def has_resume(self):
        return bool(self.resume)
