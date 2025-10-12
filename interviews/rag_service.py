"""
RAG (Retrieval Augmented Generation) service for interview content.
Uses simple PostgreSQL queries - Gemini handles semantic matching.
"""
import logging

logger = logging.getLogger(__name__)


class RAGService:
    """Service for retrieving company-specific content from PostgreSQL"""
    
    def retrieve_coding_question(self, company_slug):
        """
        Retrieve all coding questions for the given company.
        Returns list of text chunks - Gemini will select the best ones.
        
        Args:
            company_slug (str): Company slug (e.g., 'amazon', 'google')
            
        Returns:
            list[str]: List of coding question texts, or empty list if not found
        """
        from companies.models import CompanyChunk, Company
        
        try:
            # Get company
            company = Company.objects.get(slug=company_slug)
            
            # Retrieve all coding chunks for this company
            chunks = CompanyChunk.objects.filter(
                company=company,
                content_type='CODING'
            ).values_list('text', flat=True)
            
            chunk_list = list(chunks)
            
            if not chunk_list:
                logger.warning(f"No coding chunks found for company {company_slug}")
                return []
            
            logger.info(f"Retrieved {len(chunk_list)} coding chunks for {company_slug}")
            return chunk_list
            
        except Company.DoesNotExist:
            logger.error(f"Company {company_slug} not found")
            return []
        except Exception as e:
            logger.error(f"Error retrieving coding questions: {str(e)}")
            return []
    
    def retrieve_behavioral_question(self, company_slug):
        """
        Retrieve all behavioral questions for the given company.
        
        Args:
            company_slug (str): Company slug
            
        Returns:
            list[str]: List of behavioral question texts, or empty list
        """
        from companies.models import CompanyChunk, Company
        
        try:
            company = Company.objects.get(slug=company_slug)
            chunks = CompanyChunk.objects.filter(
                company=company,
                content_type='BEHAVIORAL'
            ).values_list('text', flat=True)
            
            chunk_list = list(chunks)
            
            if not chunk_list:
                logger.warning(f"No behavioral chunks found for company {company_slug}")
                return []
            
            logger.info(f"Retrieved {len(chunk_list)} behavioral chunks for {company_slug}")
            return chunk_list
            
        except Exception as e:
            logger.error(f"Error retrieving behavioral questions: {str(e)}")
            return []
    
    def retrieve_system_design_question(self, company_slug):
        """
        Retrieve all system design questions for the given company.
        
        Args:
            company_slug (str): Company slug
            
        Returns:
            list[str]: List of system design question texts, or empty list
        """
        from companies.models import CompanyChunk, Company
        
        try:
            company = Company.objects.get(slug=company_slug)
            chunks = CompanyChunk.objects.filter(
                company=company,
                content_type='SYSTEM_DESIGN'
            ).values_list('text', flat=True)
            
            chunk_list = list(chunks)
            
            if not chunk_list:
                logger.warning(f"No system design chunks found for company {company_slug}")
                return []
            
            logger.info(f"Retrieved {len(chunk_list)} system design chunks for {company_slug}")
            return chunk_list
            
        except Exception as e:
            logger.error(f"Error retrieving system design questions: {str(e)}")
            return []

