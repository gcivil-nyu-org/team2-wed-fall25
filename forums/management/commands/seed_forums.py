from django.core.management.base import BaseCommand

from forums.models import Forum


class Command(BaseCommand):
    help = "Creates sample forums for the collaboration feature"

    def handle(self, *args, **options):
        forums_data = [
            {
                "name": "SWE Interview Prep",
                "description": "Discuss coding challenges, system design, and technical interview strategies for Software Engineering roles.",
                "icon": "fa-code",
                "user_type": "swe_ng",
            },
            {
                "name": "PM Interview Prep",
                "description": "Share product sense questions, case studies, and strategies for Product Manager interviews.",
                "icon": "fa-lightbulb",
                "user_type": "pm_ng",
            },
            {
                "name": "General Discussion",
                "description": "General discussions about interview preparation, career advice, and networking.",
                "icon": "fa-comments",
                "user_type": None,
            },
            {
                "name": "Case Studies",
                "description": "Share and discuss real interview case studies and how to approach them.",
                "icon": "fa-book",
                "user_type": None,
            },
            {
                "name": "Success Stories",
                "description": "Celebrate wins and share your interview success stories to inspire others.",
                "icon": "fa-trophy",
                "user_type": None,
            },
        ]

        created_count = 0
        for forum_data in forums_data:
            forum, created = Forum.objects.get_or_create(
                name=forum_data["name"], defaults=forum_data
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created forum: {forum.name}"))
            else:
                self.stdout.write(
                    self.style.WARNING(f"Forum already exists: {forum.name}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"\nSuccessfully created {created_count} new forum(s)!")
        )
