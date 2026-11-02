"""Response bodies of the evaluation module's HTTP surface (contract §2.1 to 2.2).

Role: `DatasetSummaryResponse` (with `DatasetVersionSummaryResponse` and
  `FailureTypeCountsResponse`) and `DatasetVersionResponse` (with `GoldenResponse`), with their
  mapping from service records.
Used by: `evals.evaluation.api.router`.
Depends on: pydantic; `evals.evaluation.domain` (`Decision`, `FailureType`, `GoldenOwner`);
  `evals.evaluation.repositories` (`VersionRecord`, `GoldenRecord`); `evals.evaluation.services`
  (`DatasetSummary`, `DatasetVersionDetails`).
Key invariants: exactly the contract's keys, nothing more (bodies are compared whole).
  `expected_decision`, `failure_type` and `owner` are published as enums of the domain's value
  sets, and the failure-type counts as an object with one required key per failure type, so the
  web's label maps key on generated unions
  (`test_evaluation_response_value_sets_match_the_domain`). `expected_numbers` are strings as
  written (C-203). `published_at` comes from the same record on both endpoints, so the two
  serialise identically, with a UTC offset. Golden text is returned as plain data, never
  interpreted.
"""

from datetime import datetime

from pydantic import BaseModel

from evals.evaluation.domain import Decision, FailureType, GoldenOwner
from evals.evaluation.repositories import GoldenRecord, VersionRecord
from evals.evaluation.services import DatasetSummary, DatasetVersionDetails


class DatasetVersionSummaryResponse(BaseModel):
    number: int
    published_at: datetime
    golden_count: int

    @classmethod
    def of(cls, version: VersionRecord) -> "DatasetVersionSummaryResponse":
        return cls(
            number=version.number,
            published_at=version.published_at,
            golden_count=version.golden_count,
        )


class FailureTypeCountsResponse(BaseModel):
    """How many Goldens of the current version have each failure type; zeros included."""

    date_math: int
    refund_rules: int
    invented_facts: int
    out_of_docs: int
    retrieval_miss: int
    order_status_tool: int

    @classmethod
    def of(cls, counts: dict[FailureType, int]) -> "FailureTypeCountsResponse":
        return cls.model_validate(
            {failure_type.value: count for failure_type, count in counts.items()}
        )


class DatasetSummaryResponse(BaseModel):
    client_id: str
    project_id: str
    current_version: int
    versions: list[DatasetVersionSummaryResponse]
    failure_type_counts: FailureTypeCountsResponse

    @classmethod
    def of(cls, summary: DatasetSummary) -> "DatasetSummaryResponse":
        return cls(
            client_id=summary.client_id,
            project_id=summary.project_id,
            current_version=summary.current_version,
            versions=[DatasetVersionSummaryResponse.of(v) for v in summary.versions],
            failure_type_counts=FailureTypeCountsResponse.of(summary.failure_type_counts),
        )


class GoldenResponse(BaseModel):
    position: int
    input: str
    expected_decision: Decision
    rule: str
    failure_type: FailureType
    context: str | None
    expected_numbers: list[str]
    owner: GoldenOwner | None
    unfixable_by_code: bool

    @classmethod
    def of(cls, record: GoldenRecord) -> "GoldenResponse":
        golden = record.golden
        return cls(
            position=record.position,
            input=golden.input,
            expected_decision=golden.expected_decision,
            rule=golden.rule,
            failure_type=golden.failure_type,
            context=golden.context,
            expected_numbers=list(golden.expected_numbers),
            owner=golden.owner,
            unfixable_by_code=golden.unfixable_by_code,
        )


class DatasetVersionResponse(BaseModel):
    client_id: str
    project_id: str
    number: int
    published_at: datetime
    is_current: bool
    goldens: list[GoldenResponse]

    @classmethod
    def of(cls, details: DatasetVersionDetails) -> "DatasetVersionResponse":
        return cls(
            client_id=details.client_id,
            project_id=details.project_id,
            number=details.number,
            published_at=details.published_at,
            is_current=details.is_current,
            goldens=[GoldenResponse.of(record) for record in details.goldens],
        )
