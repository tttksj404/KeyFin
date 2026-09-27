"""전체 소비와 봉투 평가가 공유하는 엄격한 금액·분위수 계약."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from coaching_service.schemas import Frozen

Amount = Annotated[int, Field(strict=True, ge=0, le=10**14)]
Finite = Annotated[float, Field(allow_inf_nan=False)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Origin = Literal["synthetic", "historical_real", "backend_attested_real"]
Tier = Literal["synthetic", "replay", "prospective_attested"]
EnvelopeName = Literal["외식", "교통비", "의료·건강", "취미·여가", "쇼핑", "편의점·마트·잡화", "기타"]
ENVELOPES: tuple[EnvelopeName, ...] = (
    "외식", "교통비", "의료·건강", "취미·여가", "쇼핑", "편의점·마트·잡화", "기타",
)


class Quantiles(Frozen):
    p10: Amount
    p50: Amount
    p90: Amount

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if not self.p10 <= self.p50 <= self.p90:
            raise ValueError("unordered_quantiles")
        return self
