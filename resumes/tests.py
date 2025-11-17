from django.test import TestCase
from django.urls import reverse
from .models import Resume

class ResumeViewTests(TestCase):
    def setUp(self):
        self.resume = Resume.objects.create(title="Test Resume")

    def test_resume_list_view(self):
        url = reverse("resumes:list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Resume")

    def test_resume_detail_view(self):
        url = reverse("resumes:detail", args=[self.resume.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Resume")

# Create your tests here.
