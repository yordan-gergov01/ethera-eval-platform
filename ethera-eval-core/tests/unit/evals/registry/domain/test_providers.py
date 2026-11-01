"""Known providers and the `mock` full-model-ID rule (C-9).

Role: pins evals.registry.domain.providers `is_known_provider` and `is_full_model_id`.
Used by: pytest (unit).
Depends on: nothing beyond the module under test.
Key invariants: `mock` is the only known provider in slice 001; `v0`, `v01` and suffixes such as
  `-latest` are aliases, never full IDs.
"""

import pytest

from evals.registry.domain.providers import is_full_model_id, is_known_provider


def test_is_known_provider_only_mock() -> None:
    assert is_known_provider("mock")
    assert not is_known_provider("openai")
    assert not is_known_provider("Mock")


@pytest.mark.parametrize("model", ["mock-gen-small-v1", "mock-gen-large-v12", "mock-a-b-v10"])
def test_is_full_model_id_mock_full_ids(model: str) -> None:
    assert is_full_model_id("mock", model)


@pytest.mark.parametrize(
    "model",
    [
        "mock-gen-small-latest",
        "mock-gen-small",
        "mock-gen-small-v0",
        "mock-gen-small-v01",
        "mock-gen2-small-v1",
        "mock-gen-small-v1\n",
        "Mock-gen-small-v1",
    ],
)
def test_is_full_model_id_mock_aliases(model: str) -> None:
    assert not is_full_model_id("mock", model)
