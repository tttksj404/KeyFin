from datetime import date

import pytest

from coaching_service.chart_contract import BudgetPeriod, DailyForecast, DailyPoint, PurchaseChange
from coaching_service.chart_projection import ENVELOPES, Budgets, ChartInputs, project_chart
from coaching_service.chart_rendering import render_chart
from coaching_service.errors import ServiceError
from coaching_service.schemas import JsonDocument, TransactionView


def transaction(
    identity: str, amount: int, *, kind: str = "expense", pending: bool = False, active: bool = True
) -> TransactionView:
    return TransactionView(
        id=identity,
        source="SEED",
        date="2026-09-29",
        time="12:00:00",
        envelope="외식",
        amount_krw=amount,
        budget_amount_krw=amount,
        kind=kind,
        active=active,
        pending=pending,
    )


def inputs() -> ChartInputs:
    return ChartInputs(
        id="independent-arithmetic",
        question="예상 소비",
        period=BudgetPeriod(
            period_start=date(2026, 9, 1), as_of=date(2026, 9, 29), horizon_end=date(2026, 9, 30)
        ),
        transactions=(
            transaction("purchase", 100),
            transaction("pending", 30, pending=True),
            transaction("settlement", 100, kind="card_payment"),
            transaction("rent", 700, kind="fixed_expense"),
            transaction("canceled", 200, active=False),
        ),
        budgets=Budgets(budgets=dict.fromkeys(ENVELOPES, 1000)),
        paths=400,
        seed=42,
    )


def numeric(*, terminal: int = 100) -> JsonDocument:
    return JsonDocument.model_validate(
        {
            "status": "ok",
            "metrics": {"total_expense_p50_krw": {"value": 100}},
            "datasets": {
                "envelopes": [{"envelope": name, "p50_krw": 20} for name in ENVELOPES],
                "projection": [
                    {"date": "2026-09-29", "cumulative_expense_p50_krw": 0},
                    {"date": "2026-09-30", "cumulative_expense_p50_krw": terminal},
                ],
            },
        }
    )


def predicted_daily() -> DailyForecast:
    return DailyForecast(points=(DailyPoint(date=date(2026, 9, 30), amounts_krw=(3, 0, 2, 0, 0, 0, 0)),))


@pytest.mark.parametrize("extra", [0, 1])
def test_combined_observed_and_forecast_respect_safe_integer_limit(extra: int) -> None:
    limit = 9007199254740991
    future = limit - 130 + extra
    result = numeric(terminal=future)
    result.root["metrics"] = {"total_expense_p50_krw": {"value": future}}
    if extra:
        with pytest.raises(ServiceError, match="chart_money_range_limit"):
            project_chart(inputs(), result, predicted_daily())
    else:
        assert project_chart(inputs(), result, predicted_daily()).total_forecast == limit


def test_joint_total_preserved_without_double_counting_settlement_or_fixed_expense() -> None:
    # Given independently specified purchase totals and a joint P50 distinct from marginal P50s.
    source = inputs()
    # When the chart is projected.
    chart = project_chart(source, numeric(), predicted_daily())
    # Then current=100+30, joint future=100; settlement/canceled/fixed rows add nothing.
    assert chart.total_current == 130
    assert chart.unallocated_current == 30
    assert chart.total_forecast == 230
    assert chart.categories[0].current == 100
    assert chart.categories[0].forecast == 120
    assert sum(row.forecast for row in chart.categories) == 240
    assert chart.balance.history[-1].value_krw == 130
    assert chart.balance.forecast[-1].p50_krw == 230
    assert chart.balance.daily[-1] == predicted_daily().points[0]
    assert chart.balance.daily[-2].amounts_krw == (100, 0, 0, 0, 0, 0, 0)


def test_terminal_disagreement_is_rejected() -> None:
    # Given a corrupted final projection that disagrees with the engine metric.
    # When projecting it, then reject instead of drawing an inconsistent chart.
    with pytest.raises(ServiceError, match="chart_terminal_contract_mismatch"):
        project_chart(inputs(), numeric(terminal=101))


def test_missing_budgets_remain_unknown() -> None:
    # Given a missing budget snapshot.
    source = inputs().model_copy(update={"budgets": Budgets()})
    # When projected, then no zero budget or percentage is invented.
    chart = project_chart(source, numeric(), predicted_daily())
    assert chart.total_budget is None
    assert all(row.budget is None for row in chart.categories)


def test_html_keeps_question_as_data_and_never_executable_markup() -> None:
    # Given a malicious question string crossing the HTML boundary.
    chart = project_chart(inputs(), numeric(), predicted_daily()).model_copy(
        update={"question": "</script><script>alert(1)</script>"}
    )
    # When rendered, then the script boundary cannot be closed by the data.
    html = render_chart(chart)
    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script>\\u003cscript>alert(1)\\u003c/script>" in html


# --- Feature #1: purchase what-if deterministic overlay ---


def purchase_inputs() -> ChartInputs:
    return ChartInputs(
        id="purchase-overlay",
        question="이 구매를 하면 어떻게 되나요",
        period=BudgetPeriod(
            period_start=date(2026, 9, 1), as_of=date(2026, 9, 27), horizon_end=date(2026, 9, 30)
        ),
        transactions=(
            TransactionView(
                id="obs",
                source="SEED",
                date="2026-09-27",
                time="12:00:00",
                envelope="외식",
                amount_krw=100,
                budget_amount_krw=100,
                kind="expense",
                active=True,
                pending=False,
            ),
        ),
        budgets=Budgets(budgets=dict.fromkeys(ENVELOPES, 1000)),
        paths=400,
        seed=42,
    )


def purchase_numeric() -> JsonDocument:
    return JsonDocument.model_validate(
        {
            "status": "ok",
            "metrics": {"total_expense_p50_krw": {"value": 30}},
            "datasets": {
                "envelopes": [{"envelope": name, "p50_krw": 5} for name in ENVELOPES],
                "projection": [
                    {"date": "2026-09-27", "cumulative_expense_p50_krw": 0},
                    {"date": "2026-09-28", "cumulative_expense_p50_krw": 10},
                    {"date": "2026-09-29", "cumulative_expense_p50_krw": 20},
                    {"date": "2026-09-30", "cumulative_expense_p50_krw": 30},
                ],
            },
        }
    )


def purchase_daily() -> DailyForecast:
    return DailyForecast(
        points=tuple(
            DailyPoint(date=d, amounts_krw=(1, 0, 0, 0, 0, 0, 0))
            for d in (date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30))
        )
    )


def test_planned_curve_is_baseline_plus_amount_from_on_date() -> None:
    # Given a planned 50원 purchase on 09-29 over a baseline cumulative 100→110→120→130.
    purchase = PurchaseChange(envelope="외식", amount_krw=50, on_date=date(2026, 9, 29))
    # When the deterministic overlay is projected.
    chart = project_chart(purchase_inputs(), purchase_numeric(), purchase_daily(), purchase)
    # Then the muted baseline keeps the engine curve unchanged.
    assert [p.p50_krw for p in chart.balance.baseline] == [100, 110, 120, 130]
    # And the primary planned curve shifts by 50 only on/after the purchase date (anchor 09-27 intact).
    assert [p.p50_krw for p in chart.balance.forecast] == [100, 110, 170, 180]
    # And the terminal/total move by exactly the amount; the envelope category bumps by the amount.
    assert chart.total_forecast == 180
    assert chart.balance.terminal.p50_krw == 180
    assert chart.categories[0].id == "외식"
    assert chart.categories[0].forecast == 100 + 5 + 50
    # And the planned curve stays monotone non-decreasing.
    planned = [p.p50_krw for p in chart.balance.forecast]
    assert planned == sorted(planned)
    # And the applied purchase and the expense-lens caveat ride on meta.
    assert chart.meta.purchase == purchase
    assert chart.meta.purchase_note is not None
    assert "계좌 잔액" in chart.meta.purchase_note


def test_purchase_on_horizon_end_shifts_only_the_terminal() -> None:
    purchase = PurchaseChange(envelope="교통비", amount_krw=40, on_date=date(2026, 9, 30))
    chart = project_chart(purchase_inputs(), purchase_numeric(), purchase_daily(), purchase)
    assert [p.p50_krw for p in chart.balance.forecast] == [100, 110, 120, 170]
    assert chart.total_forecast == 170


@pytest.mark.parametrize("on_date", [date(2026, 9, 27), date(2026, 9, 26), date(2026, 10, 1)])
def test_purchase_outside_future_budget_period_is_rejected(on_date: date) -> None:
    purchase = PurchaseChange(envelope="외식", amount_krw=10, on_date=on_date)
    with pytest.raises(ServiceError, match="chart_purchase_out_of_period"):
        project_chart(purchase_inputs(), purchase_numeric(), purchase_daily(), purchase)


def test_purchase_with_unknown_envelope_is_rejected() -> None:
    purchase = PurchaseChange(envelope="여행", amount_krw=10, on_date=date(2026, 9, 29))
    with pytest.raises(ServiceError, match="chart_purchase_envelope_unknown"):
        project_chart(purchase_inputs(), purchase_numeric(), purchase_daily(), purchase)


def test_purchase_on_closed_period_is_rejected() -> None:
    # Given a closed period (no forecast to overlay).
    closed = purchase_inputs().model_copy(
        update={
            "period": BudgetPeriod(
                period_start=date(2026, 9, 1), as_of=date(2026, 9, 30), horizon_end=date(2026, 9, 30)
            )
        }
    )
    purchase = PurchaseChange(envelope="외식", amount_krw=10, on_date=date(2026, 9, 30))
    with pytest.raises(ServiceError, match="chart_purchase_period_closed"):
        project_chart(closed, None, None, purchase)


def test_purchase_overlay_reuses_baseline_without_a_second_simulation() -> None:
    # Given the same engine numeric result projected with and without a purchase.
    plain = project_chart(purchase_inputs(), purchase_numeric(), purchase_daily())
    purchase = PurchaseChange(envelope="외식", amount_krw=50, on_date=date(2026, 9, 29))
    overlaid = project_chart(purchase_inputs(), purchase_numeric(), purchase_daily(), purchase)
    # Then the overlay's muted baseline is exactly the plain forecast: no re-simulation, pure shift.
    assert overlaid.balance.baseline == plain.balance.forecast
    assert plain.balance.baseline == ()
    assert overlaid.balance.daily == plain.balance.daily


@pytest.mark.parametrize("days", [None, (), (date(2026, 9, 29),), (date(2026, 10, 1),)])
def test_missing_or_wrong_future_dates_fail_closed(days: tuple[date, ...] | None) -> None:
    prediction = (
        None
        if days is None
        else DailyForecast(points=tuple(DailyPoint(date=d, amounts_krw=(0,) * 7) for d in days))
    )
    with pytest.raises(ServiceError, match="chart_daily_projection_mismatch"):
        project_chart(inputs(), numeric(), prediction)
