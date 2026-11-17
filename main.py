"""Forecast GTA VI's launch-day Twitch viewers hour by hour.

Reference-class forecaster (Python 3.13, standard library only, no network).

Model
-----
The program reads one case: hour 1's Twitch viewer print p1 for a game's
release day, plus `comparables` -- past big launches' hourly curves from
14 days before to 3 days after their release day.  For each hour h = 2..24
it fits, over the comparables with a complete release-day curve, the
regression

    ln(y_h / y_1) = a_h + b_h * ln(p1 / 100_000)

where y_1 is a comparable's own hour-1 print.  The slope b_h is strongly
negative at peak hours (about -0.94 at h=20): a launch whose hour 1 is
already huge has little headroom left, while a launch whose hour 1 is
near zero (it had not unlocked anywhere yet at 00:00 UTC) can rise
hundreds of times.  Equivalently the day's peak absolute audience is
almost independent of the hour-1 print.

Two guards keep the regression honest on the final case:

* FLOOR -- a rolling-midnight floor on the median ratio.  GTA VI unlocks
  at midnight local time, region by region (New Zealand 11:00Z Nov 18,
  central Europe 23:00Z, UK 00:00Z, US East 05:00Z, US Pacific 08:00Z),
  exactly like the four practice launches.  In every one of those the
  audience rose after hour 1: the smallest peak-hour ratio among them was
  1.61-1.71x.  The raw regression, extrapolated to a very large hour-1
  print, would predict a *fall* to ~0.25x at peak hours, because the
  largest hour-1 comparables are simultaneous global launches (Cyberpunk
  2077, Elden Ring) whose hour 1 already was the peak.  The floor is
  0.85x the smallest per-hour ratio among the four practice launches, so
  the forecast never predicts less than a rolling-midnight launch's
  observed minimum rise.  It binds only for large hour-1 prints.
* Spread -- each hour's log-spread s_h is 0.7x the regression's residual
  standard deviation across comparables, clamped to [0.25, 1.0].  The
  0.7 factor and the floor were chosen on leave-one-out cross-validation
  over the comparables, not on the four practice cases alone; see
  DATA_ANALYSIS.md.

Quantiles: q_tau(h) = p1 * r_h * exp(z_tau * s_h), z the standard normal
quantiles (-1.645, -0.674, 0, 0.674, 1.645), rounded half-up to 2 decimals.

If fewer than 5 comparables have a complete release-day curve, the fit
falls back to hardcoded intercepts (the regression's a_h at p1 = 100k,
measured on the kit's 37 complete comparables) with the same floor and
s_h = 0.6.

I/O contract: read every <id>.in in $MAKEFUN_INPUT_DIR (else /input),
write <id>.out to $MAKEFUN_OUTPUT_DIR (else /output) as
{"hours": [{"hour": h, "q": [q05, q25, q50, q75, q95]}]} for h = 2..24.
Deterministic: no randomness, no time, no network.
"""

import datetime
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# Reference scale for the regression: log-ratio is modelled against
# ln(p1 / 100_000), so a_h is the log median ratio for a 100k hour 1.
REF = 100_000.0
# Spread calibration (see DATA_ANALYSIS.md).
SPREAD_MULT = 0.7
SPREAD_MIN = 0.25
SPREAD_MAX = 1.0
MIN_CURVES = 5

# Rolling-midnight floor on the median ratio r_h: 0.85x the smallest
# ratio at that hour among the four practice launches (Wolverine, RDR2,
# God of War Ragnarok, Spider-Man 2).  Hours 2..24.
FLOOR = {
    2: 0.57, 3: 0.37, 4: 0.36, 5: 0.49, 6: 0.89, 7: 0.86,
    8: 0.78, 9: 0.62, 10: 0.59, 11: 0.51, 12: 0.31, 13: 0.49,
    14: 0.69, 15: 0.86, 16: 0.98, 17: 1.19, 18: 1.37, 19: 1.40,
    20: 1.45, 21: 1.40, 22: 1.37, 23: 1.30, 24: 1.21,
}

# Fallback intercepts a_h (log median ratio at p1 = 100k), measured on the
# kit's 37 complete comparable curves.  Used only if < 5 comparables in
# the case have a complete release-day curve.
FALLBACK_A = {
    2: -0.059, 3: -0.224, 4: -0.306, 5: -0.274, 6: -0.215, 7: -0.213,
    8: -0.180, 9: -0.190, 10: -0.175, 11: -0.140, 12: -0.070, 13: 0.087,
    14: 0.222, 15: 0.356, 16: 0.480, 17: 0.580, 18: 0.668, 19: 0.760,
    20: 0.783, 21: 0.798, 22: 0.766, 23: 0.700, 24: 0.583,
}
FALLBACK_SPREAD = 0.6


def round2(x: float):
    """Round half up to 2 decimals; whole numbers come back as ints."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value == int(value) else value


def release_day_curve(comp: dict):
    """A comparable's 24 hourly viewer counts for its release day (UTC).

    Returns a list of 24 positive numbers, or None if any hour is
    missing or non-positive (e.g. the GTA VI pre-release comparable,
    which has no release day yet).
    """
    day_start = comp.get("day_start")
    hourly = comp.get("hourly")
    if not day_start or not hourly:
        return None
    by_from = {}
    for row in hourly:
        try:
            by_from[row["from"]] = float(row["viewers"])
        except (KeyError, TypeError, ValueError):
            continue
    # day_start looks like "2022-02-25T00:00:00Z"; hours are +0..23h.
    base = day_start[:10]  # YYYY-MM-DD
    try:
        y, m, d = int(base[0:4]), int(base[5:7]), int(base[8:10])
    except ValueError:
        return None
    start = datetime.datetime(y, m, d, tzinfo=datetime.timezone.utc)
    vals = []
    for h in range(24):
        t = start + datetime.timedelta(hours=h)
        key = t.strftime("%Y-%m-%dT%H:00:00Z")
        v = by_from.get(key)
        if v is None or v <= 0:
            return None
        vals.append(v)
    return vals


def fit_params(curves):
    """Per hour h=2..24: (a_h, b_h, resid_sd) of ln(y_h/y_1) on ln(y_1/REF).

    Ordinary least squares over the given complete curves.  Returns None
    when there are too few curves to fit.
    """
    if len(curves) < MIN_CURVES:
        return None
    params = {}
    for h in range(2, 25):
        xs = [math.log(v[0] / REF) for v in curves]
        ys = [math.log(v[h - 1] / v[0]) for v in curves]
        n = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        den = sum((x - mx) ** 2 for x in xs)
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0.0
        a = my - b * mx
        resid = [y - (a + b * x) for x, y in zip(xs, ys)]
        var = sum(r * r for r in resid) / n
        params[h] = (a, b, math.sqrt(var))
    return params


def hour_quantiles(p1: float, h: int, params):
    """Five quantiles for hour h given hour-1 print p1."""
    x = math.log(max(p1, 1.0) / REF)
    if params is not None:
        a, b, sd = params[h]
        med = math.exp(a + b * x)
        spread = min(SPREAD_MAX, max(SPREAD_MIN, SPREAD_MULT * sd))
    else:
        med = math.exp(FALLBACK_A[h])
        spread = FALLBACK_SPREAD
    med = max(med, FLOOR[h])
    qs = []
    prev = 0.0
    for z in Z:
        q = p1 * med * math.exp(z * spread)
        q = min(1e9, max(1.0, q))
        q = round2(q)
        if q < prev:  # rounding must never break non-decreasing order
            q = prev
        qs.append(q)
        prev = q
    return qs


def forecast_case(case: dict, name: str) -> dict:
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))
    curves = []
    for comp in case.get("comparables") or []:
        vals = release_day_curve(comp)
        if vals is not None:
            curves.append(vals)
    params = fit_params(curves)
    hours = [
        {"hour": row["hour"], "q": hour_quantiles(p1, row["hour"], params)}
        for row in case["forecast"]
    ]
    return {"hours": hours}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
