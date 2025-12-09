from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404  # Added for raising 404 in async wrapper

# --- TEST IMPORTS (Added for integrated testing) ---
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

# ---------------------------------------------------

# IMPORT FIX: We need this to safely run synchronous database calls in the ASGI environment
from channels.db import database_sync_to_async

from companies.models import Company
from .gemini_service import GeminiAnalyzer
from .models import (
    InterviewSession,
    CodingRound,
    SystemDesignRound,
    ProductSenseRound,
    AnalyticalStrategyRound,
)


# ASYNC WRAPPER FIX: Create a wrapper function to safely run synchronous ORM logic
@database_sync_to_async
def get_session_or_404(user):
    """Safely fetch the active session using synchronous ORM."""
    session = InterviewSession.objects.filter(user=user, status="active").first()

    if not session:
        # Raise standard Django exception if session is not found
        raise Http404("No active InterviewSession matches the given query.")
    return session


# Get companies list function - synchronous since it's only used in sync views
def get_companies_list():
    """Get list of companies from database formatted as (slug, name) tuples"""
    return [
        (company.slug, company.name)
        for company in Company.objects.all().order_by("name")
    ]


@login_required
def start_session_view(request):
    """
    View to start a new interview session or continue existing one.
    Displays form with company dropdown and job description textarea.
    """
    # Check if user already has an active session
    active_session = InterviewSession.objects.filter(
        user=request.user, status="active"
    ).first()

    if active_session:
        # If session has analysis, show it; otherwise, process it
        if active_session.has_analysis():
            return redirect("interview_analysis")
        else:
            return redirect("interview_analysis")

    if request.method == "POST":
        company = request.POST.get("company")
        job_description = request.POST.get("job_description", "").strip()

        # Get companies list for template
        companies_list = get_companies_list()

        # Validation - check if company slug exists in database
        valid_company_slugs = [slug for slug, _ in companies_list]
        if not company or company not in valid_company_slugs:
            messages.error(request, "Please select a valid company.")
            return render(
                request,
                "interviews/start_session.html",
                {
                    "companies": companies_list,
                    "job_description": job_description,
                },
            )

        if not job_description:
            messages.error(request, "Please enter a job description.")
            return render(
                request,
                "interviews/start_session.html",
                {
                    "companies": companies_list,
                    "selected_company": company,
                },
            )

        if len(job_description) < 50:
            messages.error(
                request, "Job description must be at least 50 characters long."
            )
            return render(
                request,
                "interviews/start_session.html",
                {
                    "companies": companies_list,
                    "selected_company": company,
                    "job_description": job_description,
                },
            )

        # Check if user has uploaded a resume
        if not request.user.has_resume:
            messages.error(
                request,
                "Please upload your resume before starting an interview session.",
            )
            return redirect("profile")

        try:
            # Create new session
            session = InterviewSession.objects.create(
                user=request.user,
                company=company,
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
                "You already have an active session. Please end it before starting a new one.",
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
    Calls Gemini API to analyze resume fit with job description.
    """
    # Get active session
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    # If analysis doesn't exist yet, generate it
    if not session.has_analysis():
        # Initialize Gemini analyzer
        analyzer = GeminiAnalyzer()

        # Extract resume text
        try:
            resume_text = analyzer.extract_text_from_pdf(request.user.resume)
        except Exception as e:
            messages.error(request, f"Error reading resume: {str(e)}")
            resume_text = "Resume text could not be extracted."

        # Analyze resume fit
        analysis_result = analyzer.analyze_resume_fit(
            resume_text=resume_text,
            job_description=session.job_description,
            company_name=session.get_company_display(),
        )

        # Save results to session
        session.resume_fit_score = analysis_result["fit_score"]
        session.resume_analysis = analysis_result["analysis"]
        session.resume_suggestions = analysis_result["suggestions"]
        session.save()

        messages.success(request, "Resume analysis completed!")

    return render(request, "interviews/analysis.html", {"session": session})


@login_required
def end_session_view(request):
    """
    View to end the current active interview session.
    """
    if request.method == "POST":
        # Get active session
        session = InterviewSession.objects.filter(
            user=request.user, status="active"
        ).first()

        if session:
            session.status = "completed"
            session.save()
            messages.success(request, "Interview session ended successfully.")
        else:
            messages.info(request, "No active session found.")

        return redirect("dashboard")

    # If GET request, show confirmation page
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    return render(request, "interviews/end_session_confirm.html", {"session": session})


@login_required
def coding_round_view(request):
    """
    Coding round view with RAG-powered question generation and evaluation.
    GET: Display question or generate if not exists
    POST: Evaluate submitted code
    """
    from .models import CodingRound
    from .rag_service import RAGService

    # Get active session
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    # Ensure user is SWE type
    if request.user.user_type != "swe_ng":
        messages.error(
            request, "This step is only available for Software Engineer role."
        )
        return redirect("interview_analysis")

    # Get or create coding round for question 1
    coding_round, created = CodingRound.objects.get_or_create(
        session=session, question_number=1
    )

    # If newly created or no questions generated yet, generate them
    if created or not coding_round.generated_questions:
        rag_service = RAGService()

        # Retrieve one random coding document for this company
        document_text = rag_service.retrieve_coding_question(session.company)

        if not document_text:
            document_text = "Write a function to find the longest substring without repeating characters."
            messages.warning(
                request,
                "Using fallback question. Please ensure company documents are uploaded.",
            )

        # Let Gemini select best question and generate similar ones
        analyzer = GeminiAnalyzer()
        generated_questions = analyzer.select_and_generate_questions(
            document_text=document_text,
            company_name=session.get_company_display(),
            num_questions=2,
        )

        # Save to coding round
        coding_round.base_question = "Generated from company-specific document"
        coding_round.generated_questions = generated_questions
        coding_round.selected_question_index = 0  # Show first question
        coding_round.save()

        messages.success(request, "Coding questions generated successfully!")

    # Handle POST: code submission and evaluation
    if request.method == "POST":
        user_code = request.POST.get("user_code", "").strip()
        language = request.POST.get("language", "python")

        if not user_code:
            messages.error(request, "Please write some code before submitting.")
        else:
            # Save user submission
            coding_round.user_code = user_code
            coding_round.language = language
            coding_round.save()

            # Evaluate the code
            selected_question = coding_round.get_selected_question()
            if selected_question:
                analyzer = GeminiAnalyzer()
                evaluation = analyzer.evaluate_code(
                    question=selected_question.get("question", ""),
                    reference_solution=selected_question.get("solution", ""),
                    user_code=user_code,
                    language=language,
                )

                # Save evaluation
                coding_round.evaluation_result = evaluation
                coding_round.save()

                # Mark coding Q1 as completed
                session.coding_q1_completed = True
                session.save()

                # Show feedback message
                if evaluation.get("is_correct"):
                    messages.success(
                        request, f"Great job! Score: {evaluation.get('score')}/100"
                    )
                else:
                    messages.info(
                        request,
                        f"Needs improvement. Score: {evaluation.get('score')}/100",
                    )
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
def product_sense_view(request):
    """
    Product Sense view with RAG-powered case generation and evaluation.
    """
    from .models import ProductSenseRound
    from .rag_service import RAGService

    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    if request.user.user_type != "pm_ng":
        messages.error(request, "This step is only available for Product Manager role.")
        return redirect("interview_analysis")

    product_sense_round, created = ProductSenseRound.objects.get_or_create(
        session=session
    )

    if created or not product_sense_round.generated_case:
        rag_service = RAGService()
        document_text = rag_service.retrieve_product_sense_case(session.company)

        if not document_text:
            document_text = "Design a feature to improve user engagement."
            messages.warning(request, "Using fallback case.")

        analyzer = GeminiAnalyzer()
        generated_case = analyzer.select_and_generate_product_sense_case(
            document_text=document_text, company_name=session.get_company_display()
        )

        product_sense_round.base_case = "Generated from company-specific document"
        product_sense_round.generated_case = generated_case
        product_sense_round.save()
        messages.success(request, "Product sense case generated successfully!")

    if request.method == "POST":
        user_answer = request.POST.get("user_answer", "").strip()
        if not user_answer:
            messages.error(request, "Please write your answer before submitting.")
        else:
            product_sense_round.user_answer = user_answer
            product_sense_round.save()

            case = product_sense_round.get_case()
            evaluation_criteria = (
                product_sense_round.generated_case.get("evaluation_criteria")
                if product_sense_round.generated_case
                else None
            )

            if case:
                analyzer = GeminiAnalyzer()
                evaluation = analyzer.evaluate_product_sense(
                    case=case,
                    user_answer=user_answer,
                    evaluation_criteria=evaluation_criteria,
                )
                product_sense_round.evaluation_result = evaluation
                product_sense_round.save()
                session.product_sense_completed = True
                session.save()

                if evaluation.get("is_good"):
                    messages.success(
                        request, f"Excellent! Score: {evaluation.get('score')}/100"
                    )
                else:
                    messages.info(
                        request, f"Needs work. Score: {evaluation.get('score')}/100"
                    )

    return render(
        request,
        "interviews/step_product_sense.html",
        {
            "session": session,
            "product_sense_round": product_sense_round,
            "case": product_sense_round.get_case(),
        },
    )


@login_required
def analytical_strategy_view(request):
    """
    Analytical + Strategy view with RAG-powered question generation and evaluation.
    """
    from .models import AnalyticalStrategyRound
    from .rag_service import RAGService

    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    if request.user.user_type != "pm_ng":
        messages.error(request, "This step is only available for Product Manager role.")
        return redirect("interview_analysis")

    analytical_strategy_round, created = AnalyticalStrategyRound.objects.get_or_create(
        session=session
    )

    if created or not analytical_strategy_round.generated_question:
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

        analytical_strategy_round.base_question = (
            "Generated from company-specific document"
        )
        analytical_strategy_round.generated_question = generated_question
        analytical_strategy_round.save()
        messages.success(
            request, "Analytical/strategy question generated successfully!"
        )

    if request.method == "POST":
        user_answer = request.POST.get("user_answer", "").strip()
        if not user_answer:
            messages.error(request, "Please write your answer before submitting.")
        else:
            analytical_strategy_round.user_answer = user_answer
            analytical_strategy_round.save()

            question = analytical_strategy_round.get_question()
            evaluation_criteria = (
                analytical_strategy_round.generated_question.get("evaluation_criteria")
                if analytical_strategy_round.generated_question
                else None
            )

            if question:
                analyzer = GeminiAnalyzer()
                evaluation = analyzer.evaluate_analytical_strategy(
                    question=question,
                    user_answer=user_answer,
                    evaluation_criteria=evaluation_criteria,
                )
                analytical_strategy_round.evaluation_result = evaluation
                analytical_strategy_round.save()
                session.analytical_strategy_completed = True
                session.save()

                if evaluation.get("is_good"):
                    messages.success(
                        request, f"Excellent! Score: {evaluation.get('score')}/100"
                    )
                else:
                    messages.info(
                        request, f"Needs work. Score: {evaluation.get('score')}/100"
                    )

    return render(
        request,
        "interviews/step_analytical_strategy.html",
        {
            "session": session,
            "analytical_strategy_round": analytical_strategy_round,
            "question": analytical_strategy_round.get_question(),
        },
    )


@login_required
def coding_round_q2_view(request):
    """
    Coding round Q2 view with RAG-powered question generation and evaluation.
    """
    from .models import CodingRound
    from .rag_service import RAGService

    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    if request.user.user_type != "swe_ng":
        messages.error(
            request, "This step is only available for Software Engineer role."
        )
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

                if evaluation.get("is_correct"):
                    messages.success(
                        request, f"Great job! Score: {evaluation.get('score')}/100"
                    )
                else:
                    messages.info(
                        request,
                        f"Needs improvement. Score: {evaluation.get('score')}/100",
                    )

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
    System Design view with RAG-powered question generation and evaluation.
    """
    from .models import SystemDesignRound
    from .rag_service import RAGService

    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    if request.user.user_type != "swe_ng":
        messages.error(
            request, "This step is only available for Software Engineer role."
        )
        return redirect("interview_analysis")

    system_design_round, created = SystemDesignRound.objects.get_or_create(
        session=session
    )

    if created or not system_design_round.generated_question:
        rag_service = RAGService()
        document_text = rag_service.retrieve_system_design_question(session.company)

        if not document_text:
            document_text = "Design a URL shortening service."
            messages.warning(request, "Using fallback question.")

        analyzer = GeminiAnalyzer()
        generated_question = analyzer.select_and_generate_system_design_question(
            document_text=document_text, company_name=session.get_company_display()
        )

        system_design_round.base_question = "Generated from company-specific document"
        system_design_round.generated_question = generated_question
        system_design_round.save()
        messages.success(request, "System design question generated successfully!")

    if request.method == "POST":
        user_answer = request.POST.get("user_answer", "").strip()
        design_image = request.FILES.get("design_image", None)

        if not user_answer:
            messages.error(
                request, "Please write your design answer before submitting."
            )
        else:
            system_design_round.user_answer = user_answer
            if design_image:
                if system_design_round.design_image:
                    system_design_round.design_image.delete(save=False)
                system_design_round.design_image = design_image

            system_design_round.save()

            question = system_design_round.get_question()
            evaluation_criteria = (
                system_design_round.generated_question.get("evaluation_criteria")
                if system_design_round.generated_question
                else None
            )

            if question:
                analyzer = GeminiAnalyzer()
                evaluation = analyzer.evaluate_system_design(
                    question=question,
                    user_answer=user_answer,
                    evaluation_criteria=evaluation_criteria,
                    design_image=(
                        system_design_round.design_image
                        if system_design_round.design_image
                        else None
                    ),
                )
                system_design_round.evaluation_result = evaluation
                system_design_round.save()
                session.system_design_completed = True
                session.save()

                if evaluation.get("is_correct"):
                    messages.success(
                        request,
                        f"Excellent design! Score: {evaluation.get('score')}/100",
                    )
                else:
                    messages.info(
                        request,
                        f"Needs improvement. Score: {evaluation.get('score')}/100",
                    )

    return render(
        request,
        "interviews/step_system_design.html",
        {
            "session": session,
            "system_design_round": system_design_round,
            "question": system_design_round.get_question(),
        },
    )


# Helper to send messages safely in async
@database_sync_to_async
def async_message(request, level, message):
    if level == "error":
        messages.error(request, message)
    elif level == "info":
        messages.info(request, message)


@login_required
async def behavioral_resume_live_view(request):
    """
    View for behavioral + resume live interview.
    Audio-to-audio interview using Gemini Live API.
    """
    # 1. Fetch Session (Safe)
    try:
        session = await get_session_or_404(request.user)
    except Http404:
        await async_message(request, "error", "No active interview session found.")
        return redirect("start_session")

    # 2. Check completed status (Safe) and send message safely
    if session.behavioral_resume_completed:
        await async_message(
            request,
            "info",
            "Behavioral interview already completed. View your summary below.",
        )

    # 3. Fetch Company Name (Safe)
    # This wrapper prevents the DB crash
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
    Final analysis view showing overall readiness and comprehensive feedback.
    Only accessible after all sections are completed.
    """
    # Get active session
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    # Role-specific completion checks
    if request.user.user_type == "swe_ng":
        if not (
            session.coding_q1_completed
            and session.coding_q2_completed
            and session.system_design_completed
        ):
            messages.warning(
                request, "Please complete all sections before viewing final analysis."
            )
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


# =============================================================================
# --- IN-FILE TEST CASES ---
# These classes are usually in 'tests.py', but included here per request.
# Run with: python manage.py test interviews.views
# =============================================================================

User = get_user_model()


class InterviewViewsTest(TestCase):
    """
    Test suite integrated directly into views.py.
    Uses 'dummy' (mock) objects to simulate Gemini/RAG responses.
    """

    def setUp(self):
        # Setup Users
        self.swe_user = User.objects.create_user(
            username="swe_user",
            password="password",
            user_type="swe_ng",
            has_resume=True,
        )
        self.swe_user.resume = SimpleUploadedFile(
            "resume.pdf", b"dummy content", content_type="application/pdf"
        )
        self.swe_user.save()

        self.pm_user = User.objects.create_user(
            username="pm_user", password="password", user_type="pm_ng", has_resume=True
        )

        # Setup Company
        self.company = Company.objects.create(name="TechCorp", slug="techcorp")
        self.client = Client()

    # --- Start Session Tests ---
    def test_start_session_view_get(self):
        self.client.force_login(self.swe_user)
        response = self.client.get(reverse("start_session"))
        self.assertEqual(response.status_code, 200)

    def test_start_session_success(self):
        self.client.force_login(self.swe_user)
        response = self.client.post(
            reverse("start_session"),
            {
                "company": "techcorp",
                "job_description": "A very long valid job description " * 5,
            },
        )
        self.assertRedirects(response, reverse("interview_analysis"))
        self.assertTrue(
            InterviewSession.objects.filter(
                user=self.swe_user, status="active"
            ).exists()
        )

    # --- Resume Analysis Tests (Dummy Gemini) ---
    @patch("interviews.views.GeminiAnalyzer")
    def test_resume_analysis_generation(self, MockAnalyzer):
        # DUMMY / MOCK RESPONSE
        mock_instance = MockAnalyzer.return_value
        mock_instance.extract_text_from_pdf.return_value = "Resume Text"
        mock_instance.analyze_resume_fit.return_value = {
            "fit_score": 85,
            "analysis": "Good fit",
            "suggestions": "None",
        }

        InterviewSession.objects.create(
            user=self.swe_user, company="techcorp", status="active"
        )
        self.client.force_login(self.swe_user)
        response = self.client.get(reverse("interview_analysis"))
        self.assertEqual(response.status_code, 200)

    # --- Coding Round Tests (Dummy RAG + Gemini) ---
    @patch("interviews.views.RAGService")
    @patch("interviews.views.GeminiAnalyzer")
    def test_coding_round_generation(self, MockAnalyzer, MockRAG):
        # DUMMY / MOCK RESPONSE
        MockRAG.return_value.retrieve_coding_question.return_value = "Doc content"
        MockAnalyzer.return_value.select_and_generate_questions.return_value = [
            {"question": "Two Sum", "solution": "Code"}
        ]

        session = InterviewSession.objects.create(
            user=self.swe_user, company="techcorp", status="active"
        )
        self.client.force_login(self.swe_user)
        response = self.client.get(reverse("coding_round"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            CodingRound.objects.filter(session=session, question_number=1).exists()
        )

    @patch("interviews.views.GeminiAnalyzer")
    def test_coding_round_submission(self, MockAnalyzer):
        session = InterviewSession.objects.create(
            user=self.swe_user, company="techcorp", status="active"
        )
        CodingRound.objects.create(
            session=session,
            question_number=1,
            generated_questions=[{"question": "Q1", "solution": "Sol"}],
            selected_question_index=0,
        )

        # DUMMY EVALUATION
        MockAnalyzer.return_value.evaluate_code.return_value = {
            "is_correct": True,
            "score": 95,
            "feedback": "Great",
        }

        self.client.force_login(self.swe_user)
        response = self.client.post(
            reverse("coding_round"),
            {"user_code": 'print("hello")', "language": "python"},
        )
        self.assertEqual(response.status_code, 200)

    # --- Product Sense Tests (PM) ---
    @patch("interviews.views.RAGService")
    @patch("interviews.views.GeminiAnalyzer")
    def test_product_sense_flow(self, MockAnalyzer, MockRAG):
        MockRAG.return_value.retrieve_product_sense_case.return_value = "Case Doc"
        MockAnalyzer.return_value.select_and_generate_product_sense_case.return_value = {
            "case": "Design X",
            "evaluation_criteria": "Metrics",
        }
        MockAnalyzer.return_value.evaluate_product_sense.return_value = {
            "is_good": True,
            "score": 90,
        }

        InterviewSession.objects.create(
            user=self.pm_user, company="techcorp", status="active"
        )
        self.client.force_login(self.pm_user)

        # Test Generate
        self.client.get(reverse("product_sense"))
        # Test Submit
        response = self.client.post(
            reverse("product_sense"), {"user_answer": "My Strategy"}
        )
        self.assertEqual(response.status_code, 200)
