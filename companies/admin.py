from django.contrib import admin
from .models import Company, CompanyDocument, CompanyChunk


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at', 'updated_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CompanyDocument)
class CompanyDocumentAdmin(admin.ModelAdmin):
    list_display = ('company', 'content_type', 'status', 'num_chunks', 'created_at')
    list_filter = ('company', 'content_type', 'status')
    search_fields = ('company__name',)
    readonly_fields = ('status', 'num_chunks', 'error_message', 'created_at', 'updated_at')
    
    def save_model(self, request, obj, form, change):
        """Override save to trigger Celery task for document ingestion"""
        is_new = obj.pk is None
        super().save_model(request, obj, form, change)
        
        # Only trigger ingestion for new documents or if file changed
        if is_new or 'file' in form.changed_data:
            # Import here to avoid circular imports
            from .tasks import ingest_company_document
            # Queue the ingestion task
            ingest_company_document.delay(obj.pk)


@admin.register(CompanyChunk)
class CompanyChunkAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'content_type', 'document', 'text_preview', 'created_at')
    list_filter = ('company', 'content_type')
    search_fields = ('text', 'company__name')
    readonly_fields = ('created_at',)
    
    def text_preview(self, obj):
        """Show first 100 characters of text"""
        return obj.text[:100] + '...' if len(obj.text) > 100 else obj.text
    text_preview.short_description = 'Text Preview'
