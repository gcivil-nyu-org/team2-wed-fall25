import logging
from unittest.mock import patch

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from channels.db import database_sync_to_async

# Local Imports
# (Ensure these apps exist in your project, otherwise tests will fail on import)
from companies.models import Company
from .gemini_service import GeminiAnalyzer
from .rag_service import RAGService
from .models import (
    InterviewSession,
    CodingRound,
    SystemDesignRound,
    ProductSenseRound,
    AnalyticalStrategyRound,
)

logger = logging.getLogger(__name__)


# --- Helpers ---


@database_sync_to_async
def get_session_or_404(user):
    """Safely fetch the active session using synchronous ORM."""
    session = InterviewSession.objects.filter(user=user, status="active").first()
    if not session:
        raise Http404("No active InterviewSession matches the given query.")
    return session


@database_sync_to_async
def async_message(request, level, message):
    """Helper to send messages safely in async contexts."""
    if level == "error":
        messages.error(request, message)
    elif level == "info":
        messages.info(request, message)


def get_companies_list():
    """Get list of companies from database formatted as (slug, name) tuples."""
    return [
        (company.slug, company.name)
        for company in Company.objects.all().order_by("name")
    ]


# --- Views ---


@login_required
def start_session_view(request):
    """
    View to start a new interview session or continue existing one.
    """
    active_session = InterviewSession.objects.filter(
        user=request.user, status="active"
    ).first()

    if active_session:
        return redirect("interview_analysis")

    if request.method == "POST":
        company_slug = request.POST.get("company")
        job_description = request.POST.get("job_description", "").strip()
        companies_list = get_companies_list()

        # Validation
        valid_company_slugs = [slug for slug, _ in companies_list]
        context = {
            "companies": companies_list,
            "job_description": job_description,
            "selected_company": company_slug,
        }

        if not company_slug or company_slug not in valid_company_slugs:
            messages.error(request, "Please select a valid company.")
            return render(request, "interviews/start_session.html", context)

        if not job_description:
            messages.error(request, "Please enter a job description.")
            return render(request, "interviews/start_session.html", context)

        if len(job_description) < 50:
            messages.error(
                request, "Job description must be at least 50 characters long."
            )
            return render(request, "interviews/start_session.html", context)

        if not getattr(request.user, "has_resume", False):
            messages.error(
                request,
                "Please upload your resume before starting an interview session.",
            )
            return redirect("profile")

        try:
            session = InterviewSession.objects.create(
                user=request.user,
                company=company_slug,
                job_description=job_description,
                status="active",
            )
            messages.success(
                request,
                f"Interview session started for {session.get_company_display()}!",
            )
            return redirect("interview_analysis")

        except IntegrityError:
            messages.error(
                request,
                "You have an active session. Please end it before starting a new one.",
            )
            return redirect("dashboard")

    return render(
        request,
        "interviews/start_session.html",
        {"companies": get_companies_list()},
    )


@login_required
def resume_analysis_view(request):
    """
    View to display or generate resume analysis results.
    """
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    if not session.has_analysis():
        analyzer = GeminiAnalyzer()
        try:
            resume_text = analyzer.extract_text_from_pdf(request.user.resume)
        except Exception as e:
            logger.error(f"Error reading resume: {e}")
            messages.error(request, "Error reading resume file.")
            resume_text = "Resume text could not be extracted."

        analysis_result = analyzer.analyze_resume_fit(
            resume_text=resume_text,
            job_description=session.job_description,
            company_name=session.get_company_display(),
        )

        session.resume_fit_score = analysis_result.get("fit_score", 0)
        session.resume_analysis = analysis_result.get("analysis", "")
        session.resume_suggestions = analysis_result.get("suggestions", "")
        session.save()

        messages.success(request, "Resume analysis completed!")

    return render(request, "interviews/analysis.html", {"session": session})


@login_required
def end_session_view(request):
    """
    View to end the current active interview session.
    """
    session = InterviewSession.objects.filter(
        user=request.user, status="active"
    ).first()

    if request.method == "POST":
        if session:
            session.status = "completed"
            session.save()
            messages.success(request, "Interview session ended successfully.")
        else:
            messages.info(request, "No active session found.")
        return redirect("dashboard")

    if not session:
        raise Http404("No active session")

    return render(request, "interviews/end_session_confirm.html", {"session": session})


@login_required
def coding_round_view(request):
    """
    Coding round view (Q1) with RAG-powered question generation.
    """
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    if request.user.user_type != "swe_ng":
        messages.error(request, "This step is only available for Software Engineers.")
        return redirect("interview_analysis")

    coding_round, created = CodingRound.objects.get_or_create(
        session=session, question_number=1
    )

    if created or not coding_round.generated_questions:
        rag_service = RAGService()
        document_text = rag_service.retrieve_coding_question(session.company)

        if not document_text:
            document_text = (
                "Write a function to find the longest substring without repeating characters."
            )
            messages.warning(request, "Using fallback question.")

        analyzer = GeminiAnalyzer()
        generated_questions = analyzer.select_and_generate_questions(
            document_text=document_text,
            company_name=session.get_company_display(),
            num_questions=2,
        )

        coding_round.base_question = "Generated from company-specific document"
        coding_round.generated_questions = generated_questions
        coding_round.selected_question_index = 0
        coding_round.save()
        messages.success(request, "Coding questions generated successfully!")

    if request.method == "POST":
        user_code = request.POST.get("user_code", "").strip()
        language = request.POST.get("language", "python")

        if not user_code:
            messages.error(request, "Please write some code before submitting.")
        else:
            coding_round.user_code = user_code
            coding_round.language = language
            coding_round.save()

            selected_question = coding_round.get_selected_question()
            if selected_question:
                analyzer = GeminiAnalyzer()
                evaluation = analyzer.evaluate_code(
                    question=selected_question.get("question", ""),
                    reference_solution=selected_question.get("solution", ""),
                    user_code=user_code,
                    language=language,
                )

                coding_round.evaluation_result = evaluation
                coding_round.save()
                session.coding_q1_completed = True
                session.save()

                score = evaluation.get("score", 0)
                if evaluation.get("is_correct"):
                    messages.success(request, f"Great job! Score: {score}/100")
                else:
                    messages.info(request, f"Needs improvement. Score: {score}/100")
            else:
                messages.error(request, "Could not evaluate: question not found.")

    return render(
        request,
        "interviews/step_coding_round.html",
        {
            "session": session,
            "coding_round": coding_round,
            "selected_question": coding_round.get_selected_question(),
        },
    )


@login_required
def coding_round_q2_view(request):
    """
    Coding round Q2 view.
    """
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    if request.user.user_type != "swe_ng":
        messages.error(request, "This step is only available for Software Engineers.")
        return redirect("interview_analysis")

    coding_round, created = CodingRound.objects.get_or_create(
        session=session, question_number=2
    )

    if created or not coding_round.generated_questions:
        rag_service = RAGService()
        document_text = rag_service.retrieve_coding_question(session.company)

        if not document_text:
            document_text = "Write a function to implement an LRU cache."
            messages.warning(request, "Using fallback question.")

        analyzer = GeminiAnalyzer()
        generated_questions = analyzer.select_and_generate_questions(
            document_text=document_text,
            company_name=session.get_company_display(),
            num_questions=2,
        )

        coding_round.base_question = "Generated from company-specific document"
        coding_round.generated_questions = generated_questions
        coding_round.selected_question_index = 0
        coding_round.save()
        messages.success(request, "Coding question 2 generated successfully!")

    if request.method == "POST":
        user_code = request.POST.get("user_code", "").strip()
        language = request.POST.get("language", "python")

        if not user_code:
            messages.error(request, "Please write some code before submitting.")
        else:
            coding_round.user_code = user_code
            coding_round.language = language
            coding_round.save()

            selected_question = coding_round.get_selected_question()
            if selected_question:
                analyzer = GeminiAnalyzer()
                evaluation = analyzer.evaluate_code(
                    question=selected_question.get("question", ""),
                    reference_solution=selected_question.get("solution", ""),
                    user_code=user_code,
                    language=language,
                )
                coding_round.evaluation_result = evaluation
                coding_round.save()
                session.coding_q2_completed = True
                session.save()

                score = evaluation.get("score", 0)
                if evaluation.get("is_correct"):
                    messages.success(request, f"Great job! Score: {score}/100")
                else:
                    messages.info(request, f"Needs improvement. Score: {score}/100")

    return render(
        request,
        "interviews/step_coding_round_2.html",
        {
            "session": session,
            "coding_round": coding_round,
            "selected_question": coding_round.get_selected_question(),
        },
    )


@login_required
def system_design_view(request):
    """
    System Design view.
    """
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    if request.user.user_type != "swe_ng":
        messages.error(request, "This step is only available for Software Engineers.")
        return redirect("interview_analysis")

    sd_round, created = SystemDesignRound.objects.get_or_create(session=session)

    if created or not sd_round.generated_question:
        rag_service = RAGService()
        document_text = rag_service.retrieve_system_design_question(session.company)

        if not document_text:
            document_text = "Design a URL shortening service."
            messages.warning(request, "Using fallback question.")

        analyzer = GeminiAnalyzer()
        generated_question = analyzer.select_and_generate_system_design_question(
            document_text=document_text, company_name=session.get_company_display()
        )

        sd_round.base_question = "Generated from company-specific document"
        sd_round.generated_question = generated_question
        sd_round.save()
        messages.success(request, "System design question generated successfully!")

    if request.method == "POST":
        user_answer = request.POST.get("user_answer", "").strip()
        design_image = request.FILES.get("design_image", None)

        if not user_answer:
            messages.error(request, "Please write your design answer before submitting.")
        else:
            sd_round.user_answer = user_answer
            if design_image:
                if sd_round.design_image:
                    sd_round.design_image.delete(save=False)
                sd_round.design_image = design_image

            sd_round.save()

            question = sd_round.get_question()
            eval_criteria = (
                sd_round.generated_question.get("evaluation_criteria")
                if sd_round.generated_question
                else None
            )

            if question:
                analyzer = GeminiAnalyzer()
                evaluation = analyzer.evaluate_system_design(
                    question=question,
                    user_answer=user_answer,
                    evaluation_criteria=eval_criteria,
                    design_image=(
                        sd_round.design_image if sd_round.design_image else None
                    ),
                )
                sd_round.evaluation_result = evaluation
                sd_round.save()
                session.system_design_completed = True
                session.save()

                score = evaluation.get("score", 0)
                if evaluation.get("is_correct"):
                    messages.success(request, f"Excellent design! Score: {score}/100")
                else:
                    messages.info(request, f"Needs improvement. Score: {score}/100")

    return render(
        request,
        "interviews/step_system_design.html",
        {
            "session": session,
            "system_design_round": sd_round,
            "question": sd_round.get_question(),
        },
    )


@login_required
def product_sense_view(request):
    """
    Product Sense view (PM Role).
    """
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    if request.user.user_type != "pm_ng":
        messages.error(request, "This step is only available for Product Managers.")
        return redirect("interview_analysis")

    ps_round, created = ProductSenseRound.objects.get_or_create(session=session)

    if created or not ps_round.generated_case:
        rag_service = RAGService()
        document_text = rag_service.retrieve_product_sense_case(session.company)

        if not document_text:
            document_text = "Design a feature to improve user engagement."
            messages.warning(request, "Using fallback case.")

        analyzer = GeminiAnalyzer()
        generated_case = analyzer.select_and_generate_product_sense_case(
            document_text=document_text, company_name=session.get_company_display()
        )

        ps_round.base_case = "Generated from company-specific document"
        ps_round.generated_case = generated_case
        ps_round.save()
        messages.success(request, "Product sense case generated successfully!")

    if request.method == "POST":
        user_answer = request.POST.get("user_answer", "").strip()
        if not user_answer:
            messages.error(request, "Please write your answer before submitting.")
        else:
            ps_round.user_answer = user_answer
            ps_round.save()

            case = ps_round.get_case()
            eval_criteria = (
                ps_round.generated_case.get("evaluation_criteria")
                if ps_round.generated_case
                else None
            )

            if case:
                analyzer = GeminiAnalyzer()
                evaluation = analyzer.evaluate_product_sense(
                    case=case,
                    user_answer=user_answer,
                    evaluation_criteria=eval_criteria,
                )
                ps_round.evaluation_result = evaluation
                ps_round.save()
                session.product_sense_completed = True
                session.save()

                score = evaluation.get("score", 0)
                if evaluation.get("is_good"):
                    messages.success(request, f"Excellent! Score: {score}/100")
                else:
                    messages.info(request, f"Needs work. Score: {score}/100")

    return render(
        request,
        "interviews/step_product_sense.html",
        {
            "session": session,
            "product_sense_round": ps_round,
            "case": ps_round.get_case(),
        },
    )


@login_required
def analytical_strategy_view(request):
    """
    Analytical + Strategy view (PM Role).
    """
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    if request.user.user_type != "pm_ng":
        messages.error(request, "This step is only available for Product Managers.")
        return redirect("interview_analysis")

    as_round, created = AnalyticalStrategyRound.objects.get_or_create(session=session)

    if created or not as_round.generated_question:
        rag_service = RAGService()
        document_text = rag_service.retrieve_analytical_strategy_prompt(session.company)

        if not document_text:
            document_text = (
                "Design an experiment to identify the root cause of metric drop."
            )
            messages.warning(request, "Using fallback question.")

        analyzer = GeminiAnalyzer()
        generated_question = analyzer.select_and_generate_analytical_strategy_question(
            document_text=document_text, company_name=session.get_company_display()
        )

        as_round.base_question = "Generated from company-specific document"
        as_round.generated_question = generated_question
        as_round.save()
        messages.success(request, "Analytical/strategy question generated successfully!")

    if request.method == "POST":
        user_answer = request.POST.get("user_answer", "").strip()
        if not user_answer:
            messages.error(request, "Please write your answer before submitting.")
        else:
            as_round.user_answer = user_answer
            as_round.save()

            question = as_round.get_question()
            eval_criteria = (
                as_round.generated_question.get("evaluation_criteria")
                if as_round.generated_question
                else None
            )

            if question:
                analyzer = GeminiAnalyzer()
                evaluation = analyzer.evaluate_analytical_strategy(
                    question=question,
                    user_answer=user_answer,
                    evaluation_criteria=eval_criteria,
                )
                as_round.evaluation_result = evaluation
                as_round.save()
                session.analytical_strategy_completed = True
                session.save()

                score = evaluation.get("score", 0)
                if evaluation.get("is_good"):
                    messages.success(request, f"Excellent! Score: {score}/100")
                else:
                    messages.info(request, f"Needs work. Score: {score}/100")

    return render(
        request,
        "interviews/step_analytical_strategy.html",
        {
            "session": session,
            "analytical_strategy_round": as_round,
            "question": as_round.get_question(),
        },
    )


@login_required
async def behavioral_resume_live_view(request):
    """
    View for behavioral + resume live interview (Async).
    """
    try:
        session = await get_session_or_404(request.user)
    except Http404:
        await async_message(request, "error", "No active interview session found.")
        return redirect("start_session")

    if session.behavioral_resume_completed:
        await async_message(
            request,
            "info",
            "Behavioral interview already completed. View your summary below.",
        )

    get_company_name_task = database_sync_to_async(session.get_company_display)
    company_name = await get_company_name_task()

    return render(
        request,
        "interviews/step_behavioral_resume_live.html",
        {
            "session": session,
            "company_name": company_name,
            "ws_scheme": "wss" if request.is_secure() else "ws",
            "ws_host": request.get_host(),
        },
    )


@login_required
def final_analysis_view(request):
    """
    Final analysis view showing overall readiness.
    """
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    # --- Role Specific Checks ---
    if request.user.user_type == "swe_ng":
        if not (
            session.coding_q1_completed
            and session.coding_q2_completed
            and session.system_design_completed
        ):
            messages.warning(
                request, "Please complete all sections before viewing final analysis."
            )
            # Simple redirection logic
            if not session.coding_q1_completed:
                return redirect("coding_round")
            elif not session.coding_q2_completed:
                return redirect("coding_round_q2")
            elif not session.system_design_completed:
                return redirect("system_design")

        coding_q1 = CodingRound.objects.filter(
            session=session, question_number=1
        ).first()
        coding_q2 = CodingRound.objects.filter(
            session=session, question_number=2
        ).first()
        system_design = SystemDesignRound.objects.filter(session=session).first()

        if not session.final_analysis or not session.overall_readiness_score:
            session_data = {
                "company": session.get_company_display(),
                "resume_score": session.resume_fit_score or 0,
                "resume_analysis": session.resume_analysis or "N/A",
                "coding_q1_score": (
                    coding_q1.evaluation_result.get("score", 0)
                    if coding_q1 and coding_q1.evaluation_result
                    else 0
                ),
                "coding_q2_score": (
                    coding_q2.evaluation_result.get("score", 0)
                    if coding_q2 and coding_q2.evaluation_result
                    else 0
                ),
                "system_design_score": (
                    system_design.evaluation_result.get("score", 0)
                    if system_design and system_design.evaluation_result
                    else 0
                ),
                "behavioral_resume_summary": session.behavioral_resume_summary
                or "Not completed",
            }

            scores = [
                session_data["resume_score"],
                session_data["coding_q1_score"],
                session_data["coding_q2_score"],
                session_data["system_design_score"],
            ]
            overall_score = sum(scores) // len(scores) if scores else 0

            analyzer = GeminiAnalyzer()
            final_result = analyzer.generate_final_analysis(session_data)

            session.overall_readiness_score = final_result.get(
                "overall_score", overall_score
            )
            session.final_analysis = final_result["analysis"]
            session.save()
            messages.success(request, "Final analysis generated successfully!")

        context = {
            "session": session,
            "coding_q1": coding_q1,
            "coding_q2": coding_q2,
            "system_design": system_design,
        }

    elif request.user.user_type == "pm_ng":
        if not (
            session.product_sense_completed and session.analytical_strategy_completed
        ):
            messages.warning(request, "Please complete all sections.")
            if not session.product_sense_completed:
                return redirect("product_sense")
            return redirect("analytical_strategy")

        product_sense = ProductSenseRound.objects.filter(session=session).first()
        analytical_strategy = AnalyticalStrategyRound.objects.filter(
            session=session
        ).first()

        if not session.final_analysis or not session.overall_readiness_score:
            session_data = {
                "company": session.get_company_display(),
                "role": "Product Manager",
                "resume_score": session.resume_fit_score or 0,
                "product_sense_score": (
                    product_sense.evaluation_result.get("score", 0)
                    if product_sense and product_sense.evaluation_result
                    else 0
                ),
                "analytical_strategy_score": (
                    analytical_strategy.evaluation_result.get("score", 0)
                    if analytical_strategy and analytical_strategy.evaluation_result
                    else 0
                ),
                "behavioral_resume_summary": session.behavioral_resume_summary
                or "Not completed",
            }

            scores = [
                session_data["resume_score"],
                session_data["product_sense_score"],
                session_data["analytical_strategy_score"],
            ]
            overall_score = sum(scores) // len(scores) if scores else 0

            analyzer = GeminiAnalyzer()
            final_result = analyzer.generate_final_analysis_pm(session_data)

            session.overall_readiness_score = final_result.get(
                "overall_score", overall_score
            )
            session.final_analysis = final_result["analysis"]
            session.save()
            messages.success(request, "Final analysis generated successfully!")

        context = {
            "session": session,
            "product_sense": product_sense,
            "analytical_strategy": analytical_strategy,
        }
    else:
        messages.error(request, "Invalid user type.")
        return redirect("dashboard")

    return render(request, "interviews/step_final_analysis.html", context)


# ==============================================================================
# INTEGRATED TESTS
# ==============================================================================
# To run these tests: python manage.py test interviews.views


class InterviewsViewsTests(TestCase):
    def setUp(self):
        # Create a user
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testuser",
            password="testpassword",
            user_type="swe_ng",
            has_resume=True,
        )
        self.user.resume = SimpleUploadedFile(
            "test_resume.pdf", b"content", content_type="application/pdf"
        )
        self.user.save()

        # Create a company
        self.company = Company.objects.create(name="Google", slug="google")

        # Create a session
        self.session = InterviewSession.objects.create(
            user=self.user,
            company="google",
            job_description="Test JD",
            status="active",
        )

        self.client = Client()
        self.client.login(username="testuser", password="testpassword")

    @patch("interviews.views.GeminiAnalyzer")
    @patch("interviews.views.RAGService")
    def test_start_session_view(self, mock_rag, mock_gemini):
        # Test GET
        response = self.client.get(reverse("start_session"))
        self.assertEqual(response.status_code, 200)

        # Ensure we redirect if session is active
        response = self.client.get(reverse("start_session"))
        # Should redirect to analysis
        self.assertEqual(response.status_code, 200)  # Logic in view: returns redirect

        # Create new user for POST test
        new_user = self.User.objects.create_user(
            username="newuser",
            password="password",
            has_resume=True,
        )
        self.client.login(username="newuser", password="password")

        # Test POST
        response = self.client.post(
            reverse("start_session"),
            {"company": "google", "job_description": "A very long job description..." * 5},
        )
        self.assertEqual(response.status_code, 302)  # Redirects to analysis
        self.assertTrue(
            InterviewSession.objects.filter(user=new_user, status="active").exists()
        )

    @patch("interviews.views.GeminiAnalyzer")
    def test_resume_analysis_view(self, MockGemini):
        # Setup Mock
        mock_instance = MockGemini.return_value
        mock_instance.extract_text_from_pdf.return_value = "Resume Text"
        mock_instance.analyze_resume_fit.return_value = {
            "fit_score": 85,
            "analysis": "Good fit",
            "suggestions": "Add X",
        }

        response = self.client.get(reverse("resume_analysis"))
        self.assertEqual(response.status_code, 200)

        self.session.refresh_from_db()
        self.assertEqual(self.session.resume_fit_score, 85)

    @patch("interviews.views.GeminiAnalyzer")
    @patch("interviews.views.RAGService")
    def test_coding_round_view(self, MockRAG, MockGemini):
        # Setup Mocks
        mock_rag = MockRAG.return_value
        mock_rag.retrieve_coding_question.return_value = "RAG Doc"

        mock_gemini = MockGemini.return_value
        mock_gemini.select_and_generate_questions.return_value = [
            {"question": "Q1", "solution": "S1"}
        ]
        mock_gemini.evaluate_code.return_value = {"score": 90, "is_correct": True}

        # Test GET (Generate Question)
        response = self.client.get(reverse("coding_round"))
        self.assertEqual(response.status_code, 200)

        coding_round = CodingRound.objects.get(session=self.session, question_number=1)
        self.assertEqual(coding_round.base_question, "Generated from company-specific document")

        # Test POST (Submit Code)
        response = self.client.post(
            reverse("coding_round"),
            {"user_code": "print('hello')", "language": "python"},
        )
        self.assertEqual(response.status_code, 200)
        
        coding_round.refresh_from_db()
        self.assertEqual(coding_round.evaluation_result["score"], 90)
        self.session.refresh_from_db()
        self.assertTrue(self.session.coding_q1_completed)

    def test_end_session_view(self):
        response = self.client.post(reverse("end_session"))
        self.assertEqual(response.status_code, 302)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "completed")
