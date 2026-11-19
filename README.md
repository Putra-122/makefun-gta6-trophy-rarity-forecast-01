# makefun-gta6-trophy-rarity-forecast-01

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Putra-122/makefun-gta6-trophy-rarity-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Putra-122/makefun-gta6-trophy-rarity-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Entry for the make.fun competition "Forecast how many GTA VI players earn each trophy in week one". A forecaster that models earners and players separately: `rate_i(t) = E_i(t) / N(t)`, where `N(t)` is the players tracked by Exophase and `E_i(t)` the players who earned trophy `i`. N and E are modelled separately because a refresh moves them differently: N jumps when Exophase recounts its tracked base (diluting every rate), while E only grows as players actually earn trophies. Forecasting the rate directly (persistence / a curve on the rate) misses that structure.

## Run it

```sh
MAKEFUN_INPUT_DIR=<dir with *.in> MAKEFUN_OUTPUT_DIR=<dir> python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=3rytdfj3&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>

## Model: earners / players decomposition

- **N(t):** with distinct N values in the history, fit a power law in
  log-time (exponential as a cross-check, keeping the better fit) and
  extrapolate. With a flat/stale history, a refresh is overdue: a prior
  multiplier growing with the horizon.
- **E_i(t):** with distinct E values, a per-trophy power law in log-time,
  capped by N. With a flat history, new earners come from newly tracked
  players: `E_i += (N_target - N_last) * p_i`, where `p_i` is the chance a
  newly tracked player has earned trophy `i` — proportional to the trophy's
  current rate and scaled down by tier.
- The ~100% trophy (every tracked player earns it) is pinned near 100%.
- Quantiles are `logistic(logit(median) + z_tau * sigma)`, sigma from the
  uncertainty in N and E plus a horizon term; wider when the history is
  stale, narrower when it is rich.

## Local backtest (practice cases p00/p01, synthetic answers)

Synthetic answers grounded in the competition rules (04:30 refresh: N=3,868,
every rate but the 100% one lower) and the 19 Nov 23:12 Exophase snapshot
(N recovered exactly as 20,000). Two variants: A = pure dilution (E frozen),
B = power-law E growth interpolated in log-time to the snapshot.

| forecaster | variant A | variant B |
|---|---|---|
| persistence (kit starter) | 1.688 | 1.464 |
| curve baseline | 1.688 | 1.464 |
| **this entry** | **0.545** | **0.421** |

House baselines score ~1.51 on the real practice; persistence scores 1.46
on variant B, so variant B is close to the real answers. This entry beats
both baselines ~3x on both variants.

Python 3.13, stdlib only, deterministic, offline, ~0.05s per case.
