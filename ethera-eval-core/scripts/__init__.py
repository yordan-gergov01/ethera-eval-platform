"""Operational scripts of ethera-eval-core (gates and tooling run outside the app).

Role: namespace for scripts run by CI and the `full-gate` skill.
Used by: `.github/workflows/core.yml`, the `full-gate` skill, and their tests.
Depends on: the standard library only.
Key invariants: scripts never import the application packages, so they run on a report
  without the app's dependencies.
"""
