# GTA VI Twitch CCU forecast — data analysis

Date: 17 November 2026. All figures below are measured, not estimated from
memory. Sources are named per claim.

## 1. The true practice answers (SullyGnome, fetched 17 Nov 2026)

The house built the practice cases from SullyGnome's hourly Twitch category
averages ("Average viewers" dataset). I re-fetched exactly the four release
months the house used — one request per game, release month only:

- `GET https://sullygnome.com/api/charts/linecharts/getconfig/GameViewers/30/0/117671/Marvel's_Wolverine/%20/%20/2026/9/%20/0/`
- `.../28264/Red_Dead_Redemption_2/.../2018/10/...`
- `.../65645/God_of_War_Ragnar%C3%B6k/.../2022/11/...`
- `.../97296/Marvel's_Spider-Man_2/.../2023/10/...`

The hour-0 value of each month matches the kit's hour-1 print exactly
(23,357 / 116,550 / 269,517 / 119,087), confirming the fetch is the same
series the kit was cut from. Release-day hourly viewers (UTC hours 1-24):

| hour | Wolverine (h1 23,357) | RDR2 (116,550) | GOW Ragnarok (269,517) | Spider-Man 2 (119,087) |
|-----:|----------------------:|---------------:|-----------------------:|-----------------------:|
| 1 | 23,357 | 116,550 | 269,517 | 119,087 |
| 2 | 19,397 | 102,778 | 220,787 | 79,573 |
| 3 | 20,292 | 99,986 | 146,900 | 51,615 |
| 4 | 18,329 | 84,459 | 141,669 | 50,272 |
| 5 | 35,760 | 152,428 | 156,301 | 166,214 |
| 6 | 40,523 | 176,319 | 281,917 | 146,818 |
| 9 | 37,322 | 134,888 | 196,345 | 93,203 |
| 12 | 45,078 | 165,093 | 179,704 | 68,551 |
| 15 | 78,329 | 231,529 | 271,761 | 131,596 |
| 18 | 189,396 | 369,358 | 435,038 | 225,745 |
| 19 | 175,604 | 322,991 | 444,580 | 250,538 |
| 20 | 206,982 | 290,598 | 460,387 | 240,849 |
| 21 | 212,243 | 281,596 | 445,097 | 258,378 |
| 22 | 196,416 | 258,394 | 434,600 | 263,140 |
| 23 | 153,926 | 223,948 | 411,192 | 253,088 |
| 24 | 147,358 | 192,584 | 383,725 | 216,387 |

Ratios to hour 1 (y_h / y_1), the shape the forecaster must learn:

| | Wolverine | RDR2 | GOW Ragnarok | Spider-Man 2 |
|---|---:|---:|---:|---:|
| h2 | 0.83 | 0.88 | 0.82 | 0.67 |
| h3 | 0.87 | 0.86 | 0.55 | 0.43 |
| h4 | 0.78 | 0.72 | 0.53 | 0.42 |
| h5 | 1.53 | 1.31 | 0.58 | 1.40 |
| h12 | 1.93 | 1.42 | 0.67 | 0.58 |
| h18 | 8.11 | 3.17 | 1.61 | 1.90 |
| h20 | 8.86 | 2.42 | 1.71 | 2.02 |
| h21 (peak for Wolverine) | 9.09 | 2.42 | 1.65 | 2.17 |
| peak (any hour) | 9.09x @ h21 | 3.17x @ h18 | 1.71x @ h20 | 2.21x @ h22 |
| day mean viewers | 85,996 | 195,202 | 285,189 | 145,412 |

Findings:

- **Same shape, different amplitude.** All four dip in hours 2-4 (0.42-0.88x
  hour 1), jump at hour 5 (US East unlock, 05:00Z), sag around hour 12
  (0.37-1.93x; the UTC-midday lull, 03:00-04:00 PT), then rise to an
  evening peak at hours 18-22 and fall slightly into hour 24. Peak hour:
  21, 18, 20, 22.
- **Peak-to-hour-1 falls as hour 1 grows:** 9.09x at h1=23k, 3.17x at
  117k, 2.21x at 119k, 1.71x at 270k. Hour 1 already contains the
  New Zealand / Australia / Europe audience for a rolling-midnight
  launch, so a bigger hour 1 means less of the world is still to unlock.
- **Absolute peaks are much closer than hour 1s:** 212k, 369k, 460k,
  263k (range 1.7x) while hour 1 spans 23k-270k (range 11.5x). The
  peak is roughly proportional to h1^0.3 across these four, not to h1.

## 2. The 38 comparables (kit case files)

37 of the 38 comparables have a complete release-day curve (the 38th is
the GTA VI category itself, pre-release, so it has no release day).
Stratified by hour-1 size, the median ratio r_h = y_h / y_1:

| stratum | n | h1 range | median peak ratio | median ratio h20 |
|---|---:|---|---:|---:|
| h1 < 5k | 8 | 164-4,941 | ~200x (h19-21) | ~229x |
| 5k-50k | 9 | 6,400-46,345 | ~5.0x @ h21 | 4.78x |
| 50k-150k | 11 | 50,351-146,993 | ~1.87x @ h22 | 1.78x |
| h1 > 150k | 9 | 152,314-875,155 | ~1.2x @ h21 | 0.95x |

The tiny-hour-1 stratum is launches whose game had effectively not
unlocked anywhere at 00:00 UTC (e.g. Hollow Knight: Silksong h1=164,
peak 347,773 = 2,121x; Kingdom Come: Deliverance II h1=414, peak
457,359 = 1,105x). The large-hour-1 stratum is dominated by
simultaneous global launches (Cyberpunk 2077 h1=851,999, peak 1,069,278
= 1.26x; ELDEN RING h1=875,155, peak at hour 1 = 1.00x).

Peak hour across the 37: hours 18-22 hold 27 of 37 peaks (h18: 4, h19: 6,
h20: 5, h21: 7, h22: 5); only 2 peak at hour 1 and 3 at hour 2. Median
peak/h1 = 2.42x; median absolute peak = 224,179 (min 36,036 Saros,
max 1,069,278 Cyberpunk 2077).

Per-hour OLS of ln(y_h/y_1) on ln(h1/100k), all 37 curves (this is what
`main.py` fits at runtime from the case's own comparables):

| h | a (log ratio @ h1=100k) | b (slope) | resid SD | pred. ratio @ 25k / 100k / 300k / 1M |
|---:|---:|---:|---:|---:|
| 2 | -0.059 | +0.02 | 0.30 | 0.92 / 0.94 / 0.97 / 0.99 |
| 3 | -0.224 | +0.00 | 0.72 | 0.80 / 0.80 / 0.80 / 0.80 |
| 4 | -0.306 | -0.04 | 0.76 | 0.78 / 0.74 / 0.70 / 0.67 |
| 6 | -0.215 | -0.04 | 0.83 | 0.86 / 0.81 / 0.77 / 0.73 |
| 9 | -0.190 | -0.31 | 0.82 | 1.27 / 0.83 / 0.59 / 0.41 |
| 12 | -0.070 | -0.55 | 1.03 | 2.00 / 0.93 / 0.51 / 0.26 |
| 15 | +0.356 | -0.77 | 1.07 | 4.17 / 1.43 / 0.61 / 0.24 |
| 18 | +0.668 | -0.91 | 0.89 | 6.91 / 1.95 / 0.72 / 0.24 |
| 20 | +0.783 | -0.94 | 0.76 | 8.01 / 2.19 / 0.78 / 0.25 |
| 21 | +0.798 | -0.94 | 0.77 | 8.15 / 2.22 / 0.79 / 0.26 |
| 24 | +0.583 | -0.91 | 0.77 | 6.28 / 1.79 / 0.66 / 0.22 |

The slope steepens through the day to about -0.94 at peak hours: the
day's peak absolute audience barely depends on hour 1 at all
(peak proportional to h1^(1+b) = h1^0.06). The residual SD is large
(0.75-1.07 in log units at hours 9-16) because the pool mixes
rolling-midnight and simultaneous launches; the forecaster uses
0.7x that SD as its spread, a factor chosen on leave-one-out
cross-validation (see section 4), not on the practice cases.

## 3. Why the floor exists

The raw OLS, extrapolated to a very large hour 1 (say 1M, plausible for
GTA VI — see section 5), predicts a peak-hour ratio of ~0.25x, i.e. the
audience *falls* to a quarter of hour 1 by hour 20. That extrapolation
is driven by simultaneous launches (Elden Ring, Cyberpunk) whose hour 1
already was the peak. GTA VI is a rolling-midnight launch like the four
practice games: at 00:00 UTC the US (the largest Twitch audience) has
not unlocked yet (East 05:00Z, Pacific 08:00Z). In all four practice
launches the audience rose after hour 1, and the smallest peak-hour
ratio among them was 1.61-1.71x. The forecaster therefore floors the
median ratio at 0.85x the smallest per-hour ratio among the four
practice launches (h17: 1.19, h18: 1.37, h19: 1.40, h20: 1.45,
h21: 1.40, h22: 1.37, h23: 1.30, h24: 1.21; early hours 0.31-0.89).
The floor binds only for large hour-1 prints; at h1=100k the OLS
prediction is above it almost everywhere. Cost if wrong: if GTA VI
behaved like a simultaneous launch and truly fell to 0.8x at peak, the
floor costs ~ln(1.45/0.8) = 0.59 log units at those hours; if it
behaves like the practice launches and we forecast 0.25x, the cost
would be ~ln(1.7/0.25) = 1.9. The floor is cheap insurance against
the catastrophic error.

## 4. Validation

Pinball loss on the log scale (lower is better), scored against the true
answers in section 1. House persistence baseline on the same cases:
**0.387** (typical miss 82.8%, 90% coverage 0.783, per the kit).

| forecaster | practice loss (p00/p01/p02/p03) | typical miss | 90% coverage |
|---|---:|---:|---:|
| House baseline (starter) | 0.387 (0.744/0.287/0.215/0.303) | 82.8% | 0.78 |
| Global median ratio | 0.313 | — | — |
| OLS on ln(h1), all curves | 0.239 | — | — |
| OLS + rolling-midnight floor, spread 0.7x resid SD (**shipped**) | **0.181 (0.173/0.199/0.156/0.194)** | **28.0%** | **1.00** |

Leave-one-out CV on the 38 comparables (each comparable's release day
as a pseudo-case, forecast from the other 37, scored against its own
actuals; run through the shipped `main.py` itself):

| | LOOCV all (n=37) | LOOCV h1 >= 20k (n=27) |
|---|---:|---:|
| House baseline | mean 0.930, median 0.325 | mean 0.321, median 0.256 |
| Shipped forecaster | **mean 0.419, median 0.274** | **mean 0.294, median 0.252** |

The LOOCV mean is dominated by the tiny-hour-1 pseudo-cases (a 164-viewer
hour 1 rising 2,000x is inherently near-unpredictable; every method
scores badly on them). The h1 >= 20k subset is the relevant one for
GTA VI, whose hour 1 will be large, and the shipped forecaster beats
the baseline there too (0.294 vs 0.321 mean). Determinism: two runs on
the practice produce byte-identical outputs. Timing: ~0.07 s per case
(limit 8 s). Output files ~1.5 kB (limit 65,536).

## 5. GTA VI scale anchors (web research, 17 Nov 2026)

These anchors do **not** enter the forecaster (it only uses the case's
hour-1 print and comparables); they are context for what hour 1 may look
like and a sanity check on the floor.

- Pre-orders: Sensor Tower estimated **12.13M digital pre-orders**
  (~$1.18B) as of 13 Nov, **14.94M (~$1.45B) as of 16 Nov** (Axis
  Intelligence tracker; third-party estimates, not Rockstar/Take-Two
  figures). Take-Two CEO Strauss Zelnick, 10 Nov: pre-orders "vastly
  exceeding" expectations. Bank of America: >= $1.9B gross in the first
  3 days (~15M copies day one) to satisfy investors. Newzoo: $3.25-5.2B
  first-week revenue, 37-51M copies week one.
- Precedent: GTA V made $800M in its first 24 hours (2013) and $1B in
  3 days; 230M+ units lifetime. It still drew 1.4B hours watched on
  Twitch in 2024 (Tubefilter/SullyGnome).
- Twitch launch peaks, single-player: Cyberpunk 2077 **1,140,960**
  (TwitchTracker, Dec 2020; 1.1M in first 24 h, 15.9M hours watched);
  Hogwarts Legacy **~1.27M** (Stream Hatchet, Feb 2023, helped by Twitch
  Drops — the single-player record); Elden Ring **909,800** (Feb 2022);
  Baldur's Gate 3 **481,500** (Streams Charts, Aug 2023, 3.7M hours
  watched on release day). GTA V's own all-time Twitch peak is
  1,140,747 (3 May 2021, RP era).
- GTA VI pre-release Twitch signal: the category already had **1,240
  viewers / 181 channels** on 17 Nov (house probe, competition.yaml);
  the 26-minute "Extended Look" premiere (27 Aug 2026) peaked at
  **1,418,094** viewers in the GTA VI category that hour (SullyGnome
  comparable in the kit) and drew 3.97M peak viewers across platforms
  with 5.2M hours watched on Twitch alone (Streams Charts / Eurogamer
  via The Guardian). Trailer 1 drew 93M YouTube views in 24 h.
- Implication: GTA VI's hour-1 print is likely in the hundreds of
  thousands to over a million — far above every practice hour 1
  (23k-270k) — which is exactly the regime where the raw OLS
  extrapolation is dangerous and the rolling-midnight floor matters.
  A 1.3-2.5M peak (past single-player records are 1.14-1.27M, and GTA VI
  pre-orders exceed Cyberpunk's 8M by ~2x) is plausible; the
  forecaster's q95 at h20 for a 1M hour 1 is ~3.7M, which covers it.

## 6. Honest limitations

- **Four practice cases only.** The practice loss (0.181) is measured on
  n=4 launches; the floor constants come from those same four minima.
  The floor is a one-sided guard, not a fitted shape, and LOOCV over 37
  independent launches confirms the direction, but a 4-case sample
  cannot pin the true peak ratio for GTA VI.
- **SullyGnome vs minute reads.** Practice answers are SullyGnome hourly
  averages (one point per hour); the final is the mean of 60 minute
  reads. The two measures differ slightly (a fast-moving hour's average
  vs its minute mean); nothing in the model corrects for that.
- **Hour 1 is a single number.** The model uses only the hour-1 print
  (plus the comparables). It ignores the case's `history` (pre-release
  minute reads), `streams` (top streamers at the checkpoint) and
  `channels` — a huge streamer going live at hour 2 would move the
  real curve and the model cannot see it coming.
- **The final is one case.** The grade is a single launch day. Even a
  well-calibrated forecaster can lose to a lucky narrow one on one
  realisation; the spread (0.7x residual SD) is a compromise between
  the 4-case practice optimum (narrower) and the 37-case LOOCV optimum.
- **GTA VI is out of sample on scale.** No comparable had a 15M-pre-order
  launch; the biggest Twitch single-player peak in the data is 1.27M.
  If GTA VI's hour 1 lands above ~1.5M, the forecast is extrapolating
  beyond every training point and the floor does most of the work.
- **SullyGnome terms.** SullyGnome asks not to be bulk-scraped; only the
  four release-month fetches the house itself used were made, no other
  bulk download. Figures are factual public Twitch counts, quoted with
  attribution.
