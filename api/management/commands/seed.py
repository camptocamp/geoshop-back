from django.core.management.base import BaseCommand
import random


class Command(BaseCommand):
    help = "seed database for testing and development."

    def handle(self, *args, **options):
        print('Seeding data...')
        seed(self)
        print('Done.')


def seed(cmd: Command):
    pass