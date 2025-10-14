"""
Celery tasks for company document ingestion and processing.
"""
from celery import shared_task
from django.conf import settings
from PyPDF2 import PdfReader
import io
import logging

logger = logging.getLogger(__name__)


def chunk_text(text, chunk_size=1000, overlap=150):
    """
    Split text into overlapping chunks.
    
    Args:
        text: The text to chunk
        chunk_size: Target size of each chunk
        overlap: Number of characters to overlap between chunks
    
    Returns:
        List of text chunks
    """
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = start + chunk_size
        
        # If this is not the last chunk, try to break at a sentence or word boundary
        if end < text_length:
            # Look for sentence ending
            sentence_end = text.rfind('.', start, end)
            if sentence_end > start:
                end = sentence_end + 1
            else:
                # Look for word boundary
                space = text.rfind(' ', start, end)
                if space > start:
                    end = space
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start position with overlap
        start = end - overlap if end < text_length else text_length
    
    return chunks


@shared_task(bind=True, max_retries=3)
def ingest_company_document(self, document_id):
    """
    Extract text from PDF, chunk it, and store in database.
    No embeddings needed - Gemini will handle semantic matching.
    
    Args:
        document_id: Primary key of CompanyDocument to process
    """
    from .models import CompanyDocument, CompanyChunk
    
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
        
        # Chunk the text
        chunks = chunk_text(full_text, chunk_size=1000, overlap=150)
        logger.info(f"Created {len(chunks)} chunks from document {document_id}")
        
        if not chunks:
            document.status = 'failed'
            document.error_message = 'No text content extracted from PDF'
            document.save()
            return
        
        # Create CompanyChunk objects (no embeddings needed!)
        chunk_objects = []
        for idx, chunk_text in enumerate(chunks):
            chunk_obj = CompanyChunk(
                document=document,
                company=document.company,
                content_type=document.content_type,
                text=chunk_text,
                metadata={
                    'chunk_index': idx,
                    'total_chunks': len(chunks),
                    'char_count': len(chunk_text)
                }
            )
            chunk_objects.append(chunk_obj)
        
        # Bulk create all chunks at once
        CompanyChunk.objects.bulk_create(chunk_objects)
        total_chunks_created = len(chunk_objects)
        logger.info(f"Created {total_chunks_created} chunks for document {document_id}")
        
        # Update document status
        document.status = 'completed'
        document.num_chunks = total_chunks_created
        document.error_message = ''
        document.save()
        
        logger.info(f"Successfully ingested document {document_id} with {total_chunks_created} chunks")
        
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

