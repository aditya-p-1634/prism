# PRISM database migrations

This directory is the authoritative home for schema migrations.

The existing `Base.metadata.create_all()` path remains available for the demo
bootstrap while the initial schema is being captured in a reviewed baseline
migration. New schema changes must be generated and reviewed through Alembic;
do not add ad-hoc `ALTER TABLE` statements to application startup code.

Migration commands are run from the repository root:

```text
alembic upgrade head
alembic revision --autogenerate -m "describe the schema change"
```
