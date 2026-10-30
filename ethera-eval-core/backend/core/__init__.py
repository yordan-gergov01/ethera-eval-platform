"""Infrastructure of the backend: settings, database, startup tasks.

Role: package marker for the backend's infrastructure — settings, Tortoise configuration,
  startup lock and migrations, module mounts, password hashing, tokens, periodic tasks and the
  generic job-waiting machinery.
Used by: `backend.main` and the `backend` barrel import its modules directly.
Depends on: nothing itself.
Key invariants: domain modules reach these modules only through the `backend` barrel
  (import-linter "The domain reaches the core only through its barrel").
"""
