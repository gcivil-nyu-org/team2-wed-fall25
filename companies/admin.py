from django import forms
from django.contrib import admin, messages

from .models import Company, CompanyDocument


class CompanyDocumentAdminForm(forms.ModelForm):
    """Custom form to ensure file upload is handled properly"""

    class Meta:
        model = CompanyDocument
        fields = "__all__"

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file:
            # Check if file has content
            if hasattr(file, "size") and file.size == 0:
                raise forms.ValidationError("The submitted file is empty.")
            # Check if it's a PDF
            if not file.name.lower().endswith(".pdf"):
                raise forms.ValidationError("Only PDF files are allowed.")
        return file


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at", "updated_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(CompanyDocument)
class CompanyDocumentAdmin(admin.ModelAdmin):
    form = CompanyDocumentAdminForm
    list_display = ("company", "content_type", "status", "text_preview", "created_at")
    list_filter = ("company", "content_type", "status")
    search_fields = ("company__name", "extracted_text")
    readonly_fields = (
        "status",
        "error_message",
        "created_at",
        "updated_at",
        "extracted_text_preview",
    )

    def text_preview(self, obj):
        """Show first 100 characters of extracted text"""
        if obj.extracted_text:
            return (
                obj.extracted_text[:100] + "..."
                if len(obj.extracted_text) > 100
                else obj.extracted_text
            )
        return "Not extracted yet"

    text_preview.short_description = "Text Preview"

    def extracted_text_preview(self, obj):
        """Show first 500 characters of extracted text in detail view"""
        if obj.extracted_text:
            return (
                obj.extracted_text[:500] + "..."
                if len(obj.extracted_text) > 500
                else obj.extracted_text
            )
        return "Not extracted yet"

    extracted_text_preview.short_description = "Extracted Text Preview"

    def save_model(self, request, obj, form, change):
        """Override save to process PDF directly instead of using Celery"""
        is_new = obj.pk is None
        file_changed = "file" in form.changed_data

        # Only process if new document or file changed
        if is_new or file_changed:
            # Get the uploaded file from the form
            uploaded_file = form.cleaned_data.get("file")

            if not uploaded_file:
                messages.error(request, "No file was uploaded.")
                # Still let Django save the object normally (may fail if required)
                return super().save_model(request, obj, form, change)

            try:
                # Extract text from PDF before saving
                import io

                from PyPDF2 import PdfReader

                # Read the uploaded file
                uploaded_file.seek(0)
                pdf_content = uploaded_file.read()
                uploaded_file.seek(0)  # Reset for Django to save it

                if not pdf_content:
                    raise ValueError("The uploaded file is empty")

                pdf_reader = PdfReader(io.BytesIO(pdf_content))

                full_text = ""
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"

                # Remove null bytes that PostgreSQL cannot handle
                full_text = full_text.replace("\x00", "")

                # Validate extracted text
                if not full_text.strip():
                    raise ValueError("No text content could be extracted from the PDF")

                # Truncate text if too long (safe token limit for Gemini)
                MAX_CHARS = 15000
                if len(full_text) > MAX_CHARS:
                    full_text = full_text[:MAX_CHARS]

                # Set the extracted text and status before saving
                obj.extracted_text = full_text.strip()
                obj.status = "completed"
                obj.error_message = ""

                messages.success(
                    request,
                    f"Successfully extracted {len(full_text)} characters from PDF.",
                )

            except Exception as e:
                # Only handle PDF / parsing errors here.
                # No DB has been touched yet, so the transaction is still clean.
                obj.status = "failed"
                obj.error_message = f"Error extracting PDF text: {str(e)}"
                messages.error(request, f"Error processing PDF: {str(e)}")

        # Important: all DB write happens here, outside the try/except
        # This ensures any DB errors propagate
        # properly instead of breaking the transaction
        return super().save_model(request, obj, form, change)
