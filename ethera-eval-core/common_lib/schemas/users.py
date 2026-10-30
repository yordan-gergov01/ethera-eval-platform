"""Request schemas for user accounts, one per operation.

Role: `UserSelfUpdate`, `UserAdminUpdate`, `UserCreate` and `PasswordChange`, plus the
  `PartialUpdate` base of PATCH bodies.
Used by: `backend.api.v1.users.router`, `backend.services.users.service`;
  tests/unit/backend/test_user_service.py.
Depends on: `common_lib.schemas.identity`, `common_lib.permissions.RoleName`, pydantic.
Key invariants: each schema accepts exactly the fields its operation may change and rejects any
  other (no mass assignment), so a client cannot set a role or active status where it is not
  allowed (template_core D-007). PATCH bodies reject explicit nulls and need at least one field.
  The password policy needs the username and email, so it runs in the service, not here.
"""

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    SecretStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from common_lib.permissions import RoleName
from common_lib.schemas.identity import Email, Username

FULL_NAME_MAX_LENGTH = 200

FullName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=FULL_NAME_MAX_LENGTH)
]


class PartialUpdate(BaseModel):
    """Base of PATCH bodies: omitted fields stay unchanged, at least one is given."""

    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def _reject_null(cls, value: object) -> object:
        # Omitting a field keeps it; an explicit null would mean "clear it", which no
        # field allows.
        if value is None:
            raise ValueError("must not be null; omit the field to keep its value")
        return value

    @model_validator(mode="after")
    def _require_a_change(self) -> "PartialUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be given")
        return self


class UserSelfUpdate(PartialUpdate):
    """Changes a user may make to their own profile."""

    full_name: FullName | None = None
    email: Email | None = None


class UserAdminUpdate(PartialUpdate):
    """Changes an administrator may make to any account.

    Nobody may change their own role or active status; the service enforces that.
    """

    full_name: FullName | None = None
    email: Email | None = None
    role: RoleName | None = None
    is_active: bool | None = None


class UserCreate(BaseModel):
    """A new account. The password policy needs the username and email, so it runs in
    the service, not here.
    """

    model_config = ConfigDict(extra="forbid")

    username: Username
    email: Email
    full_name: FullName
    password: SecretStr
    role: RoleName


class PasswordChange(BaseModel):
    """A new password for the current user, confirmed with the current one.

    The policy check needs the account's username and email, so it runs in the
    service, not here.
    """

    model_config = ConfigDict(extra="forbid")

    current_password: SecretStr
    new_password: SecretStr
