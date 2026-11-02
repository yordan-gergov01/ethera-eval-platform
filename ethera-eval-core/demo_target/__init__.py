"""The demo target: the client's product under test, a support chatbot with mock models.

Role: the package barrel — `create_app` and the configuration it is started with (generation
  model, instruction set, retrieval mode), the refusal of unknown values, the demo target's own
  Decision set, and the name of its logger.
Used by: tests/integration/evaluation_fixtures.py (the contract §6 helpers);
  tests/unit/demo_target/. The runner reaches it over HTTP in the `sandbox` network from
  slice 003 (D-024 Fork D1).
Depends on: `demo_target.app`, `demo_target.behaviour`, `demo_target.configuration`.
Key invariants: imports nothing from this repository's other packages (FR-208; import-linter
  contract "The demo target imports nothing from this repository"); it plays the client's
  product, so it is never a domain module and never mounted in the platform.
"""

from demo_target.app import LOGGER_NAME, create_app
from demo_target.behaviour import Decision
from demo_target.configuration import (
    Configuration,
    InstructionSet,
    Model,
    RetrievalMode,
    UnknownConfigurationError,
)

__all__ = [
    "LOGGER_NAME",
    "Configuration",
    "Decision",
    "InstructionSet",
    "Model",
    "RetrievalMode",
    "UnknownConfigurationError",
    "create_app",
]
