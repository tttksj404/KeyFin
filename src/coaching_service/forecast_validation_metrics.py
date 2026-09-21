"""Transparent point and central-80%-interval errors; no customer-accuracy gate."""

from coaching_service.errors import ServiceError
from coaching_service.forecast_validation_contracts import EnvelopeMetric, MetricValues, Quantiles, Settlement
from coaching_service.forecast_validation_values import ENVELOPES


def calculate_metrics(
    forecasts: tuple[Quantiles, ...], actuals: tuple[int, ...], baselines: tuple[float, ...]
) -> MetricValues:
    """WIS uses one central 80% interval and the median, with denominator K+0.5.

    Positive bias means overprediction. WAPE is a ratio, not a percentage string;
    it is absent when the sum of actual consumption is zero. Baselines are point
    forecasts and consequently have no fabricated prediction interval or WIS.
    """
    n = len(forecasts)
    if not n or len(actuals) != n or len(baselines) != n:
        raise ValueError("nonempty_aligned_samples_required")
    errors = tuple(pred.p50 - actual for pred, actual in zip(forecasts, actuals, strict=True))
    baseline_errors = tuple(base - actual for base, actual in zip(baselines, actuals, strict=True))
    absolute_sum = sum(abs(error) for error in errors)
    baseline_absolute = sum(abs(error) for error in baseline_errors)
    actual_sum = sum(actuals)
    widths = tuple(pred.p90 - pred.p10 for pred in forecasts)
    scores = tuple(
        (
            0.5 * abs(pred.p50 - actual)
            + 0.1 * (pred.p90 - pred.p10 + 10 * max(pred.p10 - actual, actual - pred.p90, 0))
        )
        / 1.5
        for pred, actual in zip(forecasts, actuals, strict=True)
    )
    return MetricValues(
        sample_count=n,
        mae_krw=absolute_sum / n,
        wape=absolute_sum / actual_sum if actual_sum else None,
        bias_krw=sum(errors) / n,
        wis80_krw=sum(scores) / n,
        coverage80=sum(p.p10 <= y <= p.p90 for p, y in zip(forecasts, actuals, strict=True)) / n,
        mean_interval_width_krw=sum(widths) / n,
        baseline_mae_krw=baseline_absolute / n,
        baseline_wape=baseline_absolute / actual_sum if actual_sum else None,
        baseline_bias_krw=sum(baseline_errors) / n,
    )


def envelope_metrics(settlements: tuple[Settlement, ...]) -> tuple[EnvelopeMetric, ...] | None:
    """예측과 기준 모델의 오차는 같은 미래 기간만 비교한다. 월 예산 사용률은 합치지 않는다."""
    if all(row.registration.monthly is None and row.monthly is None for row in settlements):
        return None
    if any(row.registration.monthly is None or row.monthly is None for row in settlements):
        raise ServiceError("validation_incomparable_monthly_cohort")
    result: list[EnvelopeMetric] = []
    for envelope in ENVELOPES:
        forecasts = tuple(
            item for row in settlements if row.registration.monthly is not None
            for item in row.registration.monthly.forecasts if item.envelope == envelope
        )
        actuals = tuple(
            item.future_actual.consumption_krw for row in settlements if row.monthly is not None
            for item in row.monthly.comparisons if item.envelope == envelope
        )
        result.append(EnvelopeMetric(
            envelope=envelope,
            values=calculate_metrics(
                tuple(row.future_prediction for row in forecasts), actuals,
                tuple(row.baseline_future_krw for row in forecasts),
            ),
        ))
    return tuple(result)
