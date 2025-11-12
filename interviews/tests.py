# Create your tests here.
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import InterviewSession, CodingRound, SystemDesignRound

class InterviewsModelTests(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(username='testuser', password='testpass')
        # Create a sample coding round
        self.coding_round = CodingRound.objects.create(title="Sample Coding Round", description="Test")
        # Create a sample system design round
        self.sd_round = SystemDesignRound.objects.create(title="Sample SD Round", description="Design test")
        # Create an interview session
        self.session = InterviewSession.objects.create(
            user=self.user,
            coding_round=self.coding_round,
            system_design_round=self.sd_round,
            status="Scheduled"
        )

    def test_interview_session_str(self):
        self.assertEqual(str(self.session), f"InterviewSession for {self.user.username}")

    def test_coding_round_str(self):
        self.assertEqual(str(self.coding_round), "Sample Coding Round")

    def test_system_design_round_str(self):
        self.assertEqual(str(self.sd_round), "Sample SD Round")


class InterviewsViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='viewuser', password='viewpass')
        self.client.login(username='viewuser', password='viewpass')
        self.coding_round = CodingRound.objects.create(title="View Coding", description="Desc")
        self.sd_round = SystemDesignRound.objects.create(title="View SD", description="Desc")
        self.session = InterviewSession.objects.create(
            user=self.user,
            coding_round=self.coding_round,
            system_design_round=self.sd_round,
            status="Scheduled"
        )

    def test_interview_list_view(self):
        url = reverse('interviews:list')  # Adjust according to your urls.py
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.session.status)

    def test_interview_detail_view(self):
        url = reverse('interviews:detail', args=[self.session.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.session.coding_round.title)

    def test_create_interview_view_get(self):
        url = reverse('interviews:create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_create_interview_view_post(self):
        url = reverse('interviews:create')
        data = {
            'user': self.user.id,
            'coding_round': self.coding_round.id,
            'system_design_round': self.sd_round.id,
            'status': 'Completed'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)  # Should redirect after creation
        self.assertTrue(InterviewSession.objects.filter(status='Completed').exists())

    def test_update_interview_view_post(self):
        url = reverse('interviews:update', args=[self.session.id])
        data = {'status': 'Completed'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'Completed')

    def test_delete_interview_view_post(self):
        url = reverse('interviews:delete', args=[self.session.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(InterviewSession.objects.filter(id=self.session.id).exists())
