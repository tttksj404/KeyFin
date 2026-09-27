"""Private backend identity and model configuration from the environment only."""

from pathlib import Path
from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from coaching_service.llm_contract import ModelConfig
from coaching_service.schemas import Frozen, Identifier


class Client(Frozen):
    user_id: Identifier
    token: SecretStr = Field(min_length=32)
    role: Literal["backend", "user", "notification"] = "backend"


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="COACHING_", frozen=True, extra="forbid"
    )
    database: Path = Path("state/coaching.sqlite3")
    clients: tuple[Client, ...] = Field(default=(), min_length=1, max_length=1000, validate_default=True)
    model: ModelConfig = ModelConfig()
    # A deterministic FDT operation is CPU-bound in the current service process.
    # Two concurrent distinct simulations preserved the best local request median in
    # the controlled external-dummy screen; higher values stay configurable for a
    # deployment that has its own trace evidence.
    fdt_max_concurrency: Annotated[int, Field(ge=1, le=8)] = 2
    # 사용자에게 보이는 문장의 말투. KeyFin 코치는 고양이라 기본은 "cat"(~다냥)이고,
    # "plain"은 저장된 중립 문장을 그대로(굵게 표시만 제거) 내보낸다.
    persona: Literal["cat", "plain"] = "cat"

    @model_validator(mode="after")
    def unique_tokens(self) -> Self:
        if len({row.token.get_secret_value() for row in self.clients}) != len(self.clients):
            raise ValueError("duplicate_authentication_tokens")
        return self
