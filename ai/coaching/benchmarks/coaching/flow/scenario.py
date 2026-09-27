"""One continuous session across ledger mutations; expected money comes from inputs."""

import calendar
from datetime import timedelta

from benchmarks.coaching.flow.client import Flow
from benchmarks.coaching.flow.contracts import Checkpoint, SavedAnswer
from benchmarks.coaching.flow.fixtures import (
    FIRST_PAYMENT,
    OPENING_CASH,
    OPENING_ENVELOPE,
    SECOND_PAYMENT,
    Scenario,
    expected_month_spend,
)
from benchmarks.coaching.flow.references import exact_references
from coaching_service.chat_answers import ChatAnswer
from coaching_service.schemas import (
    Coaching,
    EventResult,
    JsonDocument,
    NotificationList,
    Session,
)


def saved_answer(flow: Flow, stage: str, body: JsonDocument) -> SavedAnswer:
    if "receipt" in body.root:
        answer = Coaching.model_validate(body.root)
        flow.observe(stage, answer)
        path = "/v1/coaching/" + answer.id
    else:
        answer = ChatAnswer.model_validate(body.root)
        flow.observe(stage, answer)
        path = "/v1/answers/" + answer.id
    stored = flow.request(stage + "-get", "GET", path)
    flow.check(stage + ":stored_exact", passed=stored == body)
    return SavedAnswer(path=path, body=body)


def check_forecast(flow: Flow, stage: str, body: JsonDocument, data: Scenario, mode: str) -> Coaching:
    answer = Coaching.model_validate(body.root)
    period = answer.receipt.period
    request = answer.receipt.numeric_request
    result = answer.receipt.numeric_result
    expected_end = data.day.replace(day=calendar.monthrange(data.day.year, data.day.month)[1])
    flow.check(
        stage + ":calendar",
        passed=(
            period is not None
            and period.reference_date == data.day
            and period.forecast_start == data.day + timedelta(days=1)
            and period.forecast_end == expected_end
            and period.source == "question"
        ),
    )
    flow.check(stage + ":numeric_mode", passed=request is not None and request.root.get("mode") == mode)
    flow.check(stage + ":numeric_ready", passed=result is not None and result.root.get("status") == "ok")
    # The checked FDT receipt is sufficient for a numeric response. A model
    # explanation remains valid when present, but a deterministic follow-up is
    # equally valid only when it records normal template provenance rather than
    # disguising a failure as a successful answer.
    wording_accepted = (
        answer.wording_source == "llm" and answer.fallback_reason is None
    ) or (
        answer.wording_source == "template"
        and answer.model == "not_called"
        and answer.fallback_reason is None
    )
    flow.check(stage + ":wording_accepted", passed=wording_accepted)
    return answer


def check_history(flow: Flow, stage: str, body: JsonDocument, expected: int) -> None:
    answer = ChatAnswer.model_validate(body.root)
    spending = JsonDocument.model_validate(answer.evidence.root.get("spending"))
    flow.check(
        stage + ":observed_spend",
        passed=answer.answer_type == "spending_history"
        and answer.status == "answered"
        and spending.root.get("total_krw") == expected,
    )


def before_restart(flow: Flow, data: Scenario) -> Checkpoint:
    """Execute payment, ack, conversation, additional spending, refund, and follow-up."""
    _ = flow.request(
        "bootstrap", "POST", "/v1/twin", JsonDocument.model_validate_json(data.bootstrap.model_dump_json())
    )
    payment_request = data.event(0, "first", FIRST_PAYMENT, FIRST_PAYMENT)
    paid_doc = flow.request("first-payment", "POST", "/v1/events", payment_request)
    paid = EventResult.model_validate(paid_doc.root)
    flow.check("payment:p0", passed=paid.detection == "p0_half_balance")
    flow.check(
        "payment:independent_balance",
        passed=paid.payment is not None
        and paid.payment.balance_before_krw == OPENING_ENVELOPE
        and paid.payment.balance_after_krw == OPENING_ENVELOPE - FIRST_PAYMENT,
    )
    if paid.coaching is None:
        raise RuntimeError("expected_payment_coaching")
    original = JsonDocument.model_validate_json(paid.coaching.model_dump_json())
    answers = [saved_answer(flow, "payment", original)]
    notices = NotificationList.model_validate(flow.request("notifications", "GET", "/v1/notifications").root)
    flow.check("notifications:one", passed=len(notices.items) == 1)
    notice = notices.items[0]
    flow.check("notifications:coaching", passed=notice.coaching_id == paid.coaching.id)
    ack_path = "/v1/notifications/" + notice.event_id + "/ack"
    ack = flow.request("ack", "POST", ack_path)
    flow.check("notifications:ack", passed=ack.root.get("acknowledged") is True)
    session = Session.model_validate(
        flow.request("session", "POST", "/v1/sessions", JsonDocument({"coaching_id": paid.coaching.id})).root
    )
    for stage, question in (
        ("concept", "복리가 뭐야?"),
        ("forecast-before", "이번 달 말까지 잔액 예측해줘"),
        ("risk-before", "이번 달 위험을 알려줘"),
    ):
        body = flow.turn(stage, session.id, question)
        answers.append(saved_answer(flow, stage, body))
        if stage == "concept":
            concept = ChatAnswer.model_validate(body.root)
            flow.check(
                "concept:answered",
                passed=concept.status == "answered"
                and concept.answer_type == "finance_education"
                and concept.wording_source == "llm",
            )
        else:
            _ = check_forecast(
                flow, stage, body, data, "forecast" if stage.startswith("forecast") else "risk"
            )
    second = EventResult.model_validate(
        flow.request(
            "second-payment",
            "POST",
            "/v1/events",
            data.event(paid.identity.revision, "second", SECOND_PAYMENT, FIRST_PAYMENT + SECOND_PAYMENT),
        ).root
    )
    flow.check(
        "second:independent_balance",
        passed=second.payment is not None
        and second.payment.balance_before_krw == OPENING_ENVELOPE - FIRST_PAYMENT
        and second.payment.balance_after_krw == OPENING_ENVELOPE - FIRST_PAYMENT - SECOND_PAYMENT,
    )
    history = flow.turn("history-before-cancel", session.id, "이번 달 내 지출은 얼마야?")
    answers.append(saved_answer(flow, "history-before-cancel", history))
    check_history(flow, "history-before-cancel", history, expected_month_spend(data, canceled=False))
    canceled = EventResult.model_validate(
        flow.request("cancel", "POST", "/v1/events", data.cancel(second.identity.revision)).root
    )
    flow.check("cancel:refunded", passed=canceled.detection == "cancellation_refunded")
    history = flow.turn("history-after-cancel", session.id, "이번 달 내 지출은 얼마야?")
    answers.append(saved_answer(flow, "history-after-cancel", history))
    check_history(flow, "history-after-cancel", history, expected_month_spend(data, canceled=True))
    for stage, question, mode in (
        ("forecast-after", "이번 달 말까지 잔액 예측해줘", "forecast"),
        ("risk-after", "취소한 결제 이후 이번 달 위험을 알려줘", "risk"),
    ):
        body = flow.turn(stage, session.id, question)
        answers.append(saved_answer(flow, stage, body))
        answer = check_forecast(flow, stage, body, data, mode)
        flow.check(
            stage + ":original_canceled",
            passed=answer.receipt.historical is not None
            and answer.receipt.historical.transaction_status == "canceled"
            and answer.receipt.payment is None,
        )
        flow.check(
            stage + ":current_envelope",
            passed=any(
                row.envelope == "기타" and row.balance_krw == OPENING_ENVELOPE - SECOND_PAYMENT
                for row in answer.receipt.current_envelopes
            ),
        )
    twin = flow.request("twin-before-restart", "GET", "/v1/twin")
    snapshot = JsonDocument.model_validate(twin.root["snapshot"])
    flow.check(
        "snapshot:independent_balance",
        passed=snapshot.root.get("accounts")
        == [{"account_id": "cash-account", "balance_krw": OPENING_CASH - SECOND_PAYMENT}],
    )
    current_session = flow.request("session-before-restart", "GET", "/v1/sessions/" + session.id)
    flow.check("session:seven_turns", passed=len(Session.model_validate(current_session.root).messages) == 14)
    flow.check(
        "session:answer_references",
        passed=exact_references(current_session, tuple(a.body for a in answers[1:])),
    )
    pending = flow.request("notifications-before-restart", "GET", "/v1/notifications")
    remaining = NotificationList.model_validate(pending.root)
    flow.check(
        "notifications:first_remains_acknowledged",
        passed=all(row.event_id != notice.event_id for row in remaining.items),
    )
    return Checkpoint(
        session_id=session.id,
        session=current_session,
        twin=twin,
        answers=tuple(answers),
        payment_request=payment_request,
        payment_response=paid_doc,
        ack_path=ack_path,
        ack=ack,
        pending_notifications=pending,
        last_question="취소한 결제 이후 이번 달 위험을 알려줘",
        last_stage="risk-after",
        last_response=body,
    )


def after_restart(flow: Flow, saved: Checkpoint) -> None:
    """Check saved payload equality after the original API process has exited."""
    for index, answer in enumerate(saved.answers):
        body = flow.request(f"restart-answer-{index}", "GET", answer.path)
        flow.check(f"restart:answer-{index}-exact", passed=body == answer.body)
    session_path = "/v1/sessions/" + saved.session_id
    restored = flow.request("restart-session", "GET", session_path)
    flow.check("restart:session_exact", passed=restored == saved.session)
    flow.check(
        "restart:answer_references",
        passed=exact_references(restored, tuple(a.body for a in saved.answers[1:])),
    )
    flow.check("restart:twin_exact", passed=flow.request("restart-twin", "GET", "/v1/twin") == saved.twin)
    pending = flow.request("restart-notifications", "GET", "/v1/notifications")
    flow.check("restart:pending_notifications_exact", passed=pending == saved.pending_notifications)
    repeated_ack = flow.request("restart-ack", "POST", saved.ack_path, key="ack")
    flow.check("restart:ack_idempotent", passed=repeated_ack == saved.ack)
    repeated_payment = flow.request(
        "restart-payment", "POST", "/v1/events", saved.payment_request, key="first-payment"
    )
    flow.check("restart:payment_idempotent", passed=repeated_payment == saved.payment_response)
    repeated_turn = flow.request(
        "restart-turn",
        "POST",
        session_path + "/messages",
        JsonDocument({"question": saved.last_question}),
        key=saved.last_stage,
    )
    flow.check("restart:turn_idempotent", passed=repeated_turn == saved.last_response)
    flow.check(
        "restart:replay_twin_unchanged", passed=flow.request("replay-twin", "GET", "/v1/twin") == saved.twin
    )
    flow.check(
        "restart:replay_session_unchanged",
        passed=flow.request("replay-session", "GET", session_path) == saved.session,
    )
