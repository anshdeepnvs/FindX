"""
check_db.py — Diagnostic command to test and verify database connections for FindX.

Usage:
  python manage.py check_db
  python manage.py check_db "postgresql://user:password@host/dbname?sslmode=require"
"""

import time
import os
from django.core.management.base import BaseCommand
from django.conf import settings
import dj_database_url
from django.db import connections


class Command(BaseCommand):
    help = "Tests database connection health, latency, PostgreSQL version, and table status."

    def add_arguments(self, parser):
        parser.add_argument(
            "db_url",
            nargs="?",
            type=str,
            default=None,
            help="Optional database URL to test directly (e.g. postgresql://...)",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=" * 65))
        self.stdout.write(self.style.NOTICE("         FINDX DATABASE HEALTH & CONNECTIVITY TEST"))
        self.stdout.write(self.style.NOTICE("=" * 65))

        target_url = options.get("db_url") or os.getenv("DATABASE_URL") or getattr(settings, "DATABASE_URL", None)

        if target_url:
            self.stdout.write(f"Target: Custom / Configured Database URL")
            # Mask password for display
            masked = target_url
            if "@" in masked and "://" in masked:
                scheme, rest = masked.split("://", 1)
                creds, host_part = rest.split("@", 1)
                user = creds.split(":", 1)[0]
                masked = f"{scheme}://{user}:******@{host_part}"
            self.stdout.write(f"URL:    {masked}")
            db_config = dj_database_url.parse(target_url, conn_max_age=600)
            defaults = {
                'ATOMIC_REQUESTS': False,
                'AUTOCOMMIT': True,
                'CONN_MAX_AGE': 0,
                'CONN_HEALTH_CHECKS': True,
                'OPTIONS': {},
                'TIME_ZONE': getattr(settings, "TIME_ZONE", "UTC"),
                'TEST': {},
            }
            for k, v in defaults.items():
                db_config.setdefault(k, v)
        else:
            self.stdout.write("Target: Default settings database")
            db_config = settings.DATABASES["default"]
            self.stdout.write(f"Engine: {db_config.get('ENGINE')}")
            self.stdout.write(f"Name:   {db_config.get('NAME')}")

        self.stdout.write("-" * 65)

        # 1. Format & Structure Validation
        engine = db_config.get("ENGINE", "")
        is_postgres = "postgresql" in engine or "postgres" in engine
        self.stdout.write(f"[1] Engine Type: {'PostgreSQL (Production Cloud DB)' if is_postgres else 'SQLite (Local Dev DB)'}")

        if is_postgres:
            host = db_config.get("HOST", "")
            port = db_config.get("PORT", "5432")
            user = db_config.get("USER", "")
            db_name = db_config.get("NAME", "")
            self.stdout.write(f"    - Host:     {host or '(local socket)'}")
            self.stdout.write(f"    - Port:     {port}")
            self.stdout.write(f"    - User:     {user}")
            self.stdout.write(f"    - Database: {db_name}")

            # Basic sanity check
            if not host:
                self.stdout.write(self.style.ERROR("--> [WARN] Host is empty. Check your connection string format."))
            if not user or not db_name:
                self.stdout.write(self.style.ERROR("--> [WARN] Username or Database name missing in URL."))

        # 2. Live Connection Test
        self.stdout.write("\n[2] Connecting to database...")
        conn_alias = "check_db_test"
        settings.DATABASES[conn_alias] = db_config

        t0 = time.time()
        try:
            conn = connections[conn_alias]
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1;")
                row = cursor.fetchone()
                latency_ms = round((time.time() - t0) * 1000, 1)

                self.stdout.write(self.style.SUCCESS(f"--> [SUCCESS] Connection established! Ping latency: {latency_ms} ms"))

                # 3. Server Version
                if is_postgres:
                    cursor.execute("SELECT version();")
                    version = cursor.fetchone()[0]
                    self.stdout.write(f"\n[3] PostgreSQL Version:\n    {version.split(',')[0]}")

                # 4. Tables check
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
                    if is_postgres else
                    "SELECT name FROM sqlite_master WHERE type='table';"
                )
                tables = [r[0] for r in cursor.fetchall()]
                table_count = len(tables)

                self.stdout.write(f"\n[4] Database Schema Check:")
                self.stdout.write(f"    - Total tables found: {table_count}")

                expected = ["accounts_user", "items_item", "matching_match", "claims_ownershipclaim"]
                missing = [t for t in expected if t not in tables]

                if not missing:
                    self.stdout.write(self.style.SUCCESS("--> [ALL READY] All FindX core tables and models are migrated and ready!"))
                elif table_count == 0:
                    self.stdout.write(self.style.WARNING("--> [EMPTY DB] Connection works! Tables not yet created. Run 'python manage.py migrate' to initialize."))
                else:
                    self.stdout.write(self.style.WARNING(f"--> [MIGRATION PENDING] Some tables pending: {', '.join(missing)}. Run 'python manage.py migrate'."))

            self.stdout.write("\n" + "=" * 65)
            self.stdout.write(self.style.SUCCESS("RESULT: THIS DATABASE LINK IS FULLY FUNCTIONAL AND HEALTHY!"))
            self.stdout.write(self.style.NOTICE("=" * 65))

        except Exception as e:
            latency_ms = round((time.time() - t0) * 1000, 1)
            self.stdout.write(self.style.ERROR(f"--> [FAILED] Could not connect ({latency_ms} ms): {e}"))
            self.stdout.write("\nTroubleshooting tips:")
            err_str = str(e).lower()
            if "password authentication failed" in err_str:
                self.stdout.write(self.style.WARNING("  - Password incorrect in connection URL."))
            elif "does not exist" in err_str:
                self.stdout.write(self.style.WARNING("  - Database name does not exist on the server."))
            elif "timeout" in err_str or "could not translate host name" in err_str:
                self.stdout.write(self.style.WARNING("  - Hostname unreachable. Check spelling of the domain."))
            elif "ssl" in err_str:
                self.stdout.write(self.style.WARNING("  - SSL mode required. Append '?sslmode=require' to your URL."))
            self.stdout.write(self.style.NOTICE("=" * 65))
        finally:
            if conn_alias in connections:
                connections[conn_alias].close()
