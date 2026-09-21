"""Bind every request to a configured principal, never a body-supplied user ID.

A user/notification token is always bound to its own token user_id; the
X-Coaching-User header is ignored for those roles. A backend-role token may
act on behalf of a specific user by sending X-Coaching-User; a backend token
with no header keeps operating as its own user_id (single-account backward
compatibility).
"""

import hmac
from typing import Annotated, Final

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from coaching_service.errors import ServiceError
from coaching_service.settings import Client

BEARER: Final = HTTPBearer(auto_error=False)
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER)]
TargetUser = Annotated[str | None, Header(alias="X-Coaching-User")]


class Authenticate:
    def __init__(self, clients: tuple[Client, ...]) -> None:
        self.clients: tuple[Client, ...] = clients

    def principal(self, credentials: HTTPAuthorizationCredentials | None) -> Client:
        if credentials is not None:
            for client in self.clients:
                if hmac.compare_digest(
                    credentials.credentials.encode(), client.token.get_secret_value().encode()
                ):
                    return client
        raise ServiceError("authentication_required", 401)

    def _owner(self, client: Client, target: str | None) -> str:
        if client.role == "backend" and target is not None:
            resolved = target.strip()
            if not resolved:
                raise ServiceError("invalid_target_user", 400)
            return resolved
        return client.user_id

    def backend(self, credentials: Credentials, target: TargetUser = None) -> str:
        client = self.principal(credentials)
        if client.role != "backend":
            raise ServiceError("backend_role_required", 403)
        return self._owner(client, target)

    def user(self, credentials: Credentials, target: TargetUser = None) -> str:
        client = self.principal(credentials)
        if client.role not in {"user", "backend"}:
            raise ServiceError("user_role_required", 403)
        return self._owner(client, target)

    def notification(self, credentials: Credentials, target: TargetUser = None) -> str:
        client = self.principal(credentials)
        if client.role not in {"notification", "backend"}:
            raise ServiceError("notification_role_required", 403)
        return self._owner(client, target)
