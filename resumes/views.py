import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_http_methods

from accounts.forms import ResumeUpdateForm


@login_required
def view_resume(request):
    """View the logged-in user's resume"""
    user = request.user

    # Check if user has a resume
    if not user.has_resume:
        messages.warning(request, "You have not uploaded a resume yet.")
        return redirect("dashboard")

    # Check if the resume is a PDF (for legacy support)
    resume_path = user.resume.name
    ext = os.path.splitext(resume_path)[1].lower()
    is_pdf = ext == ".pdf"

    return render(
        request,
        "resumes/view_resume.html",
        {
            "user": user,
            "is_pdf": is_pdf,
        },
    )


@login_required
@xframe_options_sameorigin
def serve_resume(request):
    """Serve the resume file with proper headers for iframe embedding"""
    user = request.user

    # Check if user has a resume
    if not user.has_resume:
        raise Http404("Resume not found")

    try:
        # Open the file
        resume_file = user.resume.open("rb")
        response = FileResponse(resume_file, content_type="application/pdf")

        # Set headers to allow inline display
        response["Content-Disposition"] = (
            f'inline; filename="{os.path.basename(user.resume.name)}"'
        )

        return response
    except FileNotFoundError:
        raise Http404("Resume file not found")


@login_required
@require_http_methods(["POST"])
def update_resume(request):
    """Update/replace the user's resume"""
    user = request.user

    form = ResumeUpdateForm(request.POST, request.FILES, instance=user)

    if form.is_valid():
        # Get the old resume path before deletion
        old_resume = user.resume.name if user.resume else None

        # Save the new resume (Django will handle the old file deletion)
        user_instance = form.save(commit=False)

        # If there was an old resume, delete it manually to ensure cleanup
        if old_resume:
            try:
                # Delete the old file from storage
                from django.core.files.storage import default_storage

                if default_storage.exists(old_resume):
                    default_storage.delete(old_resume)
            except Exception as e:
                # Log error but continue
                print(f"Error deleting old resume: {e}")

        # Save the user with new resume
        user_instance.save()

        messages.success(request, "Resume updated successfully!")

        return JsonResponse(
            {"success": True, "message": "Resume updated successfully!"}
        )
    else:
        # Return validation errors
        errors = []
        for field, error_list in form.errors.items():
            for error in error_list:
                errors.append(error)

        return JsonResponse({"success": False, "errors": errors}, status=400)
