from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import InterviewSession

User = get_user_model()

class InterviewViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="pass1234")
        self.client.login(username="testuser", password="pass1234")

    def test_start_session_view_authenticated(self):
        """Authenticated user can access the start session page"""
        response = self.client.get(reverse("start_session"))
        # Expect 200 or 302 if view redirects after setup
        self.assertIn(response.status_code, [200, 302])

    def test_start_session_requires_login(self):
        """Anonymous user should be redirected to login"""
        self.client.logout()
        response = self.client.get(reverse("start_session"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.url)

    def test_interview_session_creation(self):
        """Creating a new InterviewSession model instance"""
        session = InterviewSession.objects.create(user=self.user)
        self.assertIsInstance(session, InterviewSession)
        self.assertEqual(str(session.user.username), "testuser")
