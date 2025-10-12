"""
Management command to backfill embeddings for existing company documents.
"""
from django.core.management.base import BaseCommand
from companies.models import CompanyDocument
from companies.tasks import ingest_company_document


class Command(BaseCommand):
    help = 'Backfill embeddings for existing company documents'

    def add_arguments(self, parser):
        parser.add_argument(
            '--document-id',
            type=int,
            help='Process specific document by ID',
        )
        parser.add_argument(
            '--status',
            type=str,
            default='pending',
            help='Process documents with specific status (default: pending)',
        )

    def handle(self, *args, **options):
        document_id = options.get('document_id')
        status = options.get('status')
        
        if document_id:
            # Process single document
            try:
                document = CompanyDocument.objects.get(pk=document_id)
                self.stdout.write(f'Processing document {document_id}...')
                ingest_company_document.delay(document_id)
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Queued document {document_id} for processing')
                )
            except CompanyDocument.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'✗ Document {document_id} not found')
                )
        else:
            # Process all documents with given status
            documents = CompanyDocument.objects.filter(status=status)
            count = documents.count()
            
            if count == 0:
                self.stdout.write(
                    self.style.WARNING(f'No documents found with status "{status}"')
                )
                return
            
            self.stdout.write(f'Found {count} documents with status "{status}"')
            
            for document in documents:
                self.stdout.write(f'Queuing document {document.id}: {document}')
                ingest_company_document.delay(document.id)
            
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Successfully queued {count} documents for processing')
            )
            self.stdout.write(
                'Note: Processing will happen in the background via Celery workers'
            )

