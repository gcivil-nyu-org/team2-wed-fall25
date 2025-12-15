from django.db import models
from django.contrib.auth import get_user_model

# Remove pgvector import for now
# from pgvector.django import VectorField

User = get_user_model()


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    linkedin_url = models.URLField(blank=True, null=True)
    github_url = models.URLField(blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    target_role = models.CharField(max_length=100, blank=True)
    experience_level = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Resume(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="resumes")
    file = models.FileField(upload_to="resumes/")
    filename = models.CharField(max_length=255)
    is_current = models.BooleanField(default=True)
    extracted_text = models.TextField(blank=True)
    # Replace VectorField with TextField for now
    embedding_json = models.TextField(
        null=True, blank=True
    )  # Store embedding as JSON string if needed later
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
