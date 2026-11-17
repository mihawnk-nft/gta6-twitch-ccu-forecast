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

The fit is kernel-weighted (v2): each comparable gets weight
exp(-0.5 * ((ln(h1/100k) - ln(p1/100k)) / 2.0)^2), so the regression
is local in launch size instead of one global line through tiny
indie launches and million-viewer simultaneous ones.  Bandwidth 2.0
was chosen on practice + leave-one-out CV (see DATA_ANALYSIS.md);
the optimum is flat over 1.5-2.5, so the choice is not a knife edge.

The fit is also console-weighted (v3): a comparable whose launch
included PC gets weight 0.6, a console-only launch gets 1.0.  GTA VI
launches on consoles only (PS5 + Xbox Series X|S, no PC), and
PC-included launches unlock simultaneously worldwide, so their
evening shape differs systematically from rolling-midnight console
launches.  The 0.6 weight was chosen on practice + LOOCV
(practice 0.1534 vs 0.1543, LOOCV 0.3958 vs 0.3972, and the
h1>=20k LOOCV subset improves 0.2805 -> 0.2763); the optimum is
flat over 0.5-0.8.  A comparable with no platforms field listed
counts as console (weight 1.0), so missing data falls back to v2.

The location is circadian-decomposed (v4): each comparable's
release-day log-ratio z_{i,h} = ln(y_{i,h}/y_{i,1}) is split into a
steady-state circadian wave C_{i,h} -- the mean of the same clock
hour's log-ratios on day 2 and day 3, when every regional unlock is
complete -- plus a launch-unlock transient T_{i,h} = z_{i,h} - C_{i,h}.
The wave C_hat_h is the kernel-weighted mean of C_{i,h} across
comparables (same kernel and PC weight as v3); the transient is fit
by kernel-weighted ridge regression on ln(p1/100k) (ridge 1.0), and
the spread is 0.7x the transient residual SD, clamped to [0.25, 1.0].
This uses hours 25..72 of the comparables, which v2/v3 ignored, and
is the only v4 direction that wins on practice AND on LOOCV AND on
the rolling and h1>=20k subsets (practice 0.1532 vs 0.1534, LOOCV
0.3949 vs 0.3958, 21/37 LOOCV cases improve, median delta -0.0018).
When fewer than 5 comparables have complete day-2/day-3 curves the
fit falls back to the v3 regression; when fewer than 5 have a
complete release-day curve it falls back to the hardcoded
intercepts, as before.

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
  1.15x the v1 floor (0.85x the smallest per-hour ratio among the four
  practice launches, so 0.98x that minimum in v2) -- the 1.15 factor was
  chosen because raising the floor improves every one of the four
  practice cases and the rolling-midnight LOOCV subset, while the plain
  LOOCV (which mixes in simultaneous launches the floor is not meant
  for) barely moves.  It binds only for large hour-1 prints.
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
# Kernel bandwidth (log units) for the local-in-size fit, and the
# multiplier on the rolling-midnight floor (see DATA_ANALYSIS.md §7).
KERNEL_BW = 2.0
FLOOR_FACTOR = 1.15
# Console weighting (v3, see DATA_ANALYSIS.md §8): a comparable whose
# launch included PC gets this weight; console-only launches get 1.0.
PC_WEIGHT = 0.6

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


def _hour_key(value):
    """Normalize an hourly timestamp to 'YYYY-MM-DDTHH:00:00Z' (UTC).

    The kit's comparables use that exact form, but a source that writes
    '+00:00' offsets or non-zero minutes would otherwise silently drop
    every hour of a curve.
    """
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    dt = dt.astimezone(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:00:00Z")


def curve_hours(comp: dict, start_offset: int):
    """24 hourly viewer counts starting `start_offset` hours after the
    comparable's release day starts (UTC).

    start_offset 0 -> release day (hours 1..24); 24 -> day 2; 48 ->
    day 3.  Returns a list of 24 positive numbers, or None if any hour
    is missing or non-positive.
    """
    day_start = comp.get("day_start")
    hourly = comp.get("hourly")
    if not day_start or not hourly:
        return None
    by_from = {}
    for row in hourly:
        try:
            key = _hour_key(row["from"])
            if key is None:
                continue
            by_from[key] = float(row["viewers"])
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
        t = start + datetime.timedelta(hours=start_offset + h)
        key = t.strftime("%Y-%m-%dT%H:00:00Z")
        v = by_from.get(key)
        if v is None or v <= 0:
            return None
        vals.append(v)
    return vals


def release_day_curve(comp: dict):
    """A comparable's 24 hourly viewer counts for its release day (UTC).

    Returns a list of 24 positive numbers, or None if any hour is
    missing or non-positive (e.g. the GTA VI pre-release comparable,
    which has no release day yet).
    """
    return curve_hours(comp, 0)


def fit_params(curves, x0, plats=None):
    """Per hour h=2..24: (a_h, b_h, resid_sd) of ln(y_h/y_1) on ln(y_1/REF).

    Kernel-weighted least squares around the target's own x0 = ln(p1/REF):
    a comparable with hour-1 print h1 gets weight
    exp(-0.5 * ((ln(h1/REF) - x0) / KERNEL_BW)^2).  A launch far from the
    target's size still counts, but a launch of similar size counts far
    more.  When plats is given (the comparables' raw 'platforms' strings,
    parallel to curves), a launch that included PC is further down-weighted
    by PC_WEIGHT: the target is a console-only launch, and PC-included
    launches unlock simultaneously worldwide, so their evening shape
    differs from rolling-midnight console launches.  Returns None when
    there are too few curves to fit.
    """
    if len(curves) < MIN_CURVES:
        return None
    params = {}
    for h in range(2, 25):
        xs = [math.log(v[0] / REF) for v in curves]
        ys = [math.log(v[h - 1] / v[0]) for v in curves]
        ws = [math.exp(-0.5 * ((x - x0) / KERNEL_BW) ** 2) for x in xs]
        if plats is not None:
            ws = [w * (PC_WEIGHT if "PC" in (p or "") else 1.0)
                  for w, p in zip(ws, plats)]
        sw = sum(ws)
        mx = sum(w * x for w, x in zip(ws, xs)) / sw
        my = sum(w * y for w, y in zip(ws, ys)) / sw
        den = sum(w * (x - mx) ** 2 for w, x in zip(ws, xs))
        b = sum(w * (x - mx) * (y - my) for w, x, y in zip(ws, xs, ys)) / den if den else 0.0
        a = my - b * mx
        resid = [y - (a + b * x) for x, y in zip(xs, ys)]
        var = sum(w * r * r for w, r in zip(ws, resid)) / sw
        params[h] = (a, b, math.sqrt(var))
    return params


def fit_circadian_params(curves, day2s, day3s, x0, plats=None):
    """Circadian-decomposed location + spread (v4).

    For each comparable, z_{i,h} = ln(y_{i,h}/y_{i,1}) is split into a
    steady-state circadian wave C_{i,h} (mean of the same clock hour's
    log-ratios on day 2 and day 3) and a transient T_{i,h} = z - C.
    C_hat_h is the kernel-weighted mean of C_{i,h}; the transient is
    fit by kernel-weighted ridge regression on ln(h1/REF) (ridge 1.0);
    the spread is 0.7x the transient residual SD, clamped to
    [0.25, 1.0].  Same kernel (bw 2.0) and PC weight as fit_params.

    Returns {h: (med_log_h, 0.0, spread_h)} -- the (a, b, sd) shape
    hour_quantiles expects, with b = 0 because med_log is already the
    location at this case's own x0 -- or None when too few curves
    have complete day-2/day-3 data.
    """
    if len(curves) < MIN_CURVES:
        return None
    n = len(curves)
    xs = [math.log(v[0] / REF) for v in curves]
    ws = [math.exp(-0.5 * ((x - x0) / KERNEL_BW) ** 2) for x in xs]
    if plats is not None:
        ws = [w * (PC_WEIGHT if "PC" in (p or "") else 1.0)
              for w, p in zip(ws, plats)]
    sw = sum(ws)
    mx = sum(w * x for w, x in zip(ws, xs)) / sw
    sxx = sum(w * (x - mx) ** 2 for w, x in zip(ws, xs)) + 1.0
    # C_{i,h} and T_{i,h} per comparable
    c_all = []
    t_all = []
    for i in range(n):
        c_row = []
        t_row = []
        for h in range(2, 25):
            z = math.log(curves[i][h - 1] / curves[i][0])
            c = 0.5 * (math.log(day2s[i][h - 1] / day2s[i][0])
                       + math.log(day3s[i][h - 1] / day3s[i][0]))
            c_row.append(c)
            t_row.append(z - c)
        c_all.append(c_row)
        t_all.append(t_row)
    params = {}
    for hi in range(23):
        h = hi + 2
        c_hat = sum(w * c_all[i][hi] for i, w in enumerate(ws)) / sw
        mt = sum(w * t_all[i][hi] for i, w in enumerate(ws)) / sw
        sxt = sum(w * (xs[i] - mx) * (t_all[i][hi] - mt)
                  for i, w in enumerate(ws))
        b = sxt / sxx
        a = mt - b * mx
        med_log = c_hat + a + b * x0
        res = [t_all[i][hi] - (a + b * xs[i]) for i in range(n)]
        var = sum(w * r * r for w, r in zip(ws, res)) / sw
        # Return the RAW residual SD: hour_quantiles applies
        # SPREAD_MULT and the [0.25, 1.0] clamp itself (as it does for
        # fit_params).  Applying them here too would double-count 0.7x.
        params[h] = (med_log, 0.0, math.sqrt(var))
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
    med = max(med, FLOOR[h] * FLOOR_FACTOR)
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
    plats = []
    curves_c = []  # release-day curves of comps with complete day 2+3
    day2s = []
    day3s = []
    plats_c = []
    for comp in case.get("comparables") or []:
        vals = release_day_curve(comp)
        if vals is not None:
            curves.append(vals)
            plats.append(comp.get("platforms") or "")
            d2 = curve_hours(comp, 24)
            d3 = curve_hours(comp, 48)
            if d2 is not None and d3 is not None:
                curves_c.append(vals)
                day2s.append(d2)
                day3s.append(d3)
                plats_c.append(comp.get("platforms") or "")
    x0 = math.log(max(p1, 1.0) / REF)
    # Prefer the circadian fit (v4); fall back to the v3 regression
    # when too few comparables have complete day-2/day-3 curves.
    params = None
    if len(day2s) >= MIN_CURVES:
        params = fit_circadian_params(curves_c, day2s, day3s, x0, plats_c)
    if params is None:
        params = fit_params(curves, x0, plats)
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
