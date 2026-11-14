# PRISM database migrations

This directory is the authoritative home for schema migrations.

Revision `0001_initial_schema` is a transitional baseline for the current
prototype schema. It creates the tables from the authoritative SQLAlchemy
metadata on a clean database and intentionally has a non-destructive
downgrade. New schema changes must be generated and reviewed through Alembic;
do not add ad-hoc `ALTER TABLE` statements to application startup code.

Migration commands are run from the repository root:

```text
alembic upgrade head
alembic revision --autogenerate -m "describe the schema change"
```
