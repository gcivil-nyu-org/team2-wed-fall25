import logging
from unittest.mock import patch, MagicMock
from django.test import TestCase

logger = logging.getLogger(__name__)


class RAGService:
    """
    Service for retrieving company-specific content from database.
    Refactored to use a shared helper for consistent error handling and DRY code.
    """

    def _retrieve_document(self, company_slug, content_type, log_label):
        """
        Internal helper to fetch a random document of a specific type.

        Args:
            company_slug (str): Company slug.
            content_type (str): The DB value for content_type (e.g., 'CODING').
            log_label (str): Human readable label for logging (e.g., 'coding document').

        Returns:
            str: Extracted text or empty string.
        """
        # Local import to prevent circular dependencies
        from companies.models import Company, CompanyDocument

        try:
            company = Company.objects.get(slug=company_slug)

            document = (
                CompanyDocument.objects.filter(
                    company=company, content_type=content_type, status="completed"
                )
                .order_by("?")
                .first()
            )

            if not document or not document.extracted_text:
                logger.warning(f"No {log_label} found for company {company_slug}")
                return ""

            logger.info(
                f"Retrieved {log_label} (ID: {document.id}) for {company_slug}"
            )
            return document.extracted_text

        except Company.DoesNotExist:
            logger.error(f"Company {company_slug} not found")
            return ""
        except Exception as e:
            logger.error(f"Error retrieving {log_label}: {str(e)}")
            return ""

    def retrieve_coding_question(self, company_slug):
        """Randomly select ONE coding document."""
        return self._retrieve_document(company_slug, "CODING", "coding document")

    def retrieve_behavioral_question(self, company_slug):
        """Randomly select ONE behavioral document."""
        return self._retrieve_document(company_slug, "BEHAVIORAL", "behavioral document")

    def retrieve_system_design_question(self, company_slug):
        """Randomly select ONE system design document."""
        return self._retrieve_document(
            company_slug, "SYSTEM_DESIGN", "system design document"
        )

    def retrieve_product_sense_case(self, company_slug):
        """Randomly select ONE product sense document."""
        return self._retrieve_document(
            company_slug, "PRODUCT_SENSE", "product sense document"
        )

    def retrieve_analytical_strategy_prompt(self, company_slug):
        """Randomly select ONE analytical/strategy document."""
        return self._retrieve_document(
            company_slug, "ANALYTICAL", "analytical/strategy document"
        )


# ==============================================================================
# INTEGRATED TESTS
# ==============================================================================
# Run via: python manage.py test <app_name>.rag_service


class RAGServiceTests(TestCase):
    def setUp(self):
        self.service = RAGService()

    @patch("companies.models.CompanyDocument.objects.filter")
    @patch("companies.models.Company.objects.get")
    def test_retrieve_document_success(self, mock_get_company, mock_filter):
        """Test successful retrieval of a document with text."""
        # Setup Mocks
        mock_company = MagicMock()
        mock_get_company.return_value = mock_company

        mock_doc = MagicMock()
        mock_doc.id = 123
        mock_doc.extracted_text = "Expected Content"

        # Mock chain: filter() -> order_by() -> first()
        mock_queryset = mock_filter.return_value
        mock_queryset.order_by.return_value.first.return_value = mock_doc

        # Execute
        result = self.service.retrieve_coding_question("google")

        # Verify
        self.assertEqual(result, "Expected Content")
        mock_get_company.assert_called_with(slug="google")
        mock_filter.assert_called_with(
            company=mock_company, content_type="CODING", status="completed"
        )

    @patch("companies.models.Company.objects.get")
    def test_retrieve_company_not_found(self, mock_get_company):
        """Test graceful handling when company does not exist."""
        # Setup Mock to raise DoesNotExist
        from companies.models import Company

        mock_get_company.side_effect = Company.DoesNotExist

        # Execute
        result = self.service.retrieve_behavioral_question("unknown_company")

        # Verify
        self.assertEqual(result, "")

    @patch("companies.models.CompanyDocument.objects.filter")
    @patch("companies.models.Company.objects.get")
    def test_retrieve_no_document_found(self, mock_get_company, mock_filter):
        """Test when company exists but no documents match criteria."""
        # Setup Mocks
        mock_get_company.return_value = MagicMock()

        # Mock chain returning None
        mock_queryset = mock_filter.return_value
        mock_queryset.order_by.return_value.first.return_value = None

        # Execute
        result = self.service.retrieve_system_design_question("meta")

        # Verify
        self.assertEqual(result, "")

    @patch("companies.models.CompanyDocument.objects.filter")
    @patch("companies.models.Company.objects.get")
    def test_retrieve_document_no_text(self, mock_get_company, mock_filter):
        """Test when document exists but extracted_text is empty."""
        # Setup Mocks
        mock_get_company.return_value = MagicMock()

        mock_doc = MagicMock()
        mock_doc.extracted_text = ""  # Empty text

        mock_queryset = mock_filter.return_value
        mock_queryset.order_by.return_value.first.return_value = mock_doc

        # Execute
        result = self.service.retrieve_product_sense_case("uber")

        # Verify
        self.assertEqual(result, "")

    @patch("companies.models.Company.objects.get")
    def test_retrieve_generic_exception(self, mock_get_company):
        """Test handling of unexpected database errors."""
        mock_get_company.side_effect = Exception("Database is down")

        result = self.service.retrieve_analytical_strategy_prompt("amazon")

        self.assertEqual(result, "")

    @patch("companies.models.CompanyDocument.objects.filter")
    @patch("companies.models.Company.objects.get")
    def test_all_wrappers_call_correct_types(self, mock_get, mock_filter):
        """Ensure all public methods pass the correct content_type string."""
        mock_get.return_value = MagicMock()
        mock_doc = MagicMock()
        mock_doc.extracted_text = "Content"
        mock_filter.return_value.order_by.return_value.first.return_value = mock_doc

        # 1. Behavioral
        self.service.retrieve_behavioral_question("c")
        kwargs = mock_filter.call_args[1]
        self.assertEqual(kwargs["content_type"], "BEHAVIORAL")

        # 2. System Design
        self.service.retrieve_system_design_question("c")
        kwargs = mock_filter.call_args[1]
        self.assertEqual(kwargs["content_type"], "SYSTEM_DESIGN")

        # 3. Product Sense
        self.service.retrieve_product_sense_case("c")
        kwargs = mock_filter.call_args[1]
        self.assertEqual(kwargs["content_type"], "PRODUCT_SENSE")

        # 4. Analytical
        self.service.retrieve_analytical_strategy_prompt("c")
        kwargs = mock_filter.call_args[1]
        self.assertEqual(kwargs["content_type"], "ANALYTICAL")
