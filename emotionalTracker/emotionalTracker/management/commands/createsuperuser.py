from django.contrib.auth.management.commands import createsuperuser
from django.core.management import CommandError
from emotionalTracker.emotionalTracker.models import Service


class Command(createsuperuser.Command):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--role',
            dest='role',
            default='admin',
            help='Specifies the role for the superuser'
        )
        parser.add_argument(
            '--service',
            dest='service',
            default=None,
            help='Specifies the service for the superuser'
        )

    def handle(self, *args, **options):
        if not options.get('role'):
            options['role'] = 'admin'

        if not options.get('service'):
            try:
                default_service = Service.objects.get_or_create(name='Admin Service', department=None)
                if default_service:
                    options['service'] = default_service
            except Exception:
                raise CommandError("No service found. Please create a service first or specify one.")

        return super().handle(*args, **options)