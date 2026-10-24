from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "OpenAPI sxemasini docs/openapi.yaml fayliga eksport qiladi."

    def add_arguments(self, parser):
        parser.add_argument("--file", default="../docs/openapi.yaml")

    def handle(self, *args, **options):
        call_command("spectacular", "--file", options["file"], "--validate")
        self.stdout.write(self.style.SUCCESS(f"OpenAPI: {options['file']}"))
