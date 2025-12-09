from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.messages import get_messages
from companies.models import Company
from interviews.models import (
    InterviewSession, 
    CodingRound, 
    SystemDesignRound, 
    ProductSenseRound, 
    AnalyticalStrategyRound
)

User = get_user_model()

class InterviewViewsCoverageTest(TestCase):
    def setUp(self):
        # --- Setup Users ---
        self.swe_user = User.objects.create_user(
            username='swe', password='password', user_type='swe_ng', has_resume=True
        )
        # Mock resume
        self.resume_file = SimpleUploadedFile("resume.pdf", b"content", content_type="application/pdf")
        self.swe_user.resume = self.resume_file
        self.swe_user.save()

        self.pm_user = User.objects.create_user(
            username='pm', password='password', user_type='pm_ng', has_resume=True
        )
        
        self.no_resume_user = User.objects.create_user(
            username='no_resume', password='password', user_type='swe_ng', has_resume=False
        )

        # --- Setup Data ---
        self.company = Company.objects.create(name="TechCorp", slug="techcorp")
        self.client = Client()

    # =========================================================================
    # 1. Start Session Tests (Covers lines 43-134)
    # =========================================================================

    def test_start_session_get(self):
        self.client.force_login(self.swe_user)
        response = self.client.get(reverse('start_session'))
        self.assertEqual(response.status_code, 200)

    def test_start_session_redirect_if_active(self):
        InterviewSession.objects.create(user=self.swe_user, company='techcorp', status='active')
        self.client.force_login(self.swe_user)
        response = self.client.get(reverse('start_session'))
        self.assertRedirects(response, reverse('interview_analysis'))

    def test_start_session_post_success(self):
        self.client.force_login(self.swe_user)
        response = self.client.post(reverse('start_session'), {
            'company': 'techcorp',
            'job_description': 'A very long description ' * 5  # > 50 chars
        })
        self.assertRedirects(response, reverse('interview_analysis'))
        self.assertTrue(InterviewSession.objects.filter(user=self.swe_user, status='active').exists())

    def test_start_session_post_invalid(self):
        self.client.force_login(self.swe_user)
        # Short description
        response = self.client.post(reverse('start_session'), {
            'company': 'techcorp',
            'job_description': 'Short'
        })
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("at least 50 characters" in str(m) for m in messages))

        # Invalid company
        response = self.client.post(reverse('start_session'), {
            'company': 'fake_co',
            'job_description': 'Long description ' * 5
        })
        self.assertContains(response, "Please select a valid company")

    def test_start_session_no_resume(self):
        self.client.force_login(self.no_resume_user)
        response = self.client.post(reverse('start_session'), {
            'company': 'techcorp',
            'job_description': 'Long description ' * 5
        })
        self.assertRedirects(response, reverse('profile'))

    # =========================================================================
    # 2. Resume Analysis (Covers lines 148-177)
    # =========================================================================

    @patch('interviews.views.GeminiAnalyzer')
    def test_resume_analysis(self, MockAnalyzer):
        session = InterviewSession.objects.create(user=self.swe_user, company='techcorp', status='active')
        
        # Mock Gemini
        MockAnalyzer.return_value.extract_text_from_pdf.return_value = "Resume content"
        MockAnalyzer.return_value.analyze_resume_fit.return_value = {
            "fit_score": 90, "analysis": "Good", "suggestions": "None"
        }

        self.client.force_login(self.swe_user)
        response = self.client.get(reverse('interview_analysis'))
        
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.resume_fit_score, 90)

    # =========================================================================
    # 3. SWE Rounds: Coding Q1, Q2, System Design (Covers lines 213-318, 562-786)
    # =========================================================================

    @patch('interviews.views.RAGService')
    @patch('interviews.views.GeminiAnalyzer')
    def test_coding_round_q1_flow(self, MockAnalyzer, MockRAG):
        # Setup
        session = InterviewSession.objects.create(user=self.swe_user, company='techcorp', status='active')
        MockRAG.return_value.retrieve_coding_question.return_value = "Doc"
        MockAnalyzer.return_value.select_and_generate_questions.return_value = [{"question": "Q1", "solution": "S1"}]
        MockAnalyzer.return_value.evaluate_code.return_value = {"is_correct": True, "score": 100}

        self.client.force_login(self.swe_user)

        # GET (Generate)
        response = self.client.get(reverse('coding_round'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CodingRound.objects.filter(session=session, question_number=1).exists())

        # POST (Submit)
        response = self.client.post(reverse('coding_round'), {
            'user_code': 'print("test")', 'language': 'python'
        })
        session.refresh_from_db()
        self.assertTrue(session.coding_q1_completed)

    @patch('interviews.views.RAGService')
    @patch('interviews.views.GeminiAnalyzer')
    def test_coding_round_q2_flow(self, MockAnalyzer, MockRAG):
        # Setup
        session = InterviewSession.objects.create(user=self.swe_user, company='techcorp', status='active')
        MockRAG.return_value.retrieve_coding_question.return_value = "Doc"
        MockAnalyzer.return_value.select_and_generate_questions.return_value = [{"question": "Q2", "solution": "S2"}]
        MockAnalyzer.return_value.evaluate_code.return_value = {"is_correct": False, "score": 50}

        self.client.force_login(self.swe_user)

        # GET
        self.client.get(reverse('coding_round_q2'))
        # POST
        self.client.post(reverse('coding_round_q2'), {'user_code': 'code', 'language': 'python'})
        
        session.refresh_from_db()
        self.assertTrue(session.coding_q2_completed)

    @patch('interviews.views.GeminiAnalyzer')
    def test_system_design_flow(self, MockAnalyzer):
        session = InterviewSession.objects.create(user=self.swe_user, company='techcorp', status='active')
        SystemDesignRound.objects.create(
            session=session,
            generated_question={"question": "Design X", "evaluation_criteria": "Y"}
        )
        MockAnalyzer.return_value.evaluate_system_design.return_value = {"is_correct": True, "score": 95}

        self.client.force_login(self.swe_user)
        
        img = SimpleUploadedFile("design.png", b"\x89PNG\r\n...", content_type="image/png")
        response = self.client.post(reverse('system_design'), {
            'user_answer': 'My Design',
            'design_image': img
        })
        
        session.refresh_from_db()
        self.assertTrue(session.system_design_completed)
        self.assertTrue(session.system_design_round.design_image)

    # =========================================================================
    # 4. PM Rounds: Product Sense, Analytical (Covers lines 336-544)
    # =========================================================================

    @patch('interviews.views.RAGService')
    @patch('interviews.views.GeminiAnalyzer')
    def test_pm_flow_product_sense(self, MockAnalyzer, MockRAG):
        session = InterviewSession.objects.create(user=self.pm_user, company='techcorp', status='active')
        MockRAG.return_value.retrieve_product_sense_case.return_value = "Case"
        MockAnalyzer.return_value.select_and_generate_product_sense_case.return_value = {"case": "C", "criteria": "C"}
        MockAnalyzer.return_value.evaluate_product_sense.return_value = {"is_good": True, "score": 88}

        self.client.force_login(self.pm_user)
        
        # GET
        self.client.get(reverse('product_sense'))
        # POST
        self.client.post(reverse('product_sense'), {'user_answer': 'Strategy'})
        
        session.refresh_from_db()
        self.assertTrue(session.product_sense_completed)

    @patch('interviews.views.RAGService')
    @patch('interviews.views.GeminiAnalyzer')
    def test_pm_flow_analytical(self, MockAnalyzer, MockRAG):
        session = InterviewSession.objects.create(user=self.pm_user, company='techcorp', status='active')
        MockRAG.return_value.retrieve_analytical_strategy_prompt.return_value = "Prompt"
        MockAnalyzer.return_value.select_and_generate_analytical_strategy_question.return_value = {"q": "Q", "criteria": "C"}
        MockAnalyzer.return_value.evaluate_analytical_strategy.return_value = {"is_good": True, "score": 92}

        self.client.force_login(self.pm_user)
        
        # GET
        self.client.get(reverse('analytical_strategy'))
        # POST
        self.client.post(reverse('analytical_strategy'), {'user_answer': 'Analysis'})
        
        session.refresh_from_db()
        self.assertTrue(session.analytical_strategy_completed)

    def test_role_access_control(self):
        # PM trying to access SWE round
        session = InterviewSession.objects.create(user=self.pm_user, company='techcorp', status='active')
        self.client.force_login(self.pm_user)
        response = self.client.get(reverse('coding_round'))
        self.assertRedirects(response, reverse('interview_analysis'))

        # SWE trying to access PM round
        session_swe = InterviewSession.objects.create(user=self.swe_user, company='techcorp', status='active')
        self.client.force_login(self.swe_user)
        response = self.client.get(reverse('product_sense'))
        self.assertRedirects(response, reverse('interview_analysis'))

    # =========================================================================
    # 5. Final Analysis (Covers lines 860-1056)
    # =========================================================================

    def test_final_analysis_swe_incomplete(self):
        # SWE with only Q1 done
        session = InterviewSession.objects.create(
            user=self.swe_user, company='techcorp', status='active',
            coding_q1_completed=True
        )
        self.client.force_login(self.swe_user)
        response = self.client.get(reverse('final_analysis'))
        # Should redirect to Q2
        self.assertRedirects(response, reverse('coding_round_q2'))

    @patch('interviews.views.GeminiAnalyzer')
    def test_final_analysis_swe_complete(self, MockAnalyzer):
        session = InterviewSession.objects.create(
            user=self.swe_user, company='techcorp', status='active',
            coding_q1_completed=True, coding_q2_completed=True, system_design_completed=True
        )
        # Setup mock rounds
        CodingRound.objects.create(session=session, question_number=1, evaluation_result={'score': 80})
        CodingRound.objects.create(session=session, question_number=2, evaluation_result={'score': 90})
        SystemDesignRound.objects.create(session=session, evaluation_result={'score': 85})

        MockAnalyzer.return_value.generate_final_analysis.return_value = {
            "overall_score": 85, "analysis": "Hired"
        }

        self.client.force_login(self.swe_user)
        response = self.client.get(reverse('final_analysis'))
        
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.overall_readiness_score, 85)

    @patch('interviews.views.GeminiAnalyzer')
    def test_final_analysis_pm_complete(self, MockAnalyzer):
        session = InterviewSession.objects.create(
            user=self.pm_user, company='techcorp', status='active',
            product_sense_completed=True, analytical_strategy_completed=True
        )
        ProductSenseRound.objects.create(session=session, evaluation_result={'score': 80})
        AnalyticalStrategyRound.objects.create(session=session, evaluation_result={'score': 90})

        MockAnalyzer.return_value.generate_final_analysis_pm.return_value = {
            "overall_score": 85, "analysis": "PM Hired"
        }

        self.client.force_login(self.pm_user)
        response = self.client.get(reverse('final_analysis'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PM Hired")

    # =========================================================================
    # 6. Async & Misc (Covers lines 810-842)
    # =========================================================================

    def test_behavioral_live_view(self):
        session = InterviewSession.objects.create(user=self.swe_user, company='techcorp', status='active')
        self.client.force_login(self.swe_user)
        response = self.client.get(reverse('behavioral_resume_live'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "wss")

    def test_end_session(self):
        session = InterviewSession.objects.create(user=self.swe_user, company='techcorp', status='active')
        self.client.force_login(self.swe_user)
        response = self.client.post(reverse('end_session'))
        self.assertRedirects(response, reverse('dashboard'))
        session.refresh_from_db()
        self.assertEqual(session.status, 'completed')# Create your tests here.
