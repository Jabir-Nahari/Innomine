"""Shared PostgreSQL connection helpers.

Connection configuration:
- Prefer `DATABASE_URL` (e.g. postgres://user:pass@host:5432/dbname)
- Or use libpq env vars: PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD

Dependency:
- psycopg2 (or psycopg2-binary)
"""

from __future__ import annotations

import os

import psycopg2


def get_connection():
    """Create a new PostgreSQL connection using env vars."""
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return psycopg2.connect(dsn)

    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
    )
