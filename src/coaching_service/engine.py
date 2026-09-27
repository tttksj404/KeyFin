"""Direct calls to the pinned FDT with bounded immutable-result reuse."""

from __future__ import annotations

import json
from collections import OrderedDict
from concurrent.futures import Future
from hashlib import sha256
from threading import RLock
from typing import TYPE_CHECKING, Final, final

from fdt import Engine, Twin
from fdt.coaching import Coach, observed_budgets
from fdt.ingest import Transaction, normalize
from fdt.store import apply_events
from pydantic import JsonValue, ValidationError

from coaching_service.admission import admit
from coaching_service.chart_engine import ChartEngine
from coaching_service.errors import ServiceError
from coaching_service.provenance import ENGINE_COMMIT
from coaching_service.schemas import Bootstrap, JsonDocument, TransactionView, TwinIdentity

if TYPE_CHECKING:
    from collections.abc import Callable

    from coaching_service.chart_contract import DailyForecast

__all__ = ("ENGINE_COMMIT", "EngineAdapter")


def normalized_transaction(document: JsonDocument) -> Transaction:
    """팀 엔진의 정규화를 유지하되 입금을 소비로 세는 모순된 입력은 거부한다."""
    transaction = normalize(document.root)
    # 고정된 FDT 설계에서 TRANSFER_IN은 입금이다. 누락·INCOME·TRANSFER의 기존
    # 해석은 유지하고, EXPENSE로 동시에 지정한 경우만 저장 전에 422로 돌려준다.
    if (
        transaction.raw.get("transaction_type") == "TRANSFER_IN"
        and transaction.raw.get("direction") == "EXPENSE"
    ):
        raise ServiceError("inconsistent_transfer_direction")
    return transaction


# ``Coach.review`` 가 시뮬레이션 전에 붙이는 입력 점검 경고. 잔액 확인도 같은 코드·문구를 쓴다.
_ASSUMED_SNAPSHOT_DETAIL: Final = (
    "잔액·카드 청구·예산에 사용자 또는 데모 가정이 포함되어 있습니다. 실제 계좌 확인 결과가 아닙니다."
)
_BUDGET_INPUT_INCOMPLETE_DETAIL: Final = (
    "월초 이력 또는 지출 분류가 충분하지 않아 잔여 예산만으로 새 지출을 권하지 않습니다."
)
_PENDING_EXPENSE_LIMIT: Final = 0.05


def _budget_input_incomplete(twin: Twin) -> bool:
    """``Coach.review`` 의 ``uncertain_budget`` 판정을 그대로 따른다. 거래가 없으면 불완전으로 본다."""
    if not twin.transactions or min(row.date for row in twin.transactions) > twin.as_of[:8] + "01":
        return True
    audit = twin.model.get("audit")
    audit = audit if isinstance(audit, dict) else {}
    totals = audit.get("kind_totals_krw")
    pending = audit.get("pending_consumption_krw", 0)
    expense = totals.get("expense", 0) if isinstance(totals, dict) else 0
    if not isinstance(pending, (int, float)) or not isinstance(expense, (int, float)):
        return True
    return expense > 0 and pending / expense > _PENDING_EXPENSE_LIMIT


@final
class EngineAdapter:
    """원 단위 금융 계산을 고정된 FDT에 위임하는 서비스 경계.

    거래 정규화·소유자·계산 자원은 여기서 검증하고, FDT 결과 문서를 보존한다.
    LLM 문구나 화면 표시를 근거로 엔진 금액을 덮어쓰지 않는다.
    """

    def __init__(self, *, cache_capacity: int = 32) -> None:
        """Keep only immutable, revision-bound calculations in this process.

        Stored Twin documents are immutable by convention and every mutation creates a
        new revision. Reusing a parsed Twin therefore avoids re-fitting the same
        observed history for identity, review, and numeric calls without making a
        changed transaction visible through an old cache key. Numeric output is
        additionally keyed by the full request, including its seed and scenario.
        """
        if cache_capacity < 1:
            raise ValueError("cache_capacity_must_be_positive")
        self._cache_capacity = cache_capacity
        self._lock = RLock()
        self._twins: OrderedDict[str, Twin] = OrderedDict()
        self._twin_inflight: dict[str, Future[Twin]] = {}
        self._review_results: OrderedDict[str, str] = OrderedDict()
        self._review_inflight: dict[str, Future[str]] = {}
        self._numeric_results: OrderedDict[str, str] = OrderedDict()
        # A Future lets concurrent identical requests join the leader instead of
        # consuming one simulation slot each. Errors are never cached.
        self._numeric_inflight: dict[str, Future[str]] = {}

    @staticmethod
    def _key(value: JsonValue) -> str:
        """Return a canonical, non-secret cache key for validated JSON only."""
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return sha256(encoded.encode("utf-8")).hexdigest()

    def _remember_twin(self, document: JsonDocument, twin: Twin) -> None:
        key = self._key(document.root)
        with self._lock:
            self._twins[key] = twin
            self._twins.move_to_end(key)
            while len(self._twins) > self._cache_capacity:
                _ = self._twins.popitem(last=False)

    def _twin(self, document: JsonDocument) -> Twin:
        """Load a document once per process and never return a stale revision."""
        key = self._key(document.root)
        with self._lock:
            cached = self._twins.get(key)
            if cached is not None:
                self._twins.move_to_end(key)
                return cached
            pending = self._twin_inflight.get(key)
            leader = pending is None
            if pending is None:
                pending = Future[Twin]()
                self._twin_inflight[key] = pending
        if not leader:
            return pending.result()
        try:
            loaded = Twin.from_dict(document.root)
        except Exception as error:
            pending.set_exception(error)
            raise
        else:
            with self._lock:
                # A Twin created while this parse was running is equivalent to this
                # document. Prefer that already-cached immutable instance.
                cached = self._twins.get(key)
                if cached is not None:
                    self._twins.move_to_end(key)
                    resolved = cached
                else:
                    self._twins[key] = loaded
                    while len(self._twins) > self._cache_capacity:
                        _ = self._twins.popitem(last=False)
                    resolved = loaded
            pending.set_result(resolved)
            return resolved
        finally:
            with self._lock:
                if self._twin_inflight.get(key) is pending:
                    del self._twin_inflight[key]

    def _result_key(self, operation: str, twin: Twin, request: JsonDocument) -> str:
        """Bind a cached result to one immutable Twin, operation, and full request."""
        return self._key(
            {
                "operation": operation,
                "owner": twin.user_id,
                "input_digest": twin.content_digest,
                "request": request.root,
            }
        )

    def _cached_result(
        self,
        *,
        key: str,
        cache: OrderedDict[str, str],
        inflight: dict[str, Future[str]],
        compute: Callable[[], JsonDocument],
    ) -> JsonDocument:
        """Reuse only exact deterministic outputs and let concurrent callers join one leader.

        ``cache`` contains serialized immutable JSON, so each caller receives a newly
        validated document and cannot mutate another request's result. A failed engine
        call is propagated to all joined callers but is never retained for a retry.
        """
        with self._lock:
            cached = cache.get(key)
            if cached is not None:
                cache.move_to_end(key)
                # Decode on every return so callers cannot mutate cached JSON state.
                return JsonDocument.model_validate_json(cached)
            pending = inflight.get(key)
            leader = pending is None
            if pending is None:
                pending = Future[str]()
                inflight[key] = pending
        if not leader:
            return JsonDocument.model_validate_json(pending.result())
        try:
            encoded = compute().model_dump_json()
        except BaseException as error:
            pending.set_exception(error)
            raise
        else:
            with self._lock:
                cache[key] = encoded
                cache.move_to_end(key)
                while len(cache) > self._cache_capacity:
                    _ = cache.popitem(last=False)
            pending.set_result(encoded)
            return JsonDocument.model_validate_json(encoded)
        finally:
            with self._lock:
                if inflight.get(key) is pending:
                    del inflight[key]

    def _cached_review(self, twin: Twin, request: JsonDocument) -> JsonDocument:
        return self._cached_result(
            key=self._result_key("review", twin, request),
            cache=self._review_results,
            inflight=self._review_inflight,
            compute=lambda: JsonDocument.model_validate(Coach(twin).review(request.root)),
        )

    def _cached_numeric(self, twin: Twin, request: JsonDocument) -> JsonDocument:
        return self._cached_result(
            key=self._result_key("numeric", twin, request),
            cache=self._numeric_results,
            inflight=self._numeric_inflight,
            compute=lambda: JsonDocument.model_validate(Engine(twin).run(request.root)),
        )

    def create(self, request: Bootstrap, owner: str) -> JsonDocument:
        twin = Twin(
            [normalized_transaction(row) for row in request.transactions],
            request.as_of.isoformat(),
            snapshot=request.snapshot.root if request.snapshot else None,
        )
        if twin.user_id != owner or any(row.user_id != owner for row in twin.transactions):
            raise ServiceError("user_mismatch", 403)
        document = JsonDocument.model_validate(twin.to_dict())
        self._remember_twin(document, twin)
        return document

    def update(
        self, document: JsonDocument, event: JsonDocument, snapshot_event: JsonDocument | None = None
    ) -> JsonDocument:
        if event.root.get("type") == "transaction":
            raw = event.root.get("transaction")
            if isinstance(raw, dict):
                _ = normalized_transaction(JsonDocument(raw))
        events = [event.root]
        if snapshot_event is not None:
            if snapshot_event.root.get("type") != "snapshot":
                raise ServiceError("companion_event_must_be_snapshot")
            events.append(snapshot_event.root)
        updated = apply_events(self._twin(document), events)
        result = JsonDocument.model_validate(updated.to_dict())
        self._remember_twin(result, updated)
        return result

    def identity(self, document: JsonDocument) -> TwinIdentity:
        twin = self._twin(document)
        return TwinIdentity(
            user_id=twin.user_id,
            twin_id=twin.twin_id,
            revision=twin.revision,
            input_digest=twin.content_digest,
            as_of=twin.as_of,
        )

    def transactions(self, document: JsonDocument) -> tuple[TransactionView, ...]:
        return tuple(
            TransactionView(
                id=row.id,
                source=row.source,
                date=row.date,
                time=row.time,
                envelope=row.envelope,
                amount_krw=row.amount_krw,
                budget_amount_krw=row.budget_amount_krw,
                kind=row.kind,
                active=row.active,
                pending=row.pending,
            )
            for row in self._twin(document).transactions
        )

    def observation_audit(self, document: JsonDocument) -> JsonDocument:
        return JsonDocument.model_validate(self._twin(document).model["audit"])

    def review(self, document: JsonDocument, request: JsonDocument) -> JsonDocument:
        return self._cached_review(self._twin(document), request)

    def balance(self, document: JsonDocument, request: JsonDocument) -> JsonDocument:
        """현재 봉투 잔액 확인을 미래 경로 없이 장부 사실만으로 답한다.

        ``Coach.review`` 는 항상 몬테카를로 예측을 돌리고 ``next_action``·경고 대부분을
        그 미래 경로에서 만든다. "지금 얼마 남았어"에 그 값을 현재 사실처럼 보이면 안 되므로
        엔진의 결정형 ``observed_budgets`` 와, 시뮬레이션 전에 붙는 입력 점검 경고
        (가정 스냅숏·과거 기준 재생·예산 입력 불완전)만 같은 코드·문구로 쓴다.
        """
        twin = self._twin(document)
        snapshot = twin.snapshot or {}
        on_date = request.root.get("on_date")
        missing: list[JsonValue] = list(twin.cash_requirements())
        warnings: list[JsonValue] = []
        if snapshot.get("source") == "USER_ASSUMPTION":
            warnings.append(
                {"code": "ASSUMED_SNAPSHOT", "severity": "user", "detail": _ASSUMED_SNAPSHOT_DETAIL}
            )
        if request.root.get("replay"):
            warnings.append(
                {
                    "code": "HISTORICAL_REPLAY",
                    "severity": "user",
                    "detail": f"{on_date} 자료 기준의 검토입니다. "
                    "오늘의 사용 가능 금액으로 안내하지 않습니다.",
                }
            )
        # 기준일이 자료와 다르면 review 도 갱신부터 요구하고 예산 입력 점검까지 가지 않는다.
        current = on_date == twin.as_of
        if current and _budget_input_incomplete(twin):
            warnings.append(
                {
                    "code": "BUDGET_INPUT_INCOMPLETE",
                    "severity": "user",
                    "detail": _BUDGET_INPUT_INCOMPLETE_DETAIL,
                }
            )
        return JsonDocument.model_validate(
            {
                "operation": "balance_check",
                "twin_id": twin.twin_id,
                "revision": twin.revision,
                "input_digest": twin.content_digest,
                "as_of": twin.as_of,
                "on_date": on_date,
                # review 와 같은 판정: 스냅숏이 낡았거나(dirty·기준일 불일치) 계좌·카드 자료가
                # 빠지면 needs_data 이고, 이때 봉투 구간 조언(근접·여유)은 켜지지 않는다.
                "status": "ready" if current and not missing else "needs_data",
                "missing_cash_inputs": missing,
                "observed_budgets": observed_budgets(twin),
                "projection": None,
                "comparison": None,
                "next_action": None,
                "warnings": warnings,
                "executed": False,
            }
        )

    def numeric(self, document: JsonDocument, request: JsonDocument) -> JsonDocument:
        try:
            admit(request)
        except ValidationError:
            raise ServiceError("invalid_numeric_request") from None
        return self._cached_numeric(self._twin(document), request)

    def chart_numeric(
        self, document: JsonDocument, request: JsonDocument
    ) -> tuple[JsonDocument, DailyForecast]:
        """한 번의 예측에서 누적 P50 결과와 같은 경로의 일별 평균을 함께 얻는다.

        잘못된 사용자 요청은 422, 엔진의 일별 결과 누락은 계약 위반인 502다.
        일별 막대를 만들기 위해 다른 난수 경로로 예측을 다시 실행하지 않는다.
        """
        try:
            admit(request)
        except ValidationError:
            raise ServiceError("invalid_numeric_request") from None
        if request.root.get("mode") != "forecast":
            raise ServiceError("chart_requires_forecast")
        engine = ChartEngine(self._twin(document))
        numeric = JsonDocument.model_validate(engine.run(request.root))
        if engine.daily is None:
            raise ServiceError("chart_daily_forecast_missing", 502)
        return numeric, engine.daily
