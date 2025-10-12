from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError
from .models import InterviewSession
from .gemini_service import GeminiAnalyzer


@login_required
def start_session_view(request):
    """
    View to start a new interview session or continue existing one.
    Displays form with company dropdown and job description textarea.
    """
    # Check if user already has an active session
    active_session = InterviewSession.objects.filter(
        user=request.user,
        status='active'
    ).first()
    
    if active_session:
        # If session has analysis, show it; otherwise, process it
        if active_session.has_analysis():
            return redirect('interview_analysis')
        else:
            # Process the analysis
            return redirect('interview_analysis')
    
    if request.method == 'POST':
        company = request.POST.get('company')
        job_description = request.POST.get('job_description', '').strip()
        
        # Validation
        if not company or company not in dict(InterviewSession.COMPANY_CHOICES):
            messages.error(request, 'Please select a valid company.')
            return render(request, 'interviews/start_session.html', {
                'companies': InterviewSession.COMPANY_CHOICES,
                'job_description': job_description
            })
        
        if not job_description:
            messages.error(request, 'Please enter a job description.')
            return render(request, 'interviews/start_session.html', {
                'companies': InterviewSession.COMPANY_CHOICES,
                'selected_company': company
            })
        
        if len(job_description) < 50:
            messages.error(request, 'Job description must be at least 50 characters long.')
            return render(request, 'interviews/start_session.html', {
                'companies': InterviewSession.COMPANY_CHOICES,
                'selected_company': company,
                'job_description': job_description
            })
        
        # Check if user has uploaded a resume
        if not request.user.has_resume:
            messages.error(request, 'Please upload your resume before starting an interview session.')
            return redirect('profile')
        
        try:
            # Create new session
            session = InterviewSession.objects.create(
                user=request.user,
                company=company,
                job_description=job_description,
                status='active'
            )
            
            messages.success(request, f'Interview session started for {session.get_company_display()}!')
            return redirect('interview_analysis')
            
        except IntegrityError:
            messages.error(request, 'You already have an active session. Please end it before starting a new one.')
            return redirect('dashboard')
    
    return render(request, 'interviews/start_session.html', {
        'companies': InterviewSession.COMPANY_CHOICES
    })


@login_required
def resume_analysis_view(request):
    """
    View to display or generate resume analysis results.
    Calls Gemini API to analyze resume fit with job description.
    """
    # Get active session
    session = get_object_or_404(
        InterviewSession,
        user=request.user,
        status='active'
    )
    
    # If analysis doesn't exist yet, generate it
    if not session.has_analysis():
        # Initialize Gemini analyzer
        analyzer = GeminiAnalyzer()
        
        # Extract resume text
        try:
            resume_text = analyzer.extract_text_from_pdf(request.user.resume)
        except Exception as e:
            messages.error(request, f'Error reading resume: {str(e)}')
            resume_text = "Resume text could not be extracted."
        
        # Analyze resume fit
        analysis_result = analyzer.analyze_resume_fit(
            resume_text=resume_text,
            job_description=session.job_description,
            company_name=session.get_company_display()
        )
        
        # Save results to session
        session.resume_fit_score = analysis_result['fit_score']
        session.resume_analysis = analysis_result['analysis']
        session.resume_suggestions = analysis_result['suggestions']
        session.save()
        
        messages.success(request, 'Resume analysis completed!')
    
    return render(request, 'interviews/analysis.html', {
        'session': session
    })


@login_required
def end_session_view(request):
    """
    View to end the current active interview session.
    """
    if request.method == 'POST':
        # Get active session
        session = InterviewSession.objects.filter(
            user=request.user,
            status='active'
        ).first()
        
        if session:
            session.status = 'completed'
            session.save()
            messages.success(request, 'Interview session ended successfully.')
        else:
            messages.info(request, 'No active session found.')
        
        return redirect('dashboard')
    
    # If GET request, show confirmation page
    session = get_object_or_404(
        InterviewSession,
        user=request.user,
        status='active'
    )
    
    return render(request, 'interviews/end_session_confirm.html', {
        'session': session
    })


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
    session = get_object_or_404(
        InterviewSession,
        user=request.user,
        status='active'
    )
    
    # Ensure user is SWE type
    if request.user.user_type != 'swe_ng':
        messages.error(request, 'This step is only available for Software Engineer role.')
        return redirect('interview_analysis')
    
    # Get or create coding round for question 1
    coding_round, created = CodingRound.objects.get_or_create(
        session=session,
        question_number=1
    )
    
    # If newly created or no questions generated yet, generate them
    if created or not coding_round.generated_questions:
        rag_service = RAGService()
        
        # Retrieve all coding chunks for this company
        chunks = rag_service.retrieve_coding_question(session.company)
        
        if not chunks:
            # Fallback question if no content available
            chunks = ["Write a function to find the longest substring without repeating characters in a given string."]
            messages.warning(request, 'Using fallback question. Please ensure company documents are uploaded.')
        
        # Let Gemini select best question and generate similar ones
        analyzer = GeminiAnalyzer()
        generated_questions = analyzer.select_and_generate_questions(
            chunks=chunks,
            company_name=session.get_company_display(),
            num_questions=2
        )
        
        # Save to coding round
        coding_round.base_question = f"Generated from {len(chunks)} company-specific questions"
        coding_round.generated_questions = generated_questions
        coding_round.selected_question_index = 0  # Show first question
        coding_round.save()
        
        messages.success(request, 'Coding questions generated successfully!')
    
    # Handle POST: code submission and evaluation
    if request.method == 'POST':
        print("DEBUG: POST request received!")  # Debug
        user_code = request.POST.get('user_code', '').strip()
        language = request.POST.get('language', 'python')
        print(f"DEBUG: user_code length: {len(user_code)}, language: {language}")  # Debug
        
        if not user_code:
            messages.error(request, 'Please write some code before submitting.')
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
                    question=selected_question.get('question', ''),
                    reference_solution=selected_question.get('solution', ''),
                    user_code=user_code,
                    language=language
                )
                print(f"DEBUG: Evaluation result: {evaluation}")  # Debug
                
                # Save evaluation
                coding_round.evaluation_result = evaluation
                coding_round.save()
                
                # Mark coding Q1 as completed
                session.coding_q1_completed = True
                session.save()
                
                # Show feedback message
                if evaluation.get('is_correct'):
                    messages.success(request, f'Great job! Your solution is correct. Score: {evaluation.get("score")}/100')
                else:
                    messages.info(request, f'Your solution needs improvement. Score: {evaluation.get("score")}/100')
            else:
                print("DEBUG: No selected question found!")  # Debug
                messages.error(request, 'Could not evaluate: question not found.')
    
    return render(request, 'interviews/step_coding_round.html', {
        'session': session,
        'coding_round': coding_round,
        'selected_question': coding_round.get_selected_question(),
    })


@login_required
def product_sense_view(request):
    """
    Placeholder view for Product Manager product sense step.
    """
    # Get active session
    session = get_object_or_404(
        InterviewSession,
        user=request.user,
        status='active'
    )
    
    # Ensure user is PM type
    if request.user.user_type != 'pm_ng':
        messages.error(request, 'This step is only available for Product Manager role.')
        return redirect('interview_analysis')
    
    return render(request, 'interviews/step_product_sense.html', {
        'session': session
    })


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
    session = get_object_or_404(
        InterviewSession,
        user=request.user,
        status='active'
    )
    
    # Ensure user is SWE type
    if request.user.user_type != 'swe_ng':
        messages.error(request, 'This step is only available for Software Engineer role.')
        return redirect('interview_analysis')
    
    # Get or create coding round for question 2
    coding_round, created = CodingRound.objects.get_or_create(
        session=session,
        question_number=2
    )
    
    # If newly created or no questions generated yet, generate them
    if created or not coding_round.generated_questions:
        rag_service = RAGService()
        
        # Retrieve all coding chunks for this company
        chunks = rag_service.retrieve_coding_question(session.company)
        
        if not chunks:
            # Fallback question if no content available
            chunks = ["Write a function to implement a least recently used (LRU) cache with get and put operations."]
            messages.warning(request, 'Using fallback question. Please ensure company documents are uploaded.')
        
        # Let Gemini select best question and generate similar ones
        analyzer = GeminiAnalyzer()
        generated_questions = analyzer.select_and_generate_questions(
            chunks=chunks,
            company_name=session.get_company_display(),
            num_questions=2
        )
        
        # Save to coding round
        coding_round.base_question = f"Generated from {len(chunks)} company-specific questions"
        coding_round.generated_questions = generated_questions
        coding_round.selected_question_index = 0  # Show first question
        coding_round.save()
        
        messages.success(request, 'Coding question 2 generated successfully!')
    
    # Handle POST: code submission and evaluation
    if request.method == 'POST':
        user_code = request.POST.get('user_code', '').strip()
        language = request.POST.get('language', 'python')
        
        if not user_code:
            messages.error(request, 'Please write some code before submitting.')
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
                    question=selected_question.get('question', ''),
                    reference_solution=selected_question.get('solution', ''),
                    user_code=user_code,
                    language=language
                )
                
                # Save evaluation
                coding_round.evaluation_result = evaluation
                coding_round.save()
                
                # Mark coding Q2 as completed
                session.coding_q2_completed = True
                session.save()
                
                # Show feedback message
                if evaluation.get('is_correct'):
                    messages.success(request, f'Great job! Your solution is correct. Score: {evaluation.get("score")}/100')
                else:
                    messages.info(request, f'Your solution needs improvement. Score: {evaluation.get("score")}/100')
            else:
                messages.error(request, 'Could not evaluate: question not found.')
    
    return render(request, 'interviews/step_coding_round_2.html', {
        'session': session,
        'coding_round': coding_round,
        'selected_question': coding_round.get_selected_question(),
    })


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
    session = get_object_or_404(
        InterviewSession,
        user=request.user,
        status='active'
    )
    
    # Ensure user is SWE type
    if request.user.user_type != 'swe_ng':
        messages.error(request, 'This step is only available for Software Engineer role.')
        return redirect('interview_analysis')
    
    # Get or create system design round
    system_design_round, created = SystemDesignRound.objects.get_or_create(session=session)
    
    # If newly created or no question generated yet, generate it
    if created or not system_design_round.generated_question:
        rag_service = RAGService()
        
        # Retrieve all system design chunks for this company
        chunks = rag_service.retrieve_system_design_question(session.company)
        
        if not chunks:
            # Fallback question if no content available
            chunks = ["Design a URL shortening service like bit.ly. The system should support creating short URLs, redirecting to original URLs, and tracking click analytics."]
            messages.warning(request, 'Using fallback question. Please ensure company documents are uploaded.')
        
        # Let Gemini select best question and generate a similar one
        analyzer = GeminiAnalyzer()
        generated_question = analyzer.select_and_generate_system_design_question(
            chunks=chunks,
            company_name=session.get_company_display()
        )
        
        # Save to system design round
        system_design_round.base_question = f"Generated from {len(chunks)} company-specific questions"
        system_design_round.generated_question = generated_question
        system_design_round.save()
        
        messages.success(request, 'System design question generated successfully!')
    
    # Handle POST: design answer submission and evaluation
    if request.method == 'POST':
        user_answer = request.POST.get('user_answer', '').strip()
        
        if not user_answer:
            messages.error(request, 'Please write your design answer before submitting.')
        else:
            # Save user submission
            system_design_round.user_answer = user_answer
            system_design_round.save()
            
            # Evaluate the design
            question = system_design_round.get_question()
            evaluation_criteria = system_design_round.generated_question.get('evaluation_criteria') if system_design_round.generated_question else None
            
            if question:
                analyzer = GeminiAnalyzer()
                evaluation = analyzer.evaluate_system_design(
                    question=question,
                    user_answer=user_answer,
                    evaluation_criteria=evaluation_criteria
                )
                
                # Save evaluation
                system_design_round.evaluation_result = evaluation
                system_design_round.save()
                
                # Mark system design as completed
                session.system_design_completed = True
                session.save()
                
                # Show feedback message
                if evaluation.get('is_correct'):
                    messages.success(request, f'Excellent design! Score: {evaluation.get("score")}/100')
                else:
                    messages.info(request, f'Your design needs improvement. Score: {evaluation.get("score")}/100')
            else:
                messages.error(request, 'Could not evaluate: question not found.')
    
    return render(request, 'interviews/step_system_design.html', {
        'session': session,
        'system_design_round': system_design_round,
        'question': system_design_round.get_question(),
    })


@login_required
def final_analysis_view(request):
    """
    Final analysis view showing overall readiness and comprehensive feedback.
    Only accessible after all sections are completed.
    """
    from .models import CodingRound, SystemDesignRound
    
    # Get active session
    session = get_object_or_404(
        InterviewSession,
        user=request.user,
        status='active'
    )
    
    # Ensure user is SWE type (for now)
    if request.user.user_type != 'swe_ng':
        messages.error(request, 'This step is only available for Software Engineer role.')
        return redirect('interview_analysis')
    
    # Check if all sections are completed
    if not (session.coding_q1_completed and session.coding_q2_completed and session.system_design_completed):
        messages.warning(request, 'Please complete all sections before viewing final analysis.')
        
        # Redirect to the next incomplete section
        if not session.coding_q1_completed:
            return redirect('coding_round')
        elif not session.coding_q2_completed:
            return redirect('coding_round_q2')
        elif not session.system_design_completed:
            return redirect('system_design')
    
    # Get all rounds
    coding_q1 = CodingRound.objects.filter(session=session, question_number=1).first()
    coding_q2 = CodingRound.objects.filter(session=session, question_number=2).first()
    system_design = SystemDesignRound.objects.filter(session=session).first()
    
    # If final analysis doesn't exist yet, generate it
    if not session.final_analysis or not session.overall_readiness_score:
        # Prepare session data for analysis
        session_data = {
            'company': session.get_company_display(),
            'resume_score': session.resume_fit_score or 0,
            'resume_analysis': session.resume_analysis or 'N/A',
            'coding_q1_score': coding_q1.evaluation_result.get('score', 0) if coding_q1 and coding_q1.evaluation_result else 0,
            'coding_q1_correct': 'Yes' if coding_q1 and coding_q1.evaluation_result and coding_q1.evaluation_result.get('is_correct') else 'No',
            'coding_q2_score': coding_q2.evaluation_result.get('score', 0) if coding_q2 and coding_q2.evaluation_result else 0,
            'coding_q2_correct': 'Yes' if coding_q2 and coding_q2.evaluation_result and coding_q2.evaluation_result.get('is_correct') else 'No',
            'system_design_score': system_design.evaluation_result.get('score', 0) if system_design and system_design.evaluation_result else 0,
            'system_design_quality': 'Good' if system_design and system_design.evaluation_result and system_design.evaluation_result.get('is_correct') else 'Needs Work',
        }
        
        # Generate comprehensive analysis
        analyzer = GeminiAnalyzer()
        final_result = analyzer.generate_final_analysis(session_data)
        
        # Save to session
        session.overall_readiness_score = final_result['overall_score']
        session.final_analysis = final_result['analysis']
        session.save()
        
        messages.success(request, 'Final analysis generated successfully!')
    
    # Prepare context data
    context = {
        'session': session,
        'coding_q1': coding_q1,
        'coding_q2': coding_q2,
        'system_design': system_design,
    }
    
    return render(request, 'interviews/step_final_analysis.html', context)