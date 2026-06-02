from django.core.management.base import BaseCommand, CommandError

from apps.analytics.services import get_analytics_connection
from apps.analytics.sql import SCHEMA_STATEMENTS


class Command(BaseCommand):
    help = "Create analytics PostgreSQL tables without using Django migrations."

    def handle(self, *args, **options):
        try:
            with get_analytics_connection() as connection:
                with connection.cursor() as cursor:
                    for statement in SCHEMA_STATEMENTS:
                        cursor.execute(statement)
        except Exception as exc:
            raise CommandError(f"Could not initialize analytics database: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Analytics database tables initialized."))

