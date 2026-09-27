"""The budget-period bar axis caps at 120% so one extreme envelope cannot hide the rest."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_CHART = Path(__file__).resolve().parents[1] / "vendor" / "keyfin_chart" / "keyfin-chart.js"
_NODE = shutil.which("node")

_SCRIPT = """
const K = require(process.argv[1]);
const input = {categories: [
  {id: 'a', label: 'etc', budget: 50000, current: 30000, forecast: 1207000},
  {id: 'b', label: 'food', budget: 100000, current: 60000, forecast: 100000},
  {id: 'c', label: 'shop', budget: 100000, current: 40000, forecast: 89000},
]};
const out = {};
for (const [name, opt] of [['linear', {scale: 'linear'}], ['wide', {scale: 'linear', maxScale: 2}]]) {
  const m = K.model(input, {}, opt);
  out[name] = {maxRatio: m.maxRatio, trackWidth: m.trackWidth,
    rows: m.rows.map(r => ({label: r.label, width: r.forecastBar.width,
      percent: Math.round(r.forecastBar.percent), clipped: r.forecastBar.clipped}))};
}
try { K.model(input, {}, {scale: 'linear', maxScale: 0.5}); out.invalid = 'accepted'; }
catch (e) { out.invalid = e.constructor.name; }
process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(_NODE is None, reason="node is not installed")
def test_linear_budget_bars_cap_at_120_percent_and_keep_real_labels() -> None:
    assert _NODE is not None
    completed = subprocess.run(  # noqa: S603 - fixed local node binary and vendored script.
        [_NODE, "-e", _SCRIPT, str(_CHART)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    out = json.loads(completed.stdout)
    linear = out["linear"]
    # A 2414% envelope no longer stretches the axis to 24x: the axis stops at 120%.
    assert linear["maxRatio"] == pytest.approx(1.2)
    extreme, full, most = linear["rows"]
    assert extreme == {**extreme, "percent": 2414, "clipped": True}
    assert extreme["width"] == pytest.approx(linear["trackWidth"])
    # 100% and 89% stay clearly visible (≈83% and ≈74% of the track), not a few pixels.
    assert full["width"] / linear["trackWidth"] == pytest.approx(1 / 1.2, rel=1e-3)
    assert most["width"] / linear["trackWidth"] == pytest.approx(0.89 / 1.2, rel=1e-3)
    assert not full["clipped"]
    assert not most["clipped"]
    # The cap is configurable, and a cap below 100% is rejected.
    assert out["wide"]["maxRatio"] == pytest.approx(2)
    assert out["invalid"] == "TypeError"
