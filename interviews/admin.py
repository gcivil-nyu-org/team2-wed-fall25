from django.contrib import admin
from .models import InterviewSession, CodingRound, SystemDesignRound


@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'status', 'resume_fit_score', 'overall_readiness_score', 'created_at']
    list_filter = ['status', 'company', 'created_at']
    search_fields = ['user__username', 'user__email', 'job_description']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Session Information', {
            'fields': ('user', 'company', 'job_description', 'status')
        }),
        ('AI Analysis Results', {
            'fields': ('resume_fit_score', 'resume_analysis', 'resume_suggestions')
        }),
        ('Section Completion', {
            'fields': ('coding_q1_completed', 'coding_q2_completed', 'system_design_completed')
        }),
        ('Final Analysis', {
            'fields': ('overall_readiness_score', 'final_analysis')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(CodingRound)
class CodingRoundAdmin(admin.ModelAdmin):
    list_display = ['session', 'question_number', 'language', 'is_submitted', 'is_evaluated', 'created_at']
    list_filter = ['question_number', 'language', 'created_at']
    search_fields = ['session__user__username', 'base_question']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Session', {
            'fields': ('session', 'question_number')
        }),
        ('Question Data', {
            'fields': ('base_question', 'generated_questions', 'selected_question_index')
        }),
        ('User Submission', {
            'fields': ('language', 'user_code', 'evaluation_result')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(SystemDesignRound)
class SystemDesignRoundAdmin(admin.ModelAdmin):
    list_display = ['session', 'is_submitted', 'is_evaluated', 'created_at']
    list_filter = ['created_at']
    search_fields = ['session__user__username', 'base_question']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Session', {
            'fields': ('session',)
        }),
        ('Question Data', {
            'fields': ('base_question', 'generated_question')
        }),
        ('User Submission', {
            'fields': ('user_answer', 'evaluation_result')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
