"""The demo target's start-up configuration: generation model, instruction set, retrieval mode.

Role: the closed value sets of contract §3.3 (`Model`, `InstructionSet`, `RetrievalMode`), the
  mock-model table (prices per 1M tokens, latency range, and the model traits the behaviour
  rules R2, R3 and R5 read), and `Configuration.of`, which refuses any unknown value (C-211).
  `read_instruction_set` reads an instruction set's `.md` file from the package data.
Used by: `demo_target.app` (`create_app`), `demo_target.behaviour`; the barrel; the §6 helpers in
  tests/integration/evaluation_fixtures.py; tests/unit/demo_target/.
Depends on: the standard library only (`importlib.resources` for the `.md` files).
Key invariants: values are matched exactly — no stripping, no case folding, no default (C-211);
  prices are decimal strings, never floats (C-210); the medium model's prices are exactly 2.5x
  the small ones', so with model-independent token counts (C-209) every call costs exactly 2.5x;
  the instruction set is read from disk on every construction (FR-206), never cached.
"""

from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files


class UnknownConfigurationError(ValueError):
    """A configuration value the demo target does not know: it refuses to start (C-211)."""


class Model(StrEnum):
    """The mock generation models (contract §3.3)."""

    SMALL_V1 = "mock-gen-small-v1"
    SMALL_V2 = "mock-gen-small-v2"
    MEDIUM_V1 = "mock-gen-medium-v1"


class InstructionSet(StrEnum):
    """The versioned instruction sets (glossary: Instruction set), one `.md` file each."""

    V1 = "v1"
    V2 = "v2"


class RetrievalMode(StrEnum):
    """How the demo target finds help-center documents (glossary: Retrieval mode)."""

    KEYWORD = "keyword"
    SEMANTIC = "semantic"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """One row of the mock-model table (contract §3.3, PP-206, PP-207)."""

    input_per_million: str
    output_per_million: str
    latency_min_ms: int
    latency_max_ms: int
    # R2: how many days the model counts in a week (small-v1's date-math bug counts 5).
    days_per_week: int
    # R3: with nothing covering the question, the model offers a human instead of inventing.
    offers_human_when_uncovered: bool
    # R5: the model adds an unsourced fact to shipping answers.
    embellishes_shipping: bool


CURRENCY = "USD"
MODELS: dict[Model, ModelSpec] = {
    Model.SMALL_V1: ModelSpec("0.20", "0.80", 400, 1200, 5, False, True),
    Model.SMALL_V2: ModelSpec("0.20", "0.80", 400, 1200, 7, False, True),
    Model.MEDIUM_V1: ModelSpec("0.50", "2.00", 1500, 3500, 7, True, False),
}


@dataclass(frozen=True, slots=True)
class Configuration:
    """One process's configuration; built only from known values."""

    model: Model
    instruction_set: InstructionSet
    retrieval: RetrievalMode

    @classmethod
    def of(cls, model: str, instruction_set: str, retrieval: str) -> "Configuration":
        """The configuration named by three exact values; unknown ones refuse (C-211)."""
        return cls(
            model=_known(Model, model, "model"),
            instruction_set=_known(InstructionSet, instruction_set, "instruction set"),
            retrieval=_known(RetrievalMode, retrieval, "retrieval mode"),
        )

    @property
    def spec(self) -> ModelSpec:
        return MODELS[self.model]


def _known[E: StrEnum](values: type[E], raw: str, setting: str) -> E:
    try:
        return values(raw)
    except ValueError:
        known = ", ".join(value.value for value in values)
        raise UnknownConfigurationError(f"unknown {setting}; known: {known}") from None


def read_instruction_set(version: InstructionSet) -> str:
    """The instruction set's text, read from its `.md` file now (FR-206: every construction)."""
    return (files("demo_target") / "instruction_sets" / f"{version.value}.md").read_text(
        encoding="utf-8"
    )
