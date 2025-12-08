from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404  # Added for raising 404 in async wrapper

# IMPORT FIX: We need this to safely run synchronous database calls in the ASGI environment
from channels.db import database_sync_to_async

from companies.models import Company
from .gemini_service import GeminiAnalyzer
from .models import InterviewSession


# ASYNC WRAPPER FIX: Create a wrapper function to safely run synchronous ORM logic
@database_sync_to_async
def get_session_or_404(user):
    """Safely fetch the active session using synchronous ORM."""
    session = InterviewSession.objects.filter(user=user, status="active").first()

    if not session:
        # Raise standard Django exception if session is not found
        raise Http404("No active InterviewSession matches the given query.")
    return session


# ASYNC WRAPPER FIX: Create a wrapper for get_companies_list too, as it uses the ORM
@database_sync_to_async
def get_companies_list():
    """Get list of companies from database formatted as (slug, name) tuples"""
    return [
        (company.slug, company.name)
        for company in Company.objects.all().order_by("name")
    ]


# The rest of the synchronous views will now use the wrapped get_companies_list
# IMPORTANT: These views are still synchronous and may need to be converted to async
# if you encounter the error in them later. For now, we only fix the one you are on.
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
            # Process the analysis
            return redirect("interview_analysis")

    # NOTE: get_companies_list() remains synchronous here, as it's being called
    # from a synchronous view. If this view also throws the error later, you
    # would need to change it to async def and await get_companies_list().

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
            # Fallback question if no content available
            document_text = "Write a function to find the longest substring without repeating characters in a given string."
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
        print("DEBUG: POST request received!")  # Debug
        user_code = request.POST.get("user_code", "").strip()
        language = request.POST.get("language", "python")
        print(
            f"DEBUG: user_code length: {len(user_code)}, language: {language}"
        )  # Debug

        if not user_code:
            messages.error(request, "Please write some code before submitting.")
            print("DEBUG: No code provided")  # Debug
        else:
            print("DEBUG: Starting evaluation...")  # Debug
            # Save user submission
            coding_round.user_code = user_code
            coding_round.language = language
            coding_round.save()

            # Evaluate the code
            selected_question = coding_round.get_selected_question()
            print(f"DEBUG: Selected question: {selected_question is not None}")  # Debug
            if selected_question:
                print("DEBUG: Calling Gemini API for evaluation...")  # Debug
                analyzer = GeminiAnalyzer()
                evaluation = analyzer.evaluate_code(
                    question=selected_question.get("question", ""),
                    reference_solution=selected_question.get("solution", ""),
                    user_code=user_code,
                    language=language,
                )
                print(f"DEBUG: Evaluation result: {evaluation}")  # Debug

                # Save evaluation
                coding_round.evaluation_result = evaluation
                coding_round.save()

                # Mark coding Q1 as completed
                session.coding_q1_completed = True
                session.save()

                # Show feedback message
                if evaluation.get("is_correct"):
                    messages.success(
                        request,
                        f"Great job! Your solution is correct. Score: {evaluation.get('score')}/100",
                    )
                else:
                    messages.info(
                        request,
                        f"Your solution needs improvement. Score: {evaluation.get('score')}/100",
                    )
            else:
                print("DEBUG: No selected question found!")  # Debug
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
    GET: Display case or generate if not exists
    POST: Evaluate submitted answer
    """
    from .models import ProductSenseRound
    from .rag_service import RAGService

    # Get active session
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    # Ensure user is PM type
    if request.user.user_type != "pm_ng":
        messages.error(request, "This step is only available for Product Manager role.")
        return redirect("interview_analysis")

    # Get or create product sense round
    product_sense_round, created = ProductSenseRound.objects.get_or_create(
        session=session
    )

    # If newly created or no case generated yet, generate it
    if created or not product_sense_round.generated_case:
        rag_service = RAGService()

        # Retrieve one random product sense document for this company
        document_text = rag_service.retrieve_product_sense_case(session.company)

        if not document_text:
            # Fallback case if no content available
            document_text = "You are the PM for a social media app. You notice that user engagement has dropped by 15% over the last quarter. Design a feature or strategy to improve user engagement. Consider user needs, metrics, prioritization, and potential trade-offs."
            messages.warning(
                request,
                "Using fallback case. Please ensure company documents are uploaded.",
            )

        # Let Gemini select best case and generate a similar one
        analyzer = GeminiAnalyzer()
        generated_case = analyzer.select_and_generate_product_sense_case(
            document_text=document_text, company_name=session.get_company_display()
        )

        # Save to product sense round
        product_sense_round.base_case = "Generated from company-specific document"
        product_sense_round.generated_case = generated_case
        product_sense_round.save()

        messages.success(request, "Product sense case generated successfully!")

    # Handle POST: answer submission and evaluation
    if request.method == "POST":
        user_answer = request.POST.get("user_answer", "").strip()

        if not user_answer:
            messages.error(request, "Please write your answer before submitting.")
        else:
            # Save user submission
            product_sense_round.user_answer = user_answer
            product_sense_round.save()

            # Evaluate the answer
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

                # Save evaluation
                product_sense_round.evaluation_result = evaluation
                product_sense_round.save()

                # Mark product sense as completed
                session.product_sense_completed = True
                session.save()

                # Show feedback message
                if evaluation.get("is_good"):
                    messages.success(
                        request,
                        f"Excellent answer! Score: {evaluation.get('score')}/100",
                    )
                else:
                    messages.info(
                        request,
                        f"Your answer needs improvement. Score: {evaluation.get('score')}/100",
                    )
            else:
                messages.error(request, "Could not evaluate: case not found.")

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
    GET: Display question or generate if not exists
    POST: Evaluate submitted answer
    """
    from .models import AnalyticalStrategyRound
    from .rag_service import RAGService

    # Get active session
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    # Ensure user is PM type
    if request.user.user_type != "pm_ng":
        messages.error(request, "This step is only available for Product Manager role.")
        return redirect("interview_analysis")

    # Get or create analytical strategy round
    analytical_strategy_round, created = AnalyticalStrategyRound.objects.get_or_create(
        session=session
    )

    # If newly created or no question generated yet, generate it
    if created or not analytical_strategy_round.generated_question:
        rag_service = RAGService()

        # Retrieve one random analytical/strategy document for this company
        document_text = rag_service.retrieve_analytical_strategy_prompt(session.company)

        if not document_text:
            # Fallback question if no content available
            document_text = "Your product's DAU/MAU ratio has been declining over the past 3 months. Design an experiment to identify the root cause and propose a data-driven solution. Include your hypothesis, success metrics, experiment design, and decision framework."
            messages.warning(
                request,
                "Using fallback question. Please ensure company documents are uploaded.",
            )

        # Let Gemini select best question and generate a similar one
        analyzer = GeminiAnalyzer()
        generated_question = analyzer.select_and_generate_analytical_strategy_question(
            document_text=document_text, company_name=session.get_company_display()
        )

        # Save to analytical strategy round
        analytical_strategy_round.base_question = (
            "Generated from company-specific document"
        )
        analytical_strategy_round.generated_question = generated_question
        analytical_strategy_round.save()

        messages.success(
            request, "Analytical/strategy question generated successfully!"
        )

    # Handle POST: answer submission and evaluation
    if request.method == "POST":
        user_answer = request.POST.get("user_answer", "").strip()

        if not user_answer:
            messages.error(request, "Please write your answer before submitting.")
        else:
            # Save user submission
            analytical_strategy_round.user_answer = user_answer
            analytical_strategy_round.save()

            # Evaluate the answer
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

                # Save evaluation
                analytical_strategy_round.evaluation_result = evaluation
                analytical_strategy_round.save()

                # Mark analytical strategy as completed
                session.analytical_strategy_completed = True
                session.save()

                # Show feedback message
                if evaluation.get("is_good"):
                    messages.success(
                        request,
                        f"Excellent answer! Score: {evaluation.get('score')}/100",
                    )
                else:
                    messages.info(
                        request,
                        f"Your answer needs improvement. Score: {evaluation.get('score')}/100",
                    )
            else:
                messages.error(request, "Could not evaluate: question not found.")

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

    # Get or create coding round for question 2
    coding_round, created = CodingRound.objects.get_or_create(
        session=session, question_number=2
    )

    # If newly created or no questions generated yet, generate them
    if created or not coding_round.generated_questions:
        rag_service = RAGService()

        # Retrieve one random coding document for this company
        document_text = rag_service.retrieve_coding_question(session.company)

        if not document_text:
            # Fallback question if no content available
            document_text = "Write a function to implement a least recently used (LRU) cache with get and put operations."
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

        messages.success(request, "Coding question 2 generated successfully!")

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

                # Mark coding Q2 as completed
                session.coding_q2_completed = True
                session.save()

                # Show feedback message
                if evaluation.get("is_correct"):
                    messages.success(
                        request,
                        f"Great job! Your solution is correct. Score: {evaluation.get('score')}/100",
                    )
                else:
                    messages.info(
                        request,
                        f"Your solution needs improvement. Score: {evaluation.get('score')}/100",
                    )
            else:
                messages.error(request, "Could not evaluate: question not found.")

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
    GET: Display question or generate if not exists
    POST: Evaluate submitted design answer
    """
    from .models import SystemDesignRound
    from .rag_service import RAGService

    # Get active session
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    # Ensure user is SWE type
    if request.user.user_type != "swe_ng":
        messages.error(
            request, "This step is only available for Software Engineer role."
        )
        return redirect("interview_analysis")

    # Get or create system design round
    system_design_round, created = SystemDesignRound.objects.get_or_create(
        session=session
    )

    # If newly created or no question generated yet, generate it
    if created or not system_design_round.generated_question:
        rag_service = RAGService()

        # Retrieve one random system design document for this company
        document_text = rag_service.retrieve_system_design_question(session.company)

        if not document_text:
            # Fallback question if no content available
            document_text = "Design a URL shortening service like bit.ly. The system should support creating short URLs, redirecting to original URLs, and tracking click analytics."
            messages.warning(
                request,
                "Using fallback question. Please ensure company documents are uploaded.",
            )

        # Let Gemini select best question and generate a similar one
        analyzer = GeminiAnalyzer()
        generated_question = analyzer.select_and_generate_system_design_question(
            document_text=document_text, company_name=session.get_company_display()
        )

        # Save to system design round
        system_design_round.base_question = "Generated from company-specific document"
        system_design_round.generated_question = generated_question
        system_design_round.save()

        messages.success(request, "System design question generated successfully!")

    # Handle POST: design answer submission and evaluation
    if request.method == "POST":
        user_answer = request.POST.get("user_answer", "").strip()
        design_image = request.FILES.get("design_image", None)

        if not user_answer:
            messages.error(
                request, "Please write your design answer before submitting."
            )
        else:
            # Save user submission
            system_design_round.user_answer = user_answer

            # Handle image upload if provided
            if design_image:
                # Delete old image if exists
                if system_design_round.design_image:
                    system_design_round.design_image.delete(save=False)
                system_design_round.design_image = design_image

            system_design_round.save()

            # Evaluate the design
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

                # Save evaluation
                system_design_round.evaluation_result = evaluation
                system_design_round.save()

                # Mark system design as completed
                session.system_design_completed = True
                session.save()

                # Show feedback message
                if evaluation.get("is_correct"):
                    messages.success(
                        request,
                        f"Excellent design! Score: {evaluation.get('score')}/100",
                    )
                else:
                    messages.info(
                        request,
                        f"Your design needs improvement. Score: {evaluation.get('score')}/100",
                    )
            else:
                messages.error(request, "Could not evaluate: question not found.")

    return render(
        request,
        "interviews/step_system_design.html",
        {
            "session": session,
            "system_design_round": system_design_round,
            "question": system_design_round.get_question(),
        },
    )


# THE FIX IS HERE: Change 'def' to 'async def' and use 'await'
# interviews/views.py (Snippet around line 824)
from asgiref.sync import sync_to_async # <-- Add this import

# Note: Your view function is already async (which is why the error occurs)
# interviews/views.py
# ... (other imports should remain) ...

@login_required
async def behavioral_resume_live_view(request):
    """
    View for behavioral + resume live interview.
    Audio-to-audio interview using Gemini Live API.
    """
    # FIX: Use the helper function directly (it handles status='active' correctly)
    try:
        session = await get_session_or_404(request.user)
    except Http404:
        messages.error(request, "No active interview session found.")
        return redirect("start_session")

    # Check if already completed
    if session.behavioral_resume_completed:
        messages.info(
            request, "Behavioral interview already completed. View your summary below."
        )

    # FIX: Fetch company name safely in async
    get_company_name_async = database_sync_to_async(session.get_company_display)
    company_name = await get_company_name_async()

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
    from .models import CodingRound, SystemDesignRound

    # Get active session
    session = get_object_or_404(InterviewSession, user=request.user, status="active")

    # Role-specific completion checks
    if request.user.user_type == "swe_ng":
        # Check if all SWE sections are completed
        if not (
            session.coding_q1_completed
            and session.coding_q2_completed
            and session.system_design_completed
        ):
            messages.warning(
                request, "Please complete all sections before viewing final analysis."
            )

            # Redirect to the next incomplete section
            if not session.coding_q1_completed:
                return redirect("coding_round")
            elif not session.coding_q2_completed:
                return redirect("coding_round_q2")
            elif not session.system_design_completed:
                return redirect("system_design")

        # Get all rounds for SWE
        coding_q1 = CodingRound.objects.filter(
            session=session, question_number=1
        ).first()
        coding_q2 = CodingRound.objects.filter(
            session=session, question_number=2
        ).first()
        system_design = SystemDesignRound.objects.filter(session=session).first()

        # If final analysis doesn't exist yet, generate it
        if not session.final_analysis or not session.overall_readiness_score:
            # Prepare session data for analysis
            session_data = {
                "company": session.get_company_display(),
                "resume_score": session.resume_fit_score or 0,
                "resume_analysis": session.resume_analysis or "N/A",
                "coding_q1_score": (
                    coding_q1.evaluation_result.get("score", 0)
                    if coding_q1 and coding_q1.evaluation_result
                    else 0
                ),
                "coding_q1_correct": (
                    "Yes"
                    if coding_q1
                    and coding_q1.evaluation_result
                    and coding_q1.evaluation_result.get("is_correct")
                    else "No"
                ),
                "coding_q2_score": (
                    coding_q2.evaluation_result.get("score", 0)
                    if coding_q2 and coding_q2.evaluation_result
                    else 0
                ),
                "coding_q2_correct": (
                    "Yes"
                    if coding_q2
                    and coding_q2.evaluation_result
                    and coding_q2.evaluation_result.get("is_correct")
                    else "No"
                ),
                "system_design_score": (
                    system_design.evaluation_result.get("score", 0)
                    if system_design and system_design.evaluation_result
                    else 0
                ),
                "system_design_quality": (
                    "Good"
                    if system_design
                    and system_design.evaluation_result
                    and system_design.evaluation_result.get("is_correct")
                    else "Needs Work"
                ),
                "behavioral_resume_summary": session.behavioral_resume_summary
                or "Not completed",
                "behavioral_resume_completed": session.behavioral_resume_completed,
            }

            # Generate comprehensive analysis
            analyzer = GeminiAnalyzer()
            final_result = analyzer.generate_final_analysis(session_data)

            # Save to session
            session.overall_readiness_score = final_result["overall_score"]
            session.final_analysis = final_result["analysis"]
            session.save()

            messages.success(request, "Final analysis generated successfully!")

        # Prepare context data
        context = {
            "session": session,
            "coding_q1": coding_q1,
            "coding_q2": coding_q2,
            "system_design": system_design,
        }

    elif request.user.user_type == "pm_ng":
        # Check if required PM sections are completed (behavioral is optional)
        from .models import AnalyticalStrategyRound, ProductSenseRound

        if not (
            session.product_sense_completed and session.analytical_strategy_completed
        ):
            messages.warning(
                request,
                "Please complete Product Sense and Analytical + Strategy sections before viewing final analysis.",
            )

            # Redirect to the next incomplete section
            if not session.product_sense_completed:
                return redirect("product_sense")
            elif not session.analytical_strategy_completed:
                return redirect("analytical_strategy")

        # Get all rounds for PM
        product_sense = ProductSenseRound.objects.filter(session=session).first()
        analytical_strategy = AnalyticalStrategyRound.objects.filter(
            session=session
        ).first()

        # If final analysis doesn't exist yet, generate it
        if not session.final_analysis or not session.overall_readiness_score:
            # Prepare session data for PM analysis
            session_data = {
                "company": session.get_company_display(),
                "role": "Product Manager",
                "resume_score": session.resume_fit_score or 0,
                "resume_analysis": session.resume_analysis or "N/A",
                "product_sense_score": (
                    product_sense.evaluation_result.get("score", 0)
                    if product_sense and product_sense.evaluation_result
                    else 0
                ),
                "product_sense_quality": (
                    "Good"
                    if product_sense
                    and product_sense.evaluation_result
                    and product_sense.evaluation_result.get("is_good")
                    else "Needs Work"
                ),
                "analytical_strategy_score": (
                    analytical_strategy.evaluation_result.get("score", 0)
                    if analytical_strategy and analytical_strategy.evaluation_result
                    else 0
                ),
                "analytical_strategy_quality": (
                    "Good"
                    if analytical_strategy
                    and analytical_strategy.evaluation_result
                    and analytical_strategy.evaluation_result.get("is_good")
                    else "Needs Work"
                ),
                "behavioral_resume_summary": session.behavioral_resume_summary
                or "Not completed",
            }

            # Calculate overall score as simple average of numeric scores
            scores = [
                session_data["resume_score"],
                session_data["product_sense_score"],
                session_data["analytical_strategy_score"],
            ]
            overall_score = sum(scores) // len(scores) if scores else 0

            # Generate comprehensive PM analysis
            analyzer = GeminiAnalyzer()
            final_result = analyzer.generate_final_analysis_pm(session_data)

            # Save to session
            session.overall_readiness_score = final_result.get(
                "overall_score", overall_score
            )
            session.final_analysis = final_result["analysis"]
            session.save()

            messages.success(request, "Final analysis generated successfully!")

        # Prepare context data
        context = {
            "session": session,
            "product_sense": product_sense,
            "analytical_strategy": analytical_strategy,
            "coding_q1": None,
            "coding_q2": None,
            "system_design": None,
        }

    else:
        messages.error(request, "Invalid user type.")
        return redirect("dashboard")

    return render(request, "interviews/step_final_analysis.html", context)


# ########################
# from django.contrib import messages
# from django.contrib.auth.decorators import login_required
# from django.db import IntegrityError
# from django.shortcuts import get_object_or_404, redirect, render

# from companies.models import Company
# from .gemini_service import GeminiAnalyzer
# from .models import InterviewSession


# def get_companies_list():
#     """Get list of companies from database formatted as (slug, name) tuples"""
#     return [
#         (company.slug, company.name)
#         for company in Company.objects.all().order_by("name")
#     ]


# @login_required
# def start_session_view(request):
#     """
#     View to start a new interview session or continue existing one.
#     Displays form with company dropdown and job description textarea.
#     """
#     # Check if user already has an active session
#     active_session = InterviewSession.objects.filter(
#         user=request.user, status="active"
#     ).first()

#     if active_session:
#         # If session has analysis, show it; otherwise, process it
#         if active_session.has_analysis():
#             return redirect("interview_analysis")
#         else:
#             # Process the analysis
#             return redirect("interview_analysis")

#     if request.method == "POST":
#         company = request.POST.get("company")
#         job_description = request.POST.get("job_description", "").strip()

#         # Get companies list for template
#         companies_list = get_companies_list()

#         # Validation - check if company slug exists in database
#         valid_company_slugs = [slug for slug, _ in companies_list]
#         if not company or company not in valid_company_slugs:
#             messages.error(request, "Please select a valid company.")
#             return render(
#                 request,
#                 "interviews/start_session.html",
#                 {
#                     "companies": companies_list,
#                     "job_description": job_description,
#                 },
#             )

#         if not job_description:
#             messages.error(request, "Please enter a job description.")
#             return render(
#                 request,
#                 "interviews/start_session.html",
#                 {
#                     "companies": companies_list,
#                     "selected_company": company,
#                 },
#             )

#         if len(job_description) < 50:
#             messages.error(
#                 request, "Job description must be at least 50 characters long."
#             )
#             return render(
#                 request,
#                 "interviews/start_session.html",
#                 {
#                     "companies": companies_list,
#                     "selected_company": company,
#                     "job_description": job_description,
#                 },
#             )

#         # Check if user has uploaded a resume
#         if not request.user.has_resume:
#             messages.error(
#                 request,
#                 "Please upload your resume before starting an interview session.",
#             )
#             return redirect("profile")

#         try:
#             # Create new session
#             session = InterviewSession.objects.create(
#                 user=request.user,
#                 company=company,
#                 job_description=job_description,
#                 status="active",
#             )

#             messages.success(
#                 request,
#                 f"Interview session started for {session.get_company_display()}!",
#             )
#             return redirect("interview_analysis")

#         except IntegrityError:
#             messages.error(
#                 request,
#                 "You already have an active session. Please end it before starting a new one.",
#             )
#             return redirect("dashboard")

#     return render(
#         request,
#         "interviews/start_session.html",
#         {"companies": get_companies_list()},
#     )


# @login_required
# def resume_analysis_view(request):
#     """
#     View to display or generate resume analysis results.
#     Calls Gemini API to analyze resume fit with job description.
#     """
#     # Get active session
#     session = get_object_or_404(InterviewSession, user=request.user, status="active")

#     # If analysis doesn't exist yet, generate it
#     if not session.has_analysis():
#         # Initialize Gemini analyzer
#         analyzer = GeminiAnalyzer()

#         # Extract resume text
#         try:
#             resume_text = analyzer.extract_text_from_pdf(request.user.resume)
#         except Exception as e:
#             messages.error(request, f"Error reading resume: {str(e)}")
#             resume_text = "Resume text could not be extracted."

#         # Analyze resume fit
#         analysis_result = analyzer.analyze_resume_fit(
#             resume_text=resume_text,
#             job_description=session.job_description,
#             company_name=session.get_company_display(),
#         )

#         # Save results to session
#         session.resume_fit_score = analysis_result["fit_score"]
#         session.resume_analysis = analysis_result["analysis"]
#         session.resume_suggestions = analysis_result["suggestions"]
#         session.save()

#         messages.success(request, "Resume analysis completed!")

#     return render(request, "interviews/analysis.html", {"session": session})


# @login_required
# def end_session_view(request):
#     """
#     View to end the current active interview session.
#     """
#     if request.method == "POST":
#         # Get active session
#         session = InterviewSession.objects.filter(
#             user=request.user, status="active"
#         ).first()

#         if session:
#             session.status = "completed"
#             session.save()
#             messages.success(request, "Interview session ended successfully.")
#         else:
#             messages.info(request, "No active session found.")

#         return redirect("dashboard")

#     # If GET request, show confirmation page
#     session = get_object_or_404(InterviewSession, user=request.user, status="active")

#     return render(request, "interviews/end_session_confirm.html", {"session": session})


# @login_required
# def coding_round_view(request):
#     """
#     Coding round view with RAG-powered question generation and evaluation.
#     GET: Display question or generate if not exists
#     POST: Evaluate submitted code
#     """
#     from .models import CodingRound
#     from .rag_service import RAGService

#     # Get active session
#     session = get_object_or_404(InterviewSession, user=request.user, status="active")

#     # Ensure user is SWE type
#     if request.user.user_type != "swe_ng":
#         messages.error(
#             request, "This step is only available for Software Engineer role."
#         )
#         return redirect("interview_analysis")

#     # Get or create coding round for question 1
#     coding_round, created = CodingRound.objects.get_or_create(
#         session=session, question_number=1
#     )

#     # If newly created or no questions generated yet, generate them
#     if created or not coding_round.generated_questions:
#         rag_service = RAGService()

#         # Retrieve one random coding document for this company
#         document_text = rag_service.retrieve_coding_question(session.company)

#         if not document_text:
#             # Fallback question if no content available
#             document_text = "Write a function to find the longest substring without repeating characters in a given string."
#             messages.warning(
#                 request,
#                 "Using fallback question. Please ensure company documents are uploaded.",
#             )

#         # Let Gemini select best question and generate similar ones
#         analyzer = GeminiAnalyzer()
#         generated_questions = analyzer.select_and_generate_questions(
#             document_text=document_text,
#             company_name=session.get_company_display(),
#             num_questions=2,
#         )

#         # Save to coding round
#         coding_round.base_question = "Generated from company-specific document"
#         coding_round.generated_questions = generated_questions
#         coding_round.selected_question_index = 0  # Show first question
#         coding_round.save()

#         messages.success(request, "Coding questions generated successfully!")

#     # Handle POST: code submission and evaluation
#     if request.method == "POST":
#         print("DEBUG: POST request received!")  # Debug
#         user_code = request.POST.get("user_code", "").strip()
#         language = request.POST.get("language", "python")
#         print(
#             f"DEBUG: user_code length: {len(user_code)}, language: {language}"
#         )  # Debug

#         if not user_code:
#             messages.error(request, "Please write some code before submitting.")
#             print("DEBUG: No code provided")  # Debug
#         else:
#             print("DEBUG: Starting evaluation...")  # Debug
#             # Save user submission
#             coding_round.user_code = user_code
#             coding_round.language = language
#             coding_round.save()

#             # Evaluate the code
#             selected_question = coding_round.get_selected_question()
#             print(f"DEBUG: Selected question: {selected_question is not None}")  # Debug
#             if selected_question:
#                 print("DEBUG: Calling Gemini API for evaluation...")  # Debug
#                 analyzer = GeminiAnalyzer()
#                 evaluation = analyzer.evaluate_code(
#                     question=selected_question.get("question", ""),
#                     reference_solution=selected_question.get("solution", ""),
#                     user_code=user_code,
#                     language=language,
#                 )
#                 print(f"DEBUG: Evaluation result: {evaluation}")  # Debug

#                 # Save evaluation
#                 coding_round.evaluation_result = evaluation
#                 coding_round.save()

#                 # Mark coding Q1 as completed
#                 session.coding_q1_completed = True
#                 session.save()

#                 # Show feedback message
#                 if evaluation.get("is_correct"):
#                     messages.success(
#                         request,
#                         f"Great job! Your solution is correct. Score: {evaluation.get('score')}/100",
#                     )
#                 else:
#                     messages.info(
#                         request,
#                         f"Your solution needs improvement. Score: {evaluation.get('score')}/100",
#                     )
#             else:
#                 print("DEBUG: No selected question found!")  # Debug
#                 messages.error(request, "Could not evaluate: question not found.")

#     return render(
#         request,
#         "interviews/step_coding_round.html",
#         {
#             "session": session,
#             "coding_round": coding_round,
#             "selected_question": coding_round.get_selected_question(),
#         },
#     )


# @login_required
# def product_sense_view(request):
#     """
#     Product Sense view with RAG-powered case generation and evaluation.
#     GET: Display case or generate if not exists
#     POST: Evaluate submitted answer
#     """
#     from .models import ProductSenseRound
#     from .rag_service import RAGService

#     # Get active session
#     session = get_object_or_404(InterviewSession, user=request.user, status="active")

#     # Ensure user is PM type
#     if request.user.user_type != "pm_ng":
#         messages.error(request, "This step is only available for Product Manager role.")
#         return redirect("interview_analysis")

#     # Get or create product sense round
#     product_sense_round, created = ProductSenseRound.objects.get_or_create(
#         session=session
#     )

#     # If newly created or no case generated yet, generate it
#     if created or not product_sense_round.generated_case:
#         rag_service = RAGService()

#         # Retrieve one random product sense document for this company
#         document_text = rag_service.retrieve_product_sense_case(session.company)

#         if not document_text:
#             # Fallback case if no content available
#             document_text = "You are the PM for a social media app. You notice that user engagement has dropped by 15% over the last quarter. Design a feature or strategy to improve user engagement. Consider user needs, metrics, prioritization, and potential trade-offs."
#             messages.warning(
#                 request,
#                 "Using fallback case. Please ensure company documents are uploaded.",
#             )

#         # Let Gemini select best case and generate a similar one
#         analyzer = GeminiAnalyzer()
#         generated_case = analyzer.select_and_generate_product_sense_case(
#             document_text=document_text, company_name=session.get_company_display()
#         )

#         # Save to product sense round
#         product_sense_round.base_case = "Generated from company-specific document"
#         product_sense_round.generated_case = generated_case
#         product_sense_round.save()

#         messages.success(request, "Product sense case generated successfully!")

#     # Handle POST: answer submission and evaluation
#     if request.method == "POST":
#         user_answer = request.POST.get("user_answer", "").strip()

#         if not user_answer:
#             messages.error(request, "Please write your answer before submitting.")
#         else:
#             # Save user submission
#             product_sense_round.user_answer = user_answer
#             product_sense_round.save()

#             # Evaluate the answer
#             case = product_sense_round.get_case()
#             evaluation_criteria = (
#                 product_sense_round.generated_case.get("evaluation_criteria")
#                 if product_sense_round.generated_case
#                 else None
#             )

#             if case:
#                 analyzer = GeminiAnalyzer()
#                 evaluation = analyzer.evaluate_product_sense(
#                     case=case,
#                     user_answer=user_answer,
#                     evaluation_criteria=evaluation_criteria,
#                 )

#                 # Save evaluation
#                 product_sense_round.evaluation_result = evaluation
#                 product_sense_round.save()

#                 # Mark product sense as completed
#                 session.product_sense_completed = True
#                 session.save()

#                 # Show feedback message
#                 if evaluation.get("is_good"):
#                     messages.success(
#                         request,
#                         f"Excellent answer! Score: {evaluation.get('score')}/100",
#                     )
#                 else:
#                     messages.info(
#                         request,
#                         f"Your answer needs improvement. Score: {evaluation.get('score')}/100",
#                     )
#             else:
#                 messages.error(request, "Could not evaluate: case not found.")

#     return render(
#         request,
#         "interviews/step_product_sense.html",
#         {
#             "session": session,
#             "product_sense_round": product_sense_round,
#             "case": product_sense_round.get_case(),
#         },
#     )


# @login_required
# def analytical_strategy_view(request):
#     """
#     Analytical + Strategy view with RAG-powered question generation and evaluation.
#     GET: Display question or generate if not exists
#     POST: Evaluate submitted answer
#     """
#     from .models import AnalyticalStrategyRound
#     from .rag_service import RAGService

#     # Get active session
#     session = get_object_or_404(InterviewSession, user=request.user, status="active")

#     # Ensure user is PM type
#     if request.user.user_type != "pm_ng":
#         messages.error(request, "This step is only available for Product Manager role.")
#         return redirect("interview_analysis")

#     # Get or create analytical strategy round
#     analytical_strategy_round, created = AnalyticalStrategyRound.objects.get_or_create(
#         session=session
#     )

#     # If newly created or no question generated yet, generate it
#     if created or not analytical_strategy_round.generated_question:
#         rag_service = RAGService()

#         # Retrieve one random analytical/strategy document for this company
#         document_text = rag_service.retrieve_analytical_strategy_prompt(session.company)

#         if not document_text:
#             # Fallback question if no content available
#             document_text = "Your product's DAU/MAU ratio has been declining over the past 3 months. Design an experiment to identify the root cause and propose a data-driven solution. Include your hypothesis, success metrics, experiment design, and decision framework."
#             messages.warning(
#                 request,
#                 "Using fallback question. Please ensure company documents are uploaded.",
#             )

#         # Let Gemini select best question and generate a similar one
#         analyzer = GeminiAnalyzer()
#         generated_question = analyzer.select_and_generate_analytical_strategy_question(
#             document_text=document_text, company_name=session.get_company_display()
#         )

#         # Save to analytical strategy round
#         analytical_strategy_round.base_question = (
#             "Generated from company-specific document"
#         )
#         analytical_strategy_round.generated_question = generated_question
#         analytical_strategy_round.save()

#         messages.success(
#             request, "Analytical/strategy question generated successfully!"
#         )

#     # Handle POST: answer submission and evaluation
#     if request.method == "POST":
#         user_answer = request.POST.get("user_answer", "").strip()

#         if not user_answer:
#             messages.error(request, "Please write your answer before submitting.")
#         else:
#             # Save user submission
#             analytical_strategy_round.user_answer = user_answer
#             analytical_strategy_round.save()

#             # Evaluate the answer
#             question = analytical_strategy_round.get_question()
#             evaluation_criteria = (
#                 analytical_strategy_round.generated_question.get("evaluation_criteria")
#                 if analytical_strategy_round.generated_question
#                 else None
#             )

#             if question:
#                 analyzer = GeminiAnalyzer()
#                 evaluation = analyzer.evaluate_analytical_strategy(
#                     question=question,
#                     user_answer=user_answer,
#                     evaluation_criteria=evaluation_criteria,
#                 )

#                 # Save evaluation
#                 analytical_strategy_round.evaluation_result = evaluation
#                 analytical_strategy_round.save()

#                 # Mark analytical strategy as completed
#                 session.analytical_strategy_completed = True
#                 session.save()

#                 # Show feedback message
#                 if evaluation.get("is_good"):
#                     messages.success(
#                         request,
#                         f"Excellent answer! Score: {evaluation.get('score')}/100",
#                     )
#                 else:
#                     messages.info(
#                         request,
#                         f"Your answer needs improvement. Score: {evaluation.get('score')}/100",
#                     )
#             else:
#                 messages.error(request, "Could not evaluate: question not found.")

#     return render(
#         request,
#         "interviews/step_analytical_strategy.html",
#         {
#             "session": session,
#             "analytical_strategy_round": analytical_strategy_round,
#             "question": analytical_strategy_round.get_question(),
#         },
#     )


# @login_required
# def coding_round_q2_view(request):
#     """
#     Coding round Q2 view with RAG-powered question generation and evaluation.
#     GET: Display question or generate if not exists
#     POST: Evaluate submitted code
#     """
#     from .models import CodingRound
#     from .rag_service import RAGService

#     # Get active session
#     session = get_object_or_404(InterviewSession, user=request.user, status="active")

#     # Ensure user is SWE type
#     if request.user.user_type != "swe_ng":
#         messages.error(
#             request, "This step is only available for Software Engineer role."
#         )
#         return redirect("interview_analysis")

#     # Get or create coding round for question 2
#     coding_round, created = CodingRound.objects.get_or_create(
#         session=session, question_number=2
#     )

#     # If newly created or no questions generated yet, generate them
#     if created or not coding_round.generated_questions:
#         rag_service = RAGService()

#         # Retrieve one random coding document for this company
#         document_text = rag_service.retrieve_coding_question(session.company)

#         if not document_text:
#             # Fallback question if no content available
#             document_text = "Write a function to implement a least recently used (LRU) cache with get and put operations."
#             messages.warning(
#                 request,
#                 "Using fallback question. Please ensure company documents are uploaded.",
#             )

#         # Let Gemini select best question and generate similar ones
#         analyzer = GeminiAnalyzer()
#         generated_questions = analyzer.select_and_generate_questions(
#             document_text=document_text,
#             company_name=session.get_company_display(),
#             num_questions=2,
#         )

#         # Save to coding round
#         coding_round.base_question = "Generated from company-specific document"
#         coding_round.generated_questions = generated_questions
#         coding_round.selected_question_index = 0  # Show first question
#         coding_round.save()

#         messages.success(request, "Coding question 2 generated successfully!")

#     # Handle POST: code submission and evaluation
#     if request.method == "POST":
#         user_code = request.POST.get("user_code", "").strip()
#         language = request.POST.get("language", "python")

#         if not user_code:
#             messages.error(request, "Please write some code before submitting.")
#         else:
#             # Save user submission
#             coding_round.user_code = user_code
#             coding_round.language = language
#             coding_round.save()

#             # Evaluate the code
#             selected_question = coding_round.get_selected_question()
#             if selected_question:
#                 analyzer = GeminiAnalyzer()
#                 evaluation = analyzer.evaluate_code(
#                     question=selected_question.get("question", ""),
#                     reference_solution=selected_question.get("solution", ""),
#                     user_code=user_code,
#                     language=language,
#                 )

#                 # Save evaluation
#                 coding_round.evaluation_result = evaluation
#                 coding_round.save()

#                 # Mark coding Q2 as completed
#                 session.coding_q2_completed = True
#                 session.save()

#                 # Show feedback message
#                 if evaluation.get("is_correct"):
#                     messages.success(
#                         request,
#                         f"Great job! Your solution is correct. Score: {evaluation.get('score')}/100",
#                     )
#                 else:
#                     messages.info(
#                         request,
#                         f"Your solution needs improvement. Score: {evaluation.get('score')}/100",
#                     )
#             else:
#                 messages.error(request, "Could not evaluate: question not found.")

#     return render(
#         request,
#         "interviews/step_coding_round_2.html",
#         {
#             "session": session,
#             "coding_round": coding_round,
#             "selected_question": coding_round.get_selected_question(),
#         },
#     )


# @login_required
# def system_design_view(request):
#     """
#     System Design view with RAG-powered question generation and evaluation.
#     GET: Display question or generate if not exists
#     POST: Evaluate submitted design answer
#     """
#     from .models import SystemDesignRound
#     from .rag_service import RAGService

#     # Get active session
#     session = get_object_or_404(InterviewSession, user=request.user, status="active")

#     # Ensure user is SWE type
#     if request.user.user_type != "swe_ng":
#         messages.error(
#             request, "This step is only available for Software Engineer role."
#         )
#         return redirect("interview_analysis")

#     # Get or create system design round
#     system_design_round, created = SystemDesignRound.objects.get_or_create(
#         session=session
#     )

#     # If newly created or no question generated yet, generate it
#     if created or not system_design_round.generated_question:
#         rag_service = RAGService()

#         # Retrieve one random system design document for this company
#         document_text = rag_service.retrieve_system_design_question(session.company)

#         if not document_text:
#             # Fallback question if no content available
#             document_text = "Design a URL shortening service like bit.ly. The system should support creating short URLs, redirecting to original URLs, and tracking click analytics."
#             messages.warning(
#                 request,
#                 "Using fallback question. Please ensure company documents are uploaded.",
#             )

#         # Let Gemini select best question and generate a similar one
#         analyzer = GeminiAnalyzer()
#         generated_question = analyzer.select_and_generate_system_design_question(
#             document_text=document_text, company_name=session.get_company_display()
#         )

#         # Save to system design round
#         system_design_round.base_question = "Generated from company-specific document"
#         system_design_round.generated_question = generated_question
#         system_design_round.save()

#         messages.success(request, "System design question generated successfully!")

#     # Handle POST: design answer submission and evaluation
#     if request.method == "POST":
#         user_answer = request.POST.get("user_answer", "").strip()
#         design_image = request.FILES.get("design_image", None)

#         if not user_answer:
#             messages.error(
#                 request, "Please write your design answer before submitting."
#             )
#         else:
#             # Save user submission
#             system_design_round.user_answer = user_answer

#             # Handle image upload if provided
#             if design_image:
#                 # Delete old image if exists
#                 if system_design_round.design_image:
#                     system_design_round.design_image.delete(save=False)
#                 system_design_round.design_image = design_image

#             system_design_round.save()

#             # Evaluate the design
#             question = system_design_round.get_question()
#             evaluation_criteria = (
#                 system_design_round.generated_question.get("evaluation_criteria")
#                 if system_design_round.generated_question
#                 else None
#             )

#             if question:
#                 analyzer = GeminiAnalyzer()
#                 evaluation = analyzer.evaluate_system_design(
#                     question=question,
#                     user_answer=user_answer,
#                     evaluation_criteria=evaluation_criteria,
#                     design_image=(
#                         system_design_round.design_image
#                         if system_design_round.design_image
#                         else None
#                     ),
#                 )

#                 # Save evaluation
#                 system_design_round.evaluation_result = evaluation
#                 system_design_round.save()

#                 # Mark system design as completed
#                 session.system_design_completed = True
#                 session.save()

#                 # Show feedback message
#                 if evaluation.get("is_correct"):
#                     messages.success(
#                         request,
#                         f"Excellent design! Score: {evaluation.get('score')}/100",
#                     )
#                 else:
#                     messages.info(
#                         request,
#                         f"Your design needs improvement. Score: {evaluation.get('score')}/100",
#                     )
#             else:
#                 messages.error(request, "Could not evaluate: question not found.")

#     return render(
#         request,
#         "interviews/step_system_design.html",
#         {
#             "session": session,
#             "system_design_round": system_design_round,
#             "question": system_design_round.get_question(),
#         },
#     )


# @login_required
# def behavioral_resume_live_view(request):
#     """
#     View for behavioral + resume live interview.
#     Audio-to-audio interview using Gemini Live API.
#     """
#     # Get active session
#     session = get_object_or_404(InterviewSession, user=request.user, status="active")

#     # Check if already completed
#     if session.behavioral_resume_completed:
#         messages.info(
#             request, "Behavioral interview already completed. View your summary below."
#         )

#     return render(
#         request,
#         "interviews/step_behavioral_resume_live.html",
#         {
#             "session": session,
#             "ws_scheme": "wss" if request.is_secure() else "ws",
#             "ws_host": request.get_host(),
#         },
#     )


# @login_required
# def final_analysis_view(request):
#     """
#     Final analysis view showing overall readiness and comprehensive feedback.
#     Only accessible after all sections are completed.
#     """
#     from .models import CodingRound, SystemDesignRound

#     # Get active session
#     session = get_object_or_404(InterviewSession, user=request.user, status="active")

#     # Role-specific completion checks
#     if request.user.user_type == "swe_ng":
#         # Check if all SWE sections are completed
#         if not (
#             session.coding_q1_completed
#             and session.coding_q2_completed
#             and session.system_design_completed
#         ):
#             messages.warning(
#                 request, "Please complete all sections before viewing final analysis."
#             )

#             # Redirect to the next incomplete section
#             if not session.coding_q1_completed:
#                 return redirect("coding_round")
#             elif not session.coding_q2_completed:
#                 return redirect("coding_round_q2")
#             elif not session.system_design_completed:
#                 return redirect("system_design")

#         # Get all rounds for SWE
#         coding_q1 = CodingRound.objects.filter(
#             session=session, question_number=1
#         ).first()
#         coding_q2 = CodingRound.objects.filter(
#             session=session, question_number=2
#         ).first()
#         system_design = SystemDesignRound.objects.filter(session=session).first()

#         # If final analysis doesn't exist yet, generate it
#         if not session.final_analysis or not session.overall_readiness_score:
#             # Prepare session data for analysis
#             session_data = {
#                 "company": session.get_company_display(),
#                 "resume_score": session.resume_fit_score or 0,
#                 "resume_analysis": session.resume_analysis or "N/A",
#                 "coding_q1_score": (
#                     coding_q1.evaluation_result.get("score", 0)
#                     if coding_q1 and coding_q1.evaluation_result
#                     else 0
#                 ),
#                 "coding_q1_correct": (
#                     "Yes"
#                     if coding_q1
#                     and coding_q1.evaluation_result
#                     and coding_q1.evaluation_result.get("is_correct")
#                     else "No"
#                 ),
#                 "coding_q2_score": (
#                     coding_q2.evaluation_result.get("score", 0)
#                     if coding_q2 and coding_q2.evaluation_result
#                     else 0
#                 ),
#                 "coding_q2_correct": (
#                     "Yes"
#                     if coding_q2
#                     and coding_q2.evaluation_result
#                     and coding_q2.evaluation_result.get("is_correct")
#                     else "No"
#                 ),
#                 "system_design_score": (
#                     system_design.evaluation_result.get("score", 0)
#                     if system_design and system_design.evaluation_result
#                     else 0
#                 ),
#                 "system_design_quality": (
#                     "Good"
#                     if system_design
#                     and system_design.evaluation_result
#                     and system_design.evaluation_result.get("is_correct")
#                     else "Needs Work"
#                 ),
#                 "behavioral_resume_summary": session.behavioral_resume_summary
#                 or "Not completed",
#                 "behavioral_resume_completed": session.behavioral_resume_completed,
#             }

#             # Generate comprehensive analysis
#             analyzer = GeminiAnalyzer()
#             final_result = analyzer.generate_final_analysis(session_data)

#             # Save to session
#             session.overall_readiness_score = final_result["overall_score"]
#             session.final_analysis = final_result["analysis"]
#             session.save()

#             messages.success(request, "Final analysis generated successfully!")

#         # Prepare context data
#         context = {
#             "session": session,
#             "coding_q1": coding_q1,
#             "coding_q2": coding_q2,
#             "system_design": system_design,
#         }

#     elif request.user.user_type == "pm_ng":
#         # Check if required PM sections are completed (behavioral is optional)
#         from .models import AnalyticalStrategyRound, ProductSenseRound

#         if not (
#             session.product_sense_completed and session.analytical_strategy_completed
#         ):
#             messages.warning(
#                 request,
#                 "Please complete Product Sense and Analytical + Strategy sections before viewing final analysis.",
#             )

#             # Redirect to the next incomplete section
#             if not session.product_sense_completed:
#                 return redirect("product_sense")
#             elif not session.analytical_strategy_completed:
#                 return redirect("analytical_strategy")

#         # Get all rounds for PM
#         product_sense = ProductSenseRound.objects.filter(session=session).first()
#         analytical_strategy = AnalyticalStrategyRound.objects.filter(
#             session=session
#         ).first()

#         # If final analysis doesn't exist yet, generate it
#         if not session.final_analysis or not session.overall_readiness_score:
#             # Prepare session data for PM analysis
#             session_data = {
#                 "company": session.get_company_display(),
#                 "role": "Product Manager",
#                 "resume_score": session.resume_fit_score or 0,
#                 "resume_analysis": session.resume_analysis or "N/A",
#                 "product_sense_score": (
#                     product_sense.evaluation_result.get("score", 0)
#                     if product_sense and product_sense.evaluation_result
#                     else 0
#                 ),
#                 "product_sense_quality": (
#                     "Good"
#                     if product_sense
#                     and product_sense.evaluation_result
#                     and product_sense.evaluation_result.get("is_good")
#                     else "Needs Work"
#                 ),
#                 "analytical_strategy_score": (
#                     analytical_strategy.evaluation_result.get("score", 0)
#                     if analytical_strategy and analytical_strategy.evaluation_result
#                     else 0
#                 ),
#                 "analytical_strategy_quality": (
#                     "Good"
#                     if analytical_strategy
#                     and analytical_strategy.evaluation_result
#                     and analytical_strategy.evaluation_result.get("is_good")
#                     else "Needs Work"
#                 ),
#                 "behavioral_resume_summary": session.behavioral_resume_summary
#                 or "Not completed",
#             }

#             # Calculate overall score as simple average of numeric scores
#             scores = [
#                 session_data["resume_score"],
#                 session_data["product_sense_score"],
#                 session_data["analytical_strategy_score"],
#             ]
#             overall_score = sum(scores) // len(scores) if scores else 0

#             # Generate comprehensive PM analysis
#             analyzer = GeminiAnalyzer()
#             final_result = analyzer.generate_final_analysis_pm(session_data)

#             # Save to session
#             session.overall_readiness_score = final_result.get(
#                 "overall_score", overall_score
#             )
#             session.final_analysis = final_result["analysis"]
#             session.save()

#             messages.success(request, "Final analysis generated successfully!")

#         # Prepare context data
#         context = {
#             "session": session,
#             "product_sense": product_sense,
#             "analytical_strategy": analytical_strategy,
#             "coding_q1": None,
#             "coding_q2": None,
#             "system_design": None,
#         }

#     else:
#         messages.error(request, "Invalid user type.")
#         return redirect("dashboard")

#     return render(request, "interviews/step_final_analysis.html", context)
