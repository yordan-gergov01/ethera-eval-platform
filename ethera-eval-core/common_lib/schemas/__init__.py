"""Pydantic schemas and validation rules shared by the services.

Role: package marker for identity normalisation, the password policy and the user request
  schemas; it also ships `data/common_passwords.txt`.
Used by: `common_lib.schemas.password` reads its bundled data through `importlib.resources`;
  callers import the submodules directly.
Depends on: nothing itself.
Key invariants: ORM-free (import-linter), because the runner image ships it without an ORM.
"""
