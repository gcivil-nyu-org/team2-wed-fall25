from django.conf import settings
from django.db import models


class InterviewSession(models.Model):
    """
    Represents an interview preparation session for a user.
    Only one active session per user is allowed.
    """

    STATUS_CHOICES = (
        ("active", "Active"),
        ("completed", "Completed"),
    )

    COMPANY_CHOICES = (
        ("google", "Google"),
        ("amazon", "Amazon"),
        ("microsoft", "Microsoft"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interview_sessions",
    )
    company = models.CharField(max_length=50, choices=COMPANY_CHOICES)
    job_description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    # AI Analysis Results
    resume_fit_score = models.IntegerField(
        null=True, blank=True, help_text="Score out of 100"
    )
    resume_analysis = models.TextField(
        null=True, blank=True, help_text="AI-generated analysis"
    )
    resume_suggestions = models.TextField(
        null=True, blank=True, help_text="AI-generated suggestions"
    )

    # Section Completion Tracking (SWE)
    coding_q1_completed = models.BooleanField(
        default=False, help_text="Coding Question 1 completed"
    )
    coding_q2_completed = models.BooleanField(
        default=False, help_text="Coding Question 2 completed"
    )
    system_design_completed = models.BooleanField(
        default=False, help_text="System Design completed"
    )
    behavioral_resume_completed = models.BooleanField(
        default=False, help_text="Behavioral + Resume live interview completed"
    )

    # Section Completion Tracking (PM)
    product_sense_completed = models.BooleanField(
        default=False, help_text="Product Sense completed"
    )
    analytical_strategy_completed = models.BooleanField(
        default=False, help_text="Analytical + Strategy completed"
    )

    # Behavioral + Resume Live Interview
    behavioral_resume_summary = models.TextField(
        null=True, blank=True, help_text="Final summary from live behavioral interview"
    )

    # Final Analysis
    overall_readiness_score = models.IntegerField(
        null=True, blank=True, help_text="Overall readiness score 0-100"
    )
    final_analysis = models.TextField(
        null=True, blank=True, help_text="Comprehensive final analysis"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="active"),
                name="unique_active_session_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_company_display()} - {self.status}"

    def is_active(self):
        """Check if the session is active"""
        return self.status == "active"

    def has_analysis(self):
        """Check if AI analysis has been performed"""
        return bool(self.resume_fit_score and self.resume_analysis)


class CodingRound(models.Model):
    """
    Stores coding round data for an interview session.
    Includes generated questions and user's submission.
    Multiple coding rounds per session are supported.
    """

    LANGUAGE_CHOICES = (
        ("python", "Python"),
        ("java", "Java"),
        ("javascript", "JavaScript"),
        ("cpp", "C++"),
    )

    session = models.ForeignKey(
        InterviewSession, on_delete=models.CASCADE, related_name="coding_rounds"
    )
    question_number = models.IntegerField(
        default=1, help_text="Question number (1 or 2)"
    )
    base_question = models.TextField(help_text="Base question retrieved from RAG")
    generated_questions = models.JSONField(
        default=list, help_text="List of generated questions with solutions"
    )
    selected_question_index = models.IntegerField(
        default=0, help_text="Index of the question shown to user"
    )
    user_code = models.TextField(blank=True, help_text="User submitted code")
    language = models.CharField(
        max_length=20, choices=LANGUAGE_CHOICES, default="python"
    )
    evaluation_result = models.JSONField(
        null=True, blank=True, help_text="AI evaluation results"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "question_number"],
                name="unique_question_per_session",
            )
        ]

    def __str__(self):
        return f"Coding Round Q{self.question_number} - {self.session.user.username} - {self.session.get_company_display()}"

    def get_selected_question(self):
        """Get the question that was shown to the user"""
        if (
            self.generated_questions
            and len(self.generated_questions) > self.selected_question_index
        ):
            return self.generated_questions[self.selected_question_index]
        return None

    def is_submitted(self):
        """Check if user has submitted code"""
        return bool(self.user_code and self.user_code.strip())

    def is_evaluated(self):
        """Check if submission has been evaluated"""
        return bool(self.evaluation_result)


class SystemDesignRound(models.Model):
    """
    Stores system design round data for an interview session.
    Text-based design question and user's answer.
    """

    session = models.OneToOneField(
        InterviewSession, on_delete=models.CASCADE, related_name="system_design_round"
    )
    base_question = models.TextField(help_text="Base question retrieved from RAG")
    generated_question = models.JSONField(
        null=True,
        blank=True,
        help_text="Generated system design question with evaluation criteria",
    )
    user_answer = models.TextField(blank=True, help_text="User submitted design answer")
    evaluation_result = models.JSONField(
        null=True, blank=True, help_text="AI evaluation results"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"System Design Round - {self.session.user.username} - {self.session.get_company_display()}"

    def get_question(self):
        """Get the generated question"""
        if self.generated_question:
            return self.generated_question.get("question", "")
        return None

    def is_submitted(self):
        """Check if user has submitted answer"""
        return bool(self.user_answer and self.user_answer.strip())

    def is_evaluated(self):
        """Check if submission has been evaluated"""
        return bool(self.evaluation_result)


class ProductSenseRound(models.Model):
    """
    Stores product sense round data for PM interview sessions.
    Text-based product case and user's answer.
    """

    session = models.OneToOneField(
        InterviewSession, on_delete=models.CASCADE, related_name="product_sense_round"
    )
    base_case = models.TextField(help_text="Base case retrieved from RAG")
    generated_case = models.JSONField(
        null=True,
        blank=True,
        help_text="Generated product sense case with evaluation criteria",
    )
    user_answer = models.TextField(blank=True, help_text="User submitted answer")
    evaluation_result = models.JSONField(
        null=True, blank=True, help_text="AI evaluation results"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Product Sense Round - {self.session.user.username} - {self.session.get_company_display()}"

    def get_case(self):
        """Get the generated case"""
        if self.generated_case:
            return self.generated_case.get("case", "")
        return None

    def is_submitted(self):
        """Check if user has submitted answer"""
        return bool(self.user_answer and self.user_answer.strip())

    def is_evaluated(self):
        """Check if submission has been evaluated"""
        return bool(self.evaluation_result)


class AnalyticalStrategyRound(models.Model):
    """
    Stores analytical + strategy round data for PM interview sessions.
    Text-based analytical/strategy question and user's answer.
    """

    session = models.OneToOneField(
        InterviewSession,
        on_delete=models.CASCADE,
        related_name="analytical_strategy_round",
    )
    base_question = models.TextField(help_text="Base question retrieved from RAG")
    generated_question = models.JSONField(
        null=True,
        blank=True,
        help_text="Generated analytical/strategy question with evaluation criteria",
    )
    user_answer = models.TextField(blank=True, help_text="User submitted answer")
    evaluation_result = models.JSONField(
        null=True, blank=True, help_text="AI evaluation results"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Analytical Strategy Round - {self.session.user.username} - {self.session.get_company_display()}"

    def get_question(self):
        """Get the generated question"""
        if self.generated_question:
            return self.generated_question.get("question", "")
        return None

    def is_submitted(self):
        """Check if user has submitted answer"""
        return bool(self.user_answer and self.user_answer.strip())

    def is_evaluated(self):
        """Check if submission has been evaluated"""
        return bool(self.evaluation_result)
