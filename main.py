# gta6-trophy-rarity-forecast-01 entry
#
# Model: earners / players decomposition.
#   rate_i(t) = E_i(t) / N(t)
# where N(t) = players tracked by Exophase and E_i(t) = players who earned
# trophy i. N and E are modelled separately because a refresh moves them
# differently: N jumps when Exophase recounts its tracked base (diluting every
# rate), while E only grows as players actually earn trophies. Forecasting the
# rate directly (persistence / curve on the rate) misses that structure.
#
# - N(t): if the history shows distinct N values, fit a power law in log-time
#   (and an exponential as a cross-check, keeping the better fit) and
#   extrapolate to the target. If the history is flat/stale, a refresh is
#   overdue: use a prior N multiplier that grows with the horizon.
# - E_i(t): if the history shows distinct E values, fit a power law in
#   log-time per trophy, capped by N. If flat, new earners come from the new
#   players: E_i grows by (N_target - N_last) * p_i, where p_i is the chance a
#   newly tracked player has earned trophy i by the target -- proportional to
#   the trophy's current rate (early trophies are earned by many) and scaled
#   down by tier (platinum/gold are earned by almost nobody in the window).
# - The ~100% trophy (every tracked player earns it) is pinned near 100%.
# - Quantiles: logistic(logit(median) + z_tau * sigma), sigma from the
#   uncertainty in N and E plus a horizon term; wider when the history is
#   stale (a refresh jump is the dominant uncertainty), narrower when the
#   history is rich.
#
# Deterministic, stdlib only, no network. Falls back to a wide-spread
# persistence forecast if anything unexpected happens (a valid output always
# beats a crash: an invalid/missing output is scored as last-rate).

import json
import math
import os
import sys
from datetime import datetime, timezone

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = {0.05: -1.6448536269514722, 0.25: -0.6744897501960817, 0.5: 0.0,
     0.75: 0.6744897501960817, 0.95: 1.6448536269514722}
# Launch reference for log-time (game released 2026-11-19, first reads 18 Nov
# 23:50Z). Times before it are clamped to a small positive age.
T0 = datetime(2026, 11, 19, 0, 0, tzinfo=timezone.utc)

# Prior for a newly-tracked player earning trophy i (flat-history branch),
# per tier: a * (current rate). Platinum/gold are earned by ~nobody in a
# short window; bronze chapter/activity trophies by a real fraction.
TIER_A = {"platinum": 0.03, "gold": 0.08, "silver": 0.20, "bronze": 0.35}
# Flat-history N prior: N_target = N_last * (1 + N_PRIOR_K * sqrt(horizon_h)).
# The launch-night page sat unchanged for hours, then its first refresh
# multiplied N ~6x; K=4.5 gives ~6.5x over a 90-minute horizon, with wide
# uncertainty (N_PRIOR_SIGMA on the log scale).
N_PRIOR_K = 4.5
N_PRIOR_SIGMA = 0.6


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def age_hours(at):
    """Hours since launch reference, floored at 0.1 so log() is safe."""
    return max(0.1, (at - T0).total_seconds() / 3600.0)


def clamp_pct(x):
    return min(99.99, max(0.01, x))


def logit_pct(x):
    x = clamp_pct(x)
    p = x / 100.0
    return math.log(p / (1.0 - p))


def logistic(v):
    if v >= 0:
        return 1.0 / (1.0 + math.exp(-v))
    e = math.exp(v)
    return e / (1.0 + e)


def linfit(xs, ys):
    """Least-squares y = a + b*x. Returns (a, b, rms_residual)."""
    n = len(xs)
    if n == 0:
        return 0.0, 0.0, 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return my, 0.0, 0.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    a = my - b * mx
    resid = math.sqrt(sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys)) / n)
    return a, b, resid


def distinct_states(case):
    """Collapse consecutive identical reads into states.
    Returns list of dicts {at, N, rates, total} in time order."""
    states = []
    for h in case.get("history", []):
        n = h.get("players_tracked")
        rates = h.get("rates")
        if n is None or rates is None:
            continue
        if states and states[-1]["N"] == n and states[-1]["rates"] == rates:
            continue
        states.append({"at": parse_time(h["at"]), "N": float(n),
                       "rates": [float(r) for r in rates],
                       "total": h.get("trophies_earned")})
    return states


def forecast_N(states, at, target):
    """Forecast players-tracked at target. Returns (N_med, sigma_log)."""
    n_last = states[-1]["N"]
    horizon_h = max(0.0, (target - at).total_seconds() / 3600.0)
    distinct_N = sorted({s["N"] for s in states})
    if len(distinct_N) >= 2 and len(states) >= 2:
        xs_log = [math.log(age_hours(s["at"])) for s in states]
        xs_lin = [age_hours(s["at"]) for s in states]
        ys = [math.log(s["N"]) for s in states]
        a1, b1, r1 = linfit(xs_log, ys)   # power law: log N ~ a + b log t
        a2, b2, r2 = linfit(xs_lin, ys)   # exponential: log N ~ a + b t
        x_tgt_log = math.log(age_hours(target))
        x_tgt_lin = age_hours(target)
        # Prefer the better-fitting form; damp the exponential (it explodes).
        if r1 <= r2:
            logN = a1 + b1 * x_tgt_log
            resid = r1
        else:
            logN = a2 + b2 * x_tgt_lin
            resid = r2
            # cap exponential growth to at most 3x per day of horizon
            logN = min(logN, math.log(n_last) + 1.1 * horizon_h / 24.0)
        N_med = math.exp(logN)
        # Never forecast fewer tracked players than now; cap at 10x over horizon.
        N_med = min(max(N_med, n_last), n_last * 10.0)
        sigma = max(0.25, min(0.8, resid + 0.12 * math.sqrt(horizon_h / 24.0)))
        return N_med, sigma
    # Flat history: a refresh is overdue. Prior multiplier grows with horizon.
    # (The launch-night page sat unchanged for hours, then the first refresh
    # multiplied N ~6x; a stale page + a short horizon still means a several-x
    # jump is the central case, with wide uncertainty.)
    mu = math.log(1.0 + N_PRIOR_K * math.sqrt(max(horizon_h, 0.05)))
    N_med = n_last * math.exp(mu)
    sigma = N_PRIOR_SIGMA
    return N_med, sigma


def forecast_E(case, states, N_target, at, target):
    """Forecast earners per trophy at target. Returns list of E_i."""
    n_tr = len(case["trophies"])
    last = states[-1]
    n_last = last["N"]
    rates_last = last["rates"]
    E_last = [r * n_last / 100.0 for r in rates_last]
    horizon_h = max(0.0, (target - at).total_seconds() / 3600.0)
    # Rich history: per-trophy power-law fit in log-time.
    distinct_E = any(
        any(abs(s["rates"][i] * s["N"] / 100.0 - E_last[i]) > 0.5
            for i in range(n_tr))
        for s in states[:-1])
    if len(states) >= 3 and distinct_E:
        xs = [math.log(age_hours(s["at"])) for s in states]
        x_tgt = math.log(age_hours(target))
        out = []
        for i in range(n_tr):
            ys = [math.log(max(0.5, s["rates"][i] * s["N"] / 100.0))
                  for s in states]
            a, b, _ = linfit(xs, ys)
            # E is monotone and saturating: damp positive slope for trophies
            # that are already common, and never let E exceed N.
            e = math.exp(a + b * x_tgt)
            e = max(e, E_last[i])
            out.append(min(e, N_target * 0.999))
        return out
    # Flat history: new earners come from newly tracked players.
    dN = max(0.0, N_target - n_last)
    out = []
    for i, tr in enumerate(case["trophies"]):
        r = rates_last[i]
        if r >= 90.0:
            # ~every tracked player earns this one: E tracks N.
            out.append(N_target * 0.999)
            continue
        a = TIER_A.get(str(tr.get("tier", "bronze")).lower(), 0.35)
        p = a * (r / 100.0)
        # A trophy cannot be earned by more new players than exist, and
        # earners cannot outgrow the tracked base.
        e = E_last[i] + dN * p
        out.append(min(e, N_target * 0.999))
    return out


def sigma_for(case, states, sig_N, horizon_h, rich):
    """Per-trophy logit-scale sigma."""
    out = []
    for i, tr in enumerate(case["trophies"]):
        r = states[-1]["rates"][i]
        if r >= 90.0:
            out.append(0.10)  # pinned near 100%
            continue
        if rich:
            # Rich history: fit-driven, grows slowly with horizon; harder
            # (rarer) trophies are relatively noisier.
            base = 0.22 + 0.10 * math.sqrt(horizon_h / 24.0)
            rare = 0.15 if r < 0.1 else (0.08 if r < 0.5 else 0.0)
            out.append(min(0.9, base + rare + 0.5 * sig_N))
        else:
            # Stale history: the refresh jump dominates. Sigma from N
            # uncertainty plus E-growth uncertainty.
            out.append(min(1.1, math.sqrt(sig_N ** 2 + 0.30 ** 2)))
    return out


def forecast(case):
    states = distinct_states(case)
    at = parse_time(case["at"])
    target = parse_time(case["target"])
    horizon_h = max(0.0, (target - at).total_seconds() / 3600.0)
    rich = len(states) >= 3
    if not states:
        # No history at all: flat 50% with a wide spread is the honest answer.
        return {t["id"]: [5.0, 25.0, 50.0, 75.0, 95.0]
                for t in case["trophies"]}
    N_med, sig_N = forecast_N(states, at, target)
    E = forecast_E(case, states, N_med, at, target)
    sigmas = sigma_for(case, states, sig_N, horizon_h, rich)
    out = {}
    for i, tr in enumerate(case["trophies"]):
        med = clamp_pct(100.0 * E[i] / N_med)
        s = sigmas[i]
        l = logit_pct(med)
        qs = []
        for tau in LEVELS:
            v = l + Z[tau] * s
            qs.append(clamp_pct(100.0 * logistic(v)))
        # enforce non-decreasing (logistic with increasing z already is, but
        # clamping can tie them -- keep the order explicit)
        for k in range(1, 5):
            if qs[k] < qs[k - 1]:
                qs[k] = qs[k - 1]
        out[tr["id"]] = qs
    return out


def fallback(case):
    """Wide-spread persistence: always valid, used only if forecast() fails."""
    last = case["history"][-1] if case.get("history") else None
    rates = last["rates"] if last else [50.0] * len(case["trophies"])
    out = {}
    for i, tr in enumerate(case["trophies"]):
        r = rates[i] if i < len(rates) else 50.0
        l = logit_pct(r)
        qs = [clamp_pct(100.0 * logistic(l + Z[tau] * 0.8)) for tau in LEVELS]
        out[tr["id"]] = qs
    return out


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    cases = sorted(f for f in os.listdir(in_dir) if f.endswith(".in"))
    os.makedirs(out_dir, exist_ok=True)
    for fn in cases:
        cid = fn[:-3]
        with open(os.path.join(in_dir, fn)) as f:
            case = json.load(f)
        try:
            fc = forecast(case)
        except Exception:
            fc = fallback(case)
        rows = [{"id": t["id"], "q": fc[t["id"]]} for t in case["trophies"]]
        payload = json.dumps({"trophies": rows}, separators=(",", ":"))
        with open(os.path.join(out_dir, cid + ".out"), "w") as f:
            f.write(payload)


if __name__ == "__main__":
    main()
