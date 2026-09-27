"""관측 정답의 코드·입력 스키마·실제 분류표를 원거래 해시와 별도로 고정한다."""

import inspect
import json
import sys
from hashlib import sha256
from importlib.metadata import version
from types import FunctionType, ModuleType
from typing import cast

from coaching_service import forecast_validation_month_contracts as contracts
from coaching_service import forecast_validation_month_observations as monthly
from coaching_service import forecast_validation_observations as raw
from coaching_service import forecast_validation_values as values
from coaching_service import periods
from coaching_service.errors import ServiceError


def _source_hash(value: object) -> str:
    if not isinstance(value, (FunctionType, ModuleType)):
        raise TypeError("observation_policy_requires_python_sources")
    return sha256(inspect.getsource(value).encode("utf-8")).hexdigest()


def observation_policy_sha256() -> str:
    """배포 파일 변경과 런타임 분류표 변경을 모두 감지하며 결과를 캐시하지 않는다.

    FDT 예측 코드와 무관한 관측자다. 금액/날짜 파서, 소비 제외 규칙, 원장
    검증 및 봉투 집계의 전체 소스와 실제 사용 중인 helper·상수도 포함한다.
    소스가 없는 배포는 이전 정책과 같다고 추측하지 않고 평가를 차단한다.
    """
    modules = (contracts, monthly, raw, values, periods, sys.modules[__name__])
    functions = (
        raw.integer_amount, raw.valid_time, raw.raw_rows, raw.consumption_amount,
        raw.observed_total, raw.baseline_for, raw.has_future_records,
        monthly.envelope_for, monthly.observed_envelopes, monthly.window_digest,
        monthly.consumption_amount, periods.date_only,
    )
    try:
        # 실행 모듈의 import binding이 provider와 달라질 수 있다. 전체 서비스 대신
        # 실제 관측·정산 소비 함수와 호출 대상만 고정하며 순환 import는 피한다.
        consumer = sys.modules["coaching_service.forecast_validation_month"]
        consumer_namespace = cast("dict[str, object]", consumer.__dict__)
        consumer_names = (
            "freeze_month", "settle_month", "require_current_month",
            "observed_envelopes", "window_digest",
        )
        consumers = {name: _source_hash(consumer_namespace[name]) for name in consumer_names}
        consumer_envelopes = consumer_namespace["ENVELOPES"]
        sources = {module.__name__: _source_hash(module) for module in modules}
        helpers = [_source_hash(function) for function in functions]
    except (KeyError, OSError, TypeError):
        raise ServiceError("validation_month_policy_unavailable", 503) from None
    payload = {
        "version": "monthly-observation-policy/1",
        "sources": sources, "helpers": helpers, "consumers": consumers,
        # Final 표시는 불변성을 강제하지 않는다. 실제 메모리의 값을 따로 넣는다.
        "categories": monthly.CATEGORIES,
        # envelope_for는 먼저 맞는 항목을 택하므로 분류표의 순서도 정책에 포함한다.
        "subcategories": [(name, sorted(labels)) for name, labels in monthly.SUBCATEGORIES.items()],
        "fixed_subcategories": sorted(raw.FIXED_SUBCATEGORIES),
        "envelopes": monthly.ENVELOPES,
        "consumer_envelopes": consumer_envelopes,
        "raw_schema": raw.RawTransaction.model_json_schema(),
        "twin_schema": raw.RawTwin.model_json_schema(),
        "observation_schema": contracts.EnvelopeObservation.model_json_schema(),
        "python": tuple(sys.version_info[:3]),
        "pydantic": version("pydantic"), "pydantic_core": version("pydantic-core"),
    }
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def require_month_policy(month: contracts.MonthlyRegistration) -> None:
    """구버전은 읽을 수 있으나 당시 정책을 증명할 수 없어 새 채점을 허용하지 않는다."""
    if month.policy_sha256 is None:
        raise ServiceError("validation_month_policy_missing", 409)
    if month.policy_sha256 != observation_policy_sha256():
        raise ServiceError("validation_month_policy_changed", 409)
