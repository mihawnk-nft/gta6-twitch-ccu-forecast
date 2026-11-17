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

The transient also carries a pre-release shape signal (v5): s_i =
ln(pre168_i / premax_i), the mean hourly viewership over the 168
hours before release day divided by the pre-release hourly maximum.
A category that was quiet before release relative to its pre-release
peak (a deep pre-release dip: trailer spike, otherwise quiet) rises
much more on launch day: corr(ln(pre168/premax), ln(peak/h1)) =
-0.613 across the 37 comparables. The transient regression gains s
as a second regressor (ridge 2.0 on its coefficient only). This is
the first v5 direction that wins on practice AND on LOOCV with a
real margin (practice 0.1391 vs 0.1532, LOOCV 0.3835 vs 0.3949),
and it is NOT fit on the practice cases at all -- the signal is
cross-sectional among the comparables and LOOCV-validated. For the
final case the target's own s* comes from its history_hourly
(premax 1,418,094 from the Extended Look premiere vs a quiet
pre168 mean of 940 gives s* = -7.32, beyond the comparables' range
but inside the pattern Silksong set at -6.81; the ridge keeps the
adjustment bounded and the floor caps the downside).

Finally the location is per-hour calibrated (v5): CAL_BIAS is the
median per-hour log residual of the model on the four practice
launches, applied at CAL_SHRINK (0.4x in v5b). The bias is
systematic, not noise: the model under-predicts the 05:00Z US-East
unlock jump (+0.50 at h5) and the evening peak (+0.10..+0.15 at
h18-22) and over-predicts the midday lull (-0.20..-0.25 at h12-14).
The bias is a fixed constant from the practice cases (it does not
depend on the case being forecast), so it is applied unchanged in
LOOCV and on the final case.

v5b (Gemini v5 ideas, see DATA_ANALYSIS.md §11) refines the
transient fit three ways: (1) Idea A — shrunk-slope + slope-decay:
each hour's slope is shrunk 65% toward a fitted exponential decay
curve (the raw slopes decay smoothly from 0.00 at h2 to about -0.61
at h20) and the intercept is recomputed so the weighted mean stays
exact; (2) Idea D — a rolling-midnight Tikhonov prior (a0, b0) from
the comparables with the US-East midnight surge ln(y5/y3) > 0.05,
b0 floored at -0.65, precision growing with the target's position in
the right tail of launch sizes; (3) a stronger ridge (4.0) on the
pre-dip s coefficient. Ship candidate I10 (pre-dip + A + D + CAL
0.4 + ridge 4.0): practice 0.1321 / LOOCV 0.3766 / rolling-subset
LOOCV 0.4163 — it beats v4 on all three metrics and passes both the
old dual gate and the revised gate (practice <= 0.145, subset-LOOCV
down, global LOOCV <= 0.415). The v5 candidate 1 (0.1301/0.3866)
is superseded: its rolling-subset LOOCV (0.4405) was worse than
v4's (0.4378). Ideas B (2-D local-linear on the median-7d lift
ratio), C (dip-depth evening term, kept as a frontier variant),
the Psi diurnal pre-release shape, and the log-return decomposition
were all tested in the harness and rejected (see §11).

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
# Pre-release dip signal (v5, see DATA_ANALYSIS.md §10): ridge on the
# s coefficient in the transient regression, and the per-hour
# calibration bias (median log residual of the model on the four
# practice launches) with its shrink factor.
# v5b (see §11): EXTRA_RIDGE 4.0 (stronger shrink on s — the dip
# signal is real but its coefficient was overfit at 2.0), Idea A
# (shrunk-slope + slope-decay, ALPHA_SH=0.65 toward the fitted
# exponential decay curve), Idea D (rolling-midnight Tikhonov prior,
# TAU_BASE/TAU_EXTRAP, b0 >= -0.65), CAL_SHRINK 0.4.  Ship candidate
# I10: practice 0.1321 / LOOCV 0.3766 / rolling-subset LOOCV 0.4163 —
# beats v4 on all three and beats the v5 candidate 1 (0.1301/0.3866)
# on global LOOCV (-0.010) and on the rolling subset (-0.024), for
# +0.002 practice. Candidate 1 is SUPERSEDED: its rolling-subset
# LOOCV (0.4405) was WORSE than v4's (0.4378), failing the revised
# gate (subset must fall). The clamp-0.16 idea was neutral (the
# spread floor almost never binds) and is NOT used.
EXTRA_RIDGE = 4.0
ALPHA_SH = 0.65
TAU_BASE = 1.5
TAU_EXTRAP = 2.5
CAL_SHRINK = 0.4
CAL_BIAS = {
    2: -0.143, 3: -0.144, 4: -0.135, 5: 0.495, 6: 0.288, 7: 0.191,
    8: 0.044, 9: 0.047, 10: -0.064, 11: -0.065, 12: -0.197,
    13: -0.248, 14: -0.173, 15: -0.095, 16: -0.036, 17: 0.018,
    18: 0.147, 19: 0.055, 20: 0.099, 21: 0.115, 22: 0.107,
    23: 0.025, 24: 0.025,
}

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


def pre_release_stats(comp: dict):
    """(premax, pre168) for a comparable: the maximum hourly viewership
    and the mean hourly viewership over the 168 hours strictly before
    its release day.  Returns (None, None) when there is no pre-release
    history.  The pre-release dip signal is s = ln(pre168 / premax).
    """
    day_start = comp.get("day_start")
    hourly = comp.get("hourly")
    if not day_start or not hourly:
        return None, None
    try:
        y, m, d = int(day_start[0:4]), int(day_start[5:7]), int(day_start[8:10])
    except ValueError:
        return None, None
    day0 = datetime.datetime(y, m, d, tzinfo=datetime.timezone.utc)
    vals = []       # all hourly values strictly before release day
    win = []        # values in the 168h window [day0-168h, day0)
    for row in hourly:
        try:
            key = _hour_key(row["from"])
            if key is None:
                continue
            dt = datetime.datetime.strptime(key, "%Y-%m-%dT%H:00:00Z").replace(
                tzinfo=datetime.timezone.utc)
            if dt < day0:
                vals.append(float(row["viewers"]))
                if dt >= day0 - datetime.timedelta(hours=168):
                    win.append(float(row["viewers"]))
        except (KeyError, TypeError, ValueError):
            continue
    if not vals or not win:
        return None, None
    premax = max(vals)
    pre168 = sum(win) / len(win)
    return premax, pre168


def target_pre_release(case: dict):
    """(premax, pre168) for the target case from its history_hourly:
    the maximum and the mean of the last 168 hourly values."""
    hh = case.get("history_hourly") or []
    vals = [float(r["viewers"]) for r in hh if r.get("viewers") is not None]
    if not vals:
        return None, None
    return max(vals), sum(vals[-168:]) / len(vals[-168:])


def wls_ridge_2(xs, ys, ws, ridge, ridge_idx):
    """Weighted least squares y ~ a + b1*x1 + b2*x2 with a ridge penalty
    `ridge` on the coefficients in ridge_idx (indices into the
    [intercept, b1, b2] vector).  Returns (beta, resid_sd) or None
    when the system is singular."""
    n = len(ys)
    X = [[1.0, xs[0][i], xs[1][i]] for i in range(n)]
    m = 3
    A = [[0.0] * m for _ in range(m)]
    bvec = [0.0] * m
    for i in range(n):
        w = ws[i]
        for r in range(m):
            bvec[r] += w * X[i][r] * ys[i]
            for c in range(m):
                A[r][c] += w * X[i][r] * X[i][c]
    for j in ridge_idx:
        A[j][j] += ridge
    for col in range(m):
        piv = max(range(col, m), key=lambda r: abs(A[r][col]))
        if abs(A[piv][col]) < 1e-12:
            return None
        A[col], A[piv] = A[piv], A[col]
        bvec[col], bvec[piv] = bvec[piv], bvec[col]
        for r in range(col + 1, m):
            f = A[r][col] / A[col][col]
            for c in range(col, m):
                A[r][c] -= f * A[col][c]
            bvec[r] -= f * bvec[col]
    beta = [0.0] * m
    for r in range(m - 1, -1, -1):
        s = bvec[r] - sum(A[r][c] * beta[c] for c in range(r + 1, m))
        beta[r] = s / A[r][r]
    resid = [ys[i] - sum(X[i][j] * beta[j] for j in range(m)) for i in range(n)]
    var = sum(w * r * r for w, r in zip(ws, resid)) / max(sum(ws), 1e-9)
    return beta, math.sqrt(var)


def wls_pen_2(xs, ys, ws, pen):
    """Weighted least squares y ~ a + b1*x1 + b2*x2 with penalties
    pen = [(j, lam, target)]: adds lam*(beta_j - target)^2 to the
    objective (j indexes [intercept, b1, b2]).  Returns (beta, resid_sd)
    or None when the system is singular.  This generalizes
    wls_ridge_2: a plain ridge is (j, lam, 0.0); Idea D's rolling prior
    is (0, tau0, a0) + (1, tau0, b0)."""
    n = len(ys)
    X = [[1.0, xs[0][i], xs[1][i]] for i in range(n)]
    m = 3
    A = [[0.0] * m for _ in range(m)]
    bvec = [0.0] * m
    for i in range(n):
        w = ws[i]
        for r in range(m):
            bvec[r] += w * X[i][r] * ys[i]
            for c in range(m):
                A[r][c] += w * X[i][r] * X[i][c]
    for (j, lam, tgt) in pen:
        if lam:
            A[j][j] += lam
            bvec[j] += lam * tgt
    for col in range(m):
        piv = max(range(col, m), key=lambda r: abs(A[r][col]))
        if abs(A[piv][col]) < 1e-12:
            return None
        A[col], A[piv] = A[piv], A[col]
        bvec[col], bvec[piv] = bvec[piv], bvec[col]
        for r in range(col + 1, m):
            f = A[r][col] / A[col][col]
            for c in range(col, m):
                A[r][c] -= f * A[col][c]
            bvec[r] -= f * bvec[col]
    beta = [0.0] * m
    for r in range(m - 1, -1, -1):
        s = bvec[r] - sum(A[r][c] * beta[c] for c in range(r + 1, m))
        beta[r] = s / A[r][r]
    resid = [ys[i] - sum(X[i][j] * beta[j] for j in range(m)) for i in range(n)]
    var = sum(w * r * r for w, r in zip(ws, resid)) / max(sum(ws), 1e-9)
    return beta, math.sqrt(var)


def _decay_curve(bs):
    """Fit b(h) = b_inf + (b0 - b_inf)*exp(-gamma*(h-2)) to the 23 raw
    transient slopes bs (h=2..24) by a gamma grid + linear least
    squares for (b_inf, b0).  Returns the fitted curve [b(2)..b(24)].
    Idea A: the raw transient slopes decay smoothly and monotonically
    (0.00 at h2 to about -0.61 at h20), so shrinking each hour's slope
    toward this curve removes estimation noise without biasing the
    shape."""
    ks = list(range(23))  # h-2
    best = None
    for gamma in (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.7, 1.0):
        e = [math.exp(-gamma * k) for k in ks]
        u = [1.0 - v for v in e]
        suu = sum(a * a for a in u)
        sue = sum(a * b for a, b in zip(u, e))
        see = sum(b * b for b in e)
        suy = sum(a * y for a, y in zip(u, bs))
        sey = sum(b * y for b, y in zip(e, bs))
        det = suu * see - sue * sue
        if abs(det) < 1e-12:
            continue
        b_inf = (suy * see - sey * sue) / det
        b0 = (suu * sey - sue * suy) / det
        sse = sum((y - (b_inf * uu + b0 * ee)) ** 2
                  for y, uu, ee in zip(bs, u, e))
        if best is None or sse < best[0]:
            best = (sse, b_inf, b0, gamma)
    _, b_inf, b0, gamma = best
    return [b_inf + (b0 - b_inf) * math.exp(-gamma * k) for k in ks]


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


def fit_circadian_params(curves, day2s, day3s, x0, plats=None, s_vals=None,
                         s_star=None):
    """Circadian-decomposed location + spread (v4) with the v5
    pre-release dip signal and the v5b refinements (Ideas A and D):

    * the transient regression gains s as a second regressor (ridge
      EXTRA_RIDGE=4.0 on its coefficient only);
    * Idea D — a Tikhonov prior (a0, b0) from the rolling-midnight
      subset (comparables with S_rm = ln(y5/y3) > 0.05), b0 floored at
      -0.65, with precision tau0 = TAU_BASE + TAU_EXTRAP * tail(x*)
      where tail ramps from 0 at the 75th percentile of the
      comparables' x to 1 at their max: the prior only bites when the
      target's hour-1 print is in the right tail, i.e. exactly where
      the non-parametric fit loses support (GTA VI);
    * Idea A — each hour's slope b_h is shrunk (ALPHA_SH=0.65) toward
      the fitted exponential decay curve b(h), and the intercept is
      recomputed so the weighted mean stays exact.

    The spread is 0.7x the transient residual SD, clamped to
    [0.25, 1.0].  Same kernel (bw 2.0) and PC weight as fit_params.
    The per-hour calibration bias (CAL_BIAS x CAL_SHRINK) is added to
    the location; hour_quantiles applies the floor afterwards.

    s_vals is parallel to curves (0.0 when a comparable has no
    pre-release history); s_star is the target's own s, or the mean
    of s_vals when the target has none.  Returns
    {h: (med_log_h, 0.0, spread_h)} -- the (a, b, sd) shape
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
    if s_vals is None:
        s_vals = [0.0] * n
    if s_star is None:
        s_star = sum(s_vals) / len(s_vals) if s_vals else 0.0
    sw = sum(ws)
    mx = sum(w * x for w, x in zip(ws, xs)) / sw
    ms = sum(w * s for w, s in zip(ws, s_vals)) / sw
    sxx = sum(w * (x - mx) ** 2 for w, x in zip(ws, xs)) + 1.0
    # Idea D inputs: rolling-midnight subset + tail weight of x0.
    roll = [i for i in range(n)
            if math.log(curves[i][4] / curves[i][2]) > 0.05]
    xs_sorted = sorted(xs)
    q75 = xs_sorted[int(0.75 * (len(xs_sorted) - 1))]
    xmax = xs_sorted[-1]
    tail = 0.0 if xmax <= q75 else min(1.0, max(0.0, (x0 - q75) / (xmax - q75)))
    tau0 = TAU_BASE + TAU_EXTRAP * tail
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
    c_hat = {}
    for hi in range(23):
        c_hat[hi + 2] = sum(w * c_all[i][hi] for i, w in enumerate(ws)) / sw
    # First pass: per-hour transient fit (with the rolling prior).
    abc = {}  # h -> (a, b, c)
    for hi in range(23):
        h = hi + 2
        ys = [t_all[i][hi] for i in range(n)]
        a0 = None
        b0 = None
        if len(roll) >= 5:
            xr = [xs[i] for i in roll]
            sr = [s_vals[i] for i in roll]
            yr = [ys[i] for i in roll]
            wr = [ws[i] for i in roll]
            f2 = wls_pen_2([xr, sr], yr, wr, [(2, EXTRA_RIDGE, 0.0)])
            if f2 is not None:
                a0 = f2[0][0]
                b0 = max(f2[0][1], -0.65)
        if a0 is None:
            a0 = sum(w * y for w, y in zip(ws, ys)) / sw
            b0 = 0.0
        fit = wls_pen_2([xs, s_vals], ys, ws,
                        [(0, tau0, a0), (1, tau0, b0),
                         (2, EXTRA_RIDGE, 0.0)])
        if fit is None:
            # fall back to the one-regressor ridge fit
            mt = sum(w * ys[i] for i, w in enumerate(ws)) / sw
            sxt = sum(w * (xs[i] - mx) * (ys[i] - mt) for i, w in enumerate(ws))
            b = sxt / sxx
            a = mt - b * mx
            abc[h] = (a, b, 0.0)
        else:
            (a, b, c), _ = fit
            abc[h] = (a, b, c)
    # Idea A: shrink the slopes toward the exponential decay curve and
    # recompute each intercept so the weighted mean stays exact.
    bs_raw = [abc[h][1] for h in range(2, 25)]
    curve = _decay_curve(bs_raw)
    params = {}
    for hi in range(23):
        h = hi + 2
        a, b, c = abc[h]
        b_new = (1.0 - ALPHA_SH) * b + ALPHA_SH * curve[hi]
        mt = sum(w * t_all[i][hi] for i, w in enumerate(ws)) / sw
        a_new = mt - b_new * mx - c * ms
        med_log = c_hat[h] + a_new + b_new * x0 + c * s_star
        res = [t_all[i][hi] - (a_new + b_new * xs[i] + c * s_vals[i])
               for i in range(n)]
        var = sum(w * r * r for w, r in zip(ws, res)) / sw
        # Return the RAW residual SD: hour_quantiles applies
        # SPREAD_MULT and the [0.25, 1.0] clamp itself (as it does for
        # fit_params).  Applying them here too would double-count 0.7x.
        # The calibration bias shifts the location before the floor.
        params[h] = (med_log + CAL_SHRINK * CAL_BIAS[h], 0.0, math.sqrt(var))
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
    s_vals_c = []  # pre-release dip signal, parallel to curves_c
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
                pm, p168 = pre_release_stats(comp)
                s_vals_c.append(math.log(p168 / pm) if (pm and p168) else 0.0)
    x0 = math.log(max(p1, 1.0) / REF)
    # The target's own pre-release dip signal from its history_hourly;
    # when it has none, s_star falls back to the comparables' mean.
    pm_t, p168_t = target_pre_release(case)
    if pm_t and p168_t:
        s_star = math.log(p168_t / pm_t)
    elif s_vals_c:
        s_star = sum(s_vals_c) / len(s_vals_c)
    else:
        s_star = 0.0
    # Prefer the circadian fit (v4) with the v5 pre-dip signal;
    # fall back to the v3 regression when too few comparables have
    # complete day-2/day-3 curves.
    params = None
    if len(day2s) >= MIN_CURVES:
        params = fit_circadian_params(curves_c, day2s, day3s, x0, plats_c,
                                      s_vals_c, s_star)
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
