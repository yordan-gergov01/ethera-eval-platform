"""The demo target's configuration: exact known values, the model table, the instruction sets.

Role: pins demo_target.configuration: every known value starts (C-211), unknown or near-miss
  values refuse with `UnknownConfigurationError` and no default; the model table's prices are
  decimal strings with the medium model at exactly 2.5x (C-209, C-210); and an instruction set
  is read from its `.md` package file.
Used by: pytest (unit; no services).
Depends on: `demo_target.configuration`, `demo_target.app` (`create_app`).
Key invariants: an unknown value refuses before any app exists.
"""

from decimal import Decimal
from pathlib import Path

import pytest

import demo_target
from demo_target.app import create_app
from demo_target.configuration import (
    MODELS,
    Configuration,
    InstructionSet,
    Model,
    RetrievalMode,
    UnknownConfigurationError,
    read_instruction_set,
)


def test_configuration_of_every_known_combination_starts() -> None:
    for model in Model:
        for instruction_set in InstructionSet:
            for retrieval in RetrievalMode:
                configuration = Configuration.of(
                    model.value, instruction_set.value, retrieval.value
                )
                assert create_app(configuration).title == "Demo target"


@pytest.mark.parametrize(
    ("values", "setting"),
    [
        (("mock-gen-small-v1\n", "v1", "keyword"), "model"),
        (("MOCK-GEN-SMALL-V1", "v1", "keyword"), "model"),
        (("mock-gen-small-v1", "V1", "keyword"), "instruction set"),
        (("mock-gen-small-v1", "v1", " semantic"), "retrieval mode"),
    ],
)
def test_configuration_of_unknown_value_refuses_naming_the_setting(
    values: tuple[str, str, str], setting: str
) -> None:
    with pytest.raises(UnknownConfigurationError, match=f"unknown {setting}"):
        Configuration.of(*values)


def test_models_medium_prices_are_two_and_a_half_times_the_small_ones() -> None:
    small, medium = MODELS[Model.SMALL_V1], MODELS[Model.MEDIUM_V1]
    small_v2 = MODELS[Model.SMALL_V2]
    assert (small_v2.input_per_million, small_v2.output_per_million) == (
        small.input_per_million,
        small.output_per_million,
    )
    assert Decimal(medium.input_per_million) / Decimal(small.input_per_million) == Decimal("2.5")
    assert Decimal(medium.output_per_million) / Decimal(small.output_per_million) == Decimal("2.5")


@pytest.mark.parametrize("version", list(InstructionSet))
def test_read_instruction_set_returns_its_package_file(version: InstructionSet) -> None:
    path = Path(demo_target.__file__).parent / "instruction_sets" / f"{version.value}.md"
    assert read_instruction_set(version) == path.read_text(encoding="utf-8")
