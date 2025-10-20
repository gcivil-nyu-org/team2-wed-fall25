"""
Celery tasks for company document ingestion and processing.

NOTE: The ingest_company_document task is NO LONGER USED.
PDF processing now happens synchronously in the admin save_model() method.
This file is kept for reference but can be deleted if Celery is not needed elsewhere.
"""
from celery import shared_task
from django.conf import settings
from PyPDF2 import PdfReader
import io
import logging

logger = logging.getLogger(__name__)


# DEPRECATED: This task is no longer used. Processing happens in admin.py save_model()
@shared_task(bind=True, max_retries=3)
def ingest_company_document(self, document_id):
    """
    Extract text from PDF and store in database.
    The full text is stored and used for random selection during interviews.
    
    Args:
        document_id: Primary key of CompanyDocument to process
    """
    from .models import CompanyDocument
    
    try:
        # Get the document
        document = CompanyDocument.objects.get(pk=document_id)
        document.status = 'processing'
        document.save()
        
        logger.info(f"Starting ingestion for document {document_id}")
        
        # Extract text from PDF
        try:
            pdf_content = document.file.read()
            document.file.seek(0)
            pdf_reader = PdfReader(io.BytesIO(pdf_content))
            
            full_text = ""
            page_texts = []
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                page_texts.append((page_num + 1, page_text))
                full_text += page_text + "\n"
            
            logger.info(f"Extracted {len(page_texts)} pages from document {document_id}")
            
        except Exception as e:
            error_msg = f"Error extracting PDF text: {str(e)}"
            logger.error(error_msg)
            document.status = 'failed'
            document.error_message = error_msg
            document.save()
            return
        
        # Validate extracted text
        if not full_text.strip():
            document.status = 'failed'
            document.error_message = 'No text content extracted from PDF'
            document.save()
            return
        
        # Truncate text to ~15,000 characters (safe token limit for Gemini)
        MAX_CHARS = 15000
        if len(full_text) > MAX_CHARS:
            logger.warning(f"Document {document_id} text truncated from {len(full_text)} to {MAX_CHARS} chars")
            full_text = full_text[:MAX_CHARS]
        
        # Store the full text
        document.extracted_text = full_text.strip()
        document.status = 'completed'
        document.error_message = ''
        document.save()
        
        logger.info(f"Successfully ingested document {document_id} with {len(full_text)} characters")
        
    except CompanyDocument.DoesNotExist:
        logger.error(f"CompanyDocument {document_id} does not exist")
        
    except Exception as e:
        logger.error(f"Unexpected error processing document {document_id}: {str(e)}")
        try:
            document = CompanyDocument.objects.get(pk=document_id)
            document.status = 'failed'
            document.error_message = f"Unexpected error: {str(e)}"
            document.save()
        except:
            pass
        
        # Retry the task
        raise self.retry(exc=e, countdown=60)

