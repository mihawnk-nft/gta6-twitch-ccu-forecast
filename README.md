# GTA VI Twitch CCU forecast — make.fun entry

[![gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/mihawnk-nft/gta6-twitch-ccu-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/mihawnk-nft/gta6-twitch-ccu-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)

Forecasts how many people watch Grand Theft Auto VI live on Twitch in
each hour of its release day (19 Nov 2026, UTC), from the first hour's
viewer print alone — five quantiles (5/25/50/75/95%) per hour, hours 2-24.

## Method

Reference-class forecasting over the case's comparables (past big
launches' hourly Twitch curves):

1. For each hour h, fit `ln(y_h / y_1) = a_h + b_h * ln(p1 / 100k)` over
   the comparables with a complete release-day curve, where p1 is the
   case's hour-1 print. The slope is about −0.94 at peak hours: a launch
   whose hour 1 is already huge has little headroom left, while one
   whose hour 1 is near zero can rise hundreds of times.
2. Floor the median ratio at a rolling-midnight minimum (0.85x the
   smallest per-hour ratio among the four practice launches). GTA VI
   unlocks region by region like those launches, so the audience must
   rise after hour 1 even if hour 1 is enormous — the raw regression
   would otherwise predict a fall to ~0.25x at peak hours.
3. Spread: 0.7x the regression's residual SD per hour, clamped to
   [0.25, 1.0] in log units; quantiles are log-normal around the median.

See [DATA_ANALYSIS.md](DATA_ANALYSIS.md) for the measured curves, the
regression table, the GTA VI scale anchors, and the honest limitations.

## Results (measured, not claimed)

| | pinball loss (log scale) |
|---|---:|
| House persistence baseline | 0.387 |
| This forecaster, 4 practice cases | **0.181** (typical miss 28.0%, 90% coverage 1.00) |
| Leave-one-out CV, 37 comparables | **0.419** vs baseline 0.930 |
| Leave-one-out CV, hour-1 >= 20k (n=27) | **0.294** vs baseline 0.321 |

Practice answers verified against SullyGnome's "Average viewers" data
(re-fetched release months only, 17 Nov 2026); hour-1 prints match the
kit exactly.

## Run it

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Python 3.13, standard library only, no network, deterministic
(~0.07 s per case). Reads every `*.in` in the input directory and
writes `<id>.out` for each: `{"hours": [{"hour": h, "q": [q05, q25, q50,
q75, q95]}]}` for h = 2..24.

## License

MIT — see [LICENSE](LICENSE).
