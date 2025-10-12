from django.urls import path
from . import views

urlpatterns = [
    path('start/', views.start_session_view, name='start_session'),
    path('analysis/', views.resume_analysis_view, name='interview_analysis'),
    path('end/', views.end_session_view, name='end_session'),
    # Step 2+: Role-specific routes
    path('coding-round/', views.coding_round_view, name='coding_round'),
    path('coding-round-2/', views.coding_round_q2_view, name='coding_round_q2'),
    path('system-design/', views.system_design_view, name='system_design'),
    path('final-analysis/', views.final_analysis_view, name='final_analysis'),
    path('product-sense/', views.product_sense_view, name='product_sense'),
]

