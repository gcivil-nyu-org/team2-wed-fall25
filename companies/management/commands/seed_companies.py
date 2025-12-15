"""
Management command to seed initial company data.
"""

from django.core.management.base import BaseCommand
from companies.models import Company


class Command(BaseCommand):
    help = "Seed initial company data (Amazon, Google, Microsoft)"

    def handle(self, *args, **options):
        companies_data = [
            {"slug": "amazon", "name": "Amazon"},
            {"slug": "google", "name": "Google"},
            {"slug": "microsoft", "name": "Microsoft"},
        ]

        created_count = 0
        for company_data in companies_data:
            company, created = Company.objects.get_or_create(
                slug=company_data["slug"], defaults={"name": company_data["name"]}
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created company: {company.name}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"• Company already exists: {company.name}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"\nSuccessfully seeded {created_count} new companies")
        )
