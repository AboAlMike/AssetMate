# myapp/management/commands/fix_migrations.py
from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Fixes the admin/base migration dependency conflict'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Remove problematic admin migrations
            cursor.execute("DELETE FROM django_migrations WHERE app = 'admin'")
            
            # Add Base migration if not present
            cursor.execute("""
                INSERT OR IGNORE INTO django_migrations (app, name, applied)
                VALUES ('Base', '0001_initial', datetime('now'))
            """)
            
            self.stdout.write(self.style.SUCCESS('Successfully fixed migration dependencies'))