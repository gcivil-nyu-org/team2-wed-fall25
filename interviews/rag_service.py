"""
RAG (Retrieval Augmented Generation) service for interview content.
Randomly selects one full document per interview round.
"""
import logging

logger = logging.getLogger(__name__)


class RAGService:
    """Service for retrieving company-specific content from database"""
    
    def retrieve_coding_question(self, company_slug):
        """
        Randomly select ONE coding document for the given company.
        
        Args:
            company_slug (str): Company slug (e.g., 'amazon', 'google')
            
        Returns:
            str: Extracted text from random document, or empty string if not found
        """
        from companies.models import CompanyDocument, Company
        
        try:
            # Get company
            company = Company.objects.get(slug=company_slug)
            
            # Randomly select one coding document
            document = CompanyDocument.objects.filter(
                company=company,
                content_type='CODING',
                status='completed'
            ).order_by('?').first()
            
            if not document or not document.extracted_text:
                logger.warning(f"No coding document found for company {company_slug}")
                return ""
            
            logger.info(f"Retrieved coding document (ID: {document.id}) for {company_slug}")
            return document.extracted_text
            
        except Company.DoesNotExist:
            logger.error(f"Company {company_slug} not found")
            return ""
        except Exception as e:
            logger.error(f"Error retrieving coding document: {str(e)}")
            return ""
    
    def retrieve_behavioral_question(self, company_slug):
        """
        Randomly select ONE behavioral document for the given company.
        
        Args:
            company_slug (str): Company slug
            
        Returns:
            str: Extracted text from random document, or empty string
        """
        from companies.models import CompanyDocument, Company
        
        try:
            company = Company.objects.get(slug=company_slug)
            
            document = CompanyDocument.objects.filter(
                company=company,
                content_type='BEHAVIORAL',
                status='completed'
            ).order_by('?').first()
            
            if not document or not document.extracted_text:
                logger.warning(f"No behavioral document found for company {company_slug}")
                return ""
            
            logger.info(f"Retrieved behavioral document (ID: {document.id}) for {company_slug}")
            return document.extracted_text
            
        except Exception as e:
            logger.error(f"Error retrieving behavioral document: {str(e)}")
            return ""
    
    def retrieve_system_design_question(self, company_slug):
        """
        Randomly select ONE system design document for the given company.
        
        Args:
            company_slug (str): Company slug
            
        Returns:
            str: Extracted text from random document, or empty string
        """
        from companies.models import CompanyDocument, Company
        
        try:
            company = Company.objects.get(slug=company_slug)
            
            document = CompanyDocument.objects.filter(
                company=company,
                content_type='SYSTEM_DESIGN',
                status='completed'
            ).order_by('?').first()
            
            if not document or not document.extracted_text:
                logger.warning(f"No system design document found for company {company_slug}")
                return ""
            
            logger.info(f"Retrieved system design document (ID: {document.id}) for {company_slug}")
            return document.extracted_text
            
        except Exception as e:
            logger.error(f"Error retrieving system design document: {str(e)}")
            return ""
    
    def retrieve_product_sense_case(self, company_slug):
        """
        Randomly select ONE product sense document for the given company.
        
        Args:
            company_slug (str): Company slug
            
        Returns:
            str: Extracted text from random document, or empty string
        """
        from companies.models import CompanyDocument, Company
        
        try:
            company = Company.objects.get(slug=company_slug)
            
            document = CompanyDocument.objects.filter(
                company=company,
                content_type='PRODUCT_SENSE',
                status='completed'
            ).order_by('?').first()
            
            if not document or not document.extracted_text:
                logger.warning(f"No product sense document found for company {company_slug}")
                return ""
            
            logger.info(f"Retrieved product sense document (ID: {document.id}) for {company_slug}")
            return document.extracted_text
            
        except Exception as e:
            logger.error(f"Error retrieving product sense document: {str(e)}")
            return ""
    
    def retrieve_analytical_strategy_prompt(self, company_slug):
        """
        Randomly select ONE analytical/strategy document for the given company.
        
        Args:
            company_slug (str): Company slug
            
        Returns:
            str: Extracted text from random document, or empty string
        """
        from companies.models import CompanyDocument, Company
        
        try:
            company = Company.objects.get(slug=company_slug)
            
            document = CompanyDocument.objects.filter(
                company=company,
                content_type='ANALYTICAL',
                status='completed'
            ).order_by('?').first()
            
            if not document or not document.extracted_text:
                logger.warning(f"No analytical/strategy document found for company {company_slug}")
                return ""
            
            logger.info(f"Retrieved analytical/strategy document (ID: {document.id}) for {company_slug}")
            return document.extracted_text
            
        except Exception as e:
            logger.error(f"Error retrieving analytical/strategy document: {str(e)}")
            return ""

