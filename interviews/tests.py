# from django.test import TestCase

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import InterviewSession

class InterviewViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="pass1234")
        self.client.login(username="testuser", password="pass1234")

    def test_interview_home_view_authenticated(self):
        response = self.client.get(reverse("interview_home"))  # replace with your actual name
        self.assertEqual(response.status_code, 200)

    def test_interview_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("interview_home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.url)

    def test_interview_session_creation(self):
        session = InterviewSession.objects.create(user=self.user)
        self.assertTrue(isinstance(session, InterviewSession))
        self.assertEqual(str(session.user.username), "testuser")

