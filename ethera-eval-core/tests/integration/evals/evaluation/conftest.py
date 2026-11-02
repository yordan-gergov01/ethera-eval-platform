"""The evaluation module's own integration fixtures: the started platform app of contract §6.

Role: registers `started_platform_app` from tests/integration/registry_fixtures.py for the
  evaluation module's own integration tests in this folder.
Used by: test_repositories.py, test_publishing.py in this folder.
Depends on: tests/integration/registry_fixtures.py.
Key invariants: the same fixture the sealed oracle uses, so these tests run on the app the
  oracle sees (registry and evaluation mounted, both seeds run).
"""

from tests.integration.registry_fixtures import started_platform_app

__all__ = ["started_platform_app"]
