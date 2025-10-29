from django.urls import path

from . import views

urlpatterns = [
    path("start/", views.start_session_view, name="start_session"),
    path("analysis/", views.resume_analysis_view, name="interview_analysis"),
    path("end/", views.end_session_view, name="end_session"),
    # SWE-specific routes
    path("coding-round/", views.coding_round_view, name="coding_round"),
    path("coding-round-2/", views.coding_round_q2_view, name="coding_round_q2"),
    path("system-design/", views.system_design_view, name="system_design"),
    # PM-specific routes
    path("product-sense/", views.product_sense_view, name="product_sense"),
    path(
        "analytical-strategy/",
        views.analytical_strategy_view,
        name="analytical_strategy",
    ),
    # Common routes
    path(
        "behavioral-resume-live/",
        views.behavioral_resume_live_view,
        name="behavioral_resume_live",
    ),
    path("final-analysis/", views.final_analysis_view, name="final_analysis"),
]
