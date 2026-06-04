"""
persistence — SQLAlchemy 2.0 parallel store (Phase 5a scaffolding).

Additive and OFF by default (`settings.use_sqlalchemy`). The default engine URL
is a DEDICATED sqlite file, never the live sterling_paper.db. Postgres-ready:
set DATABASE_URL. Phase 5b wires dual-write/verify against the existing raw-
sqlite stores; see MIGRATION.md.
"""
