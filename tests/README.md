# Repository-level test notes

Backend tests live under `apps/api/tests` and use the disposable database
fixture in `apps/api/tests/conftest.py`. The repository database is never used
by automated tests.
