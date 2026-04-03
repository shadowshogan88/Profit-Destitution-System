from django.core.management.base import BaseCommand

from core.services import process_due_investment_returns


class Command(BaseCommand):
    help = "Process due investment return requests (credits principal to wallet after scheduled time)."

    def handle(self, *args, **options):
        processed = process_due_investment_returns()
        self.stdout.write(self.style.SUCCESS(f"Processed {processed} investment return request(s)."))

