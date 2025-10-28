from django.urls import path
from . import views

urlpatterns = [
    path("view/", views.view_resume, name="resume_view"),
    path("file/", views.serve_resume, name="resume_file"),
    path("update/", views.update_resume, name="resume_update"),
]
