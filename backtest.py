# Local backtest for gta6-trophy-rarity-forecast-01
# Implements the official scorer (pinball loss on the logit scale) and builds
# synthetic practice answers grounded in known facts:
#   - p00 target 04:30Z, p01 target 05:00Z on 2026-11-19
#   - rules state the 04:30 refresh: N = 3,868, every rate but the 100% one lower
#   - current Exophase snapshot (crawled 2026-11-19 23:12 UTC) gives ~24h rates
# Two synthetic answer variants:
#   A: pure dilution (E frozen across the refresh) -> lower bound on true rates
#   B: power-law E growth interpolated in log-time between launch night (t=2.5h)
#      and the 23:12 snapshot (t=23.2h), evaluated at t=4.5h / 5.0h
# Validation: the house persistence baseline scores ~1.51 on the REAL practice
# (per RULES.txt). If it scores ~1.5 on a synthetic variant, that variant is in
# the right ballpark.

import json, math, os

BASE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.expanduser("~/workspace/makefun/gta6-trophy-kit/gta6-trophy-rarity-forecast-01-kit")

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]

# Current snapshot rates (Exophase PS5 page, crawled 2026-11-19 23:12 UTC), trophy order.
SNAP_RATES = [0.03, 99.99, 0.73, 0.14, 0.06, 0.06, 0.06, 0.24, 0.06, 0.06, 0.06,
              0.06, 0.06, 0.03, 0.03, 0.04, 0.04, 0.03, 0.04, 1.89, 0.41, 0.04,
              0.04, 0.04, 0.03, 0.03, 0.04, 0.03, 0.04, 0.03, 0.03, 0.03, 0.09,
              0.05, 0.24, 0.06, 0.14, 0.14, 0.06, 0.04, 0.04, 0.04, 0.04, 0.08,
              0.04, 0.09, 0.04, 0.05, 0.04, 0.11, 0.06, 0.04, 0.05, 0.04, 0.04]

def logit_pct(x):
    # x in percent, clamped 0.01..99.99; return logit(p), p = x/100
    x = min(99.99, max(0.01, x))
    p = x / 100.0
    return math.log(p / (1.0 - p))

def pinball_loss(answer_rates, forecast):
    """answer_rates: list of 55 true rates (percent).
    forecast: dict id -> [q05,q25,q50,q75,q95] (percent).
    Returns mean pinball loss over trophies x levels, as the grader defines it."""
    total = 0.0
    n = 0
    for i, y in enumerate(answer_rates, start=1):
        ly = logit_pct(y)
        qs = forecast[i]
        for tau, q in zip(LEVELS, qs):
            d = ly - logit_pct(q)
            total += 2.0 * max(tau * d, (tau - 1.0) * d)
            n += 1
    return total / n

def load_case(cid):
    with open(os.path.join(KIT, "input", cid + ".in")) as f:
        return json.load(f)

def recover_N_now():
    """Recover players-tracked at the 23:12 snapshot from integer constraints.
    E_i must be an integer, >= launch E0_i, and platinum E1 small (4..8)."""
    c = load_case("p00")
    r0 = c["history"][-1]["rates"]
    E0 = [round(r * 638 / 100.0) for r in r0]
    cands = []
    for N in range(8000, 100001):
        E1 = round(SNAP_RATES[0] * N / 100.0)
        if not (4 <= E1 <= 8):
            continue
        ok = True
        err = 0.0
        for i, r in enumerate(SNAP_RATES):
            e = r * N / 100.0
            ei = round(e)
            err += abs(e - ei)
            if i != 1 and ei < E0[i]:
                ok = False
                break
            if i == 1 and ei < E0[1]:
                ok = False
                break
        if ok:
            cands.append((err, N, E1))
    cands.sort()
    return cands, E0

def synthetic_answers():
    """Return {case_id: {'A': rates, 'B': rates}} for p00 and p01."""
    c00 = load_case("p00")
    r0 = c00["history"][-1]["rates"]
    E0 = [r * 638 / 100.0 for r in r0]
    N_refresh = 3868
    # Variant A: pure dilution
    ansA = [r * 638.0 / N_refresh if r < 100 else 99.99 for r in r0]
    # Variant B: power-law E growth, log-time interpolation.
    # t measured in hours since 2026-11-19T00:00Z. Launch-night last read ~02:30 (t=2.5),
    # snapshot ~23:12 (t=23.2). Targets: p00 04:30 (t=4.5), p01 05:00 (t=5.0).
    cands, _ = recover_N_now()
    N_now = cands[0][1] if cands else 15000
    E_now = [r * N_now / 100.0 for r in SNAP_RATES]
    def interp_E(t_target, t0=2.5, t1=23.2):
        w = math.log(t_target / t0) / math.log(t1 / t0)
        out = []
        for e0, e1 in zip(E0, E_now):
            e0 = max(e0, 0.5)
            e1 = max(e1, e0)  # earners monotone
            out.append(math.exp(math.log(e0) + w * (math.log(e1) - math.log(e0))))
        return out
    def rates_from_E(E, N):
        return [min(99.99, 100.0 * e / N) for e in E]
    # p01: assume no second refresh between 04:30 and 05:00 (same read as 04:30
    # for N), but earners keep growing slightly; N stays 3868.
    ansB00 = rates_from_E(interp_E(4.5), N_refresh)
    ansB01 = rates_from_E(interp_E(5.0), N_refresh)
    # Trophy 2 ("Just Like Paradise") is earned by ~every tracked player:
    # 100% at launch, 99.99% at the 20k snapshot. Its rate stays ~100%; the
    # log-interpolation breaks for it, so pin it.
    ansB00[1] = 99.99
    ansB01[1] = 99.99
    ansA01 = list(ansA)  # same read for p01 under the no-second-refresh assumption
    return {"p00": {"A": ansA, "B": ansB00},
            "p01": {"A": ansA01, "B": ansB01}}, N_now, cands[:8]

# ---------------- baselines ----------------

def baseline_persistence(case):
    """Kit starter: every rate stays at last read; spread 0.5*sqrt(days) logit."""
    last = case["history"][-1]
    rates = last["rates"]
    from datetime import datetime, timezone
    at = datetime.fromisoformat(case["at"].replace("Z", "+00:00"))
    tgt = datetime.fromisoformat(case["target"].replace("Z", "+00:00"))
    days = (tgt - at).total_seconds() / 86400.0
    sd = 0.5 * math.sqrt(max(days, 0.0))
    z = {0.05: -1.6448536269514722, 0.25: -0.6744897501960817, 0.5: 0.0,
         0.75: 0.6744897501960817, 0.95: 1.6448536269514722}
    out = {}
    for i, r in enumerate(rates, start=1):
        l = logit_pct(r)
        qs = []
        for tau in LEVELS:
            v = l + z[tau] * sd
            p = 1.0 / (1.0 + math.exp(-v))
            qs.append(min(99.99, max(0.01, 100.0 * p)))
        out[i] = qs
    return out

def baseline_curve(case):
    """House curve baseline: straight line fit to logit(rate) vs ln(1+hours since
    2026-11-19T00:00Z) over the last 24h of reads; same spread as persistence.
    With flat history the line is flat -> identical to persistence."""
    from datetime import datetime, timezone
    t0 = datetime(2026, 11, 19, 0, 0, tzinfo=timezone.utc)
    pts = []
    for h in case["history"]:
        at = datetime.fromisoformat(h["at"].replace("Z", "+00:00"))
        hrs = (at - t0).total_seconds() / 3600.0
        pts.append((math.log1p(max(hrs, 0.0)), h["rates"]))
    tgt = datetime.fromisoformat(case["target"].replace("Z", "+00:00"))
    x_tgt = math.log1p((tgt - t0).total_seconds() / 3600.0)
    at = datetime.fromisoformat(case["at"].replace("Z", "+00:00"))
    days = (tgt - at).total_seconds() / 86400.0
    sd = 0.5 * math.sqrt(max(days, 0.0))
    z = {0.05: -1.6448536269514722, 0.25: -0.6744897501960817, 0.5: 0.0,
         0.75: 0.6744897501960817, 0.95: 1.6448536269514722}
    out = {}
    ntr = len(case["trophies"])
    for i in range(ntr):
        xs = [x for x, _ in pts]
        ys = [logit_pct(r[i]) for _, r in pts]
        n = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        den = sum((x - mx) ** 2 for x in xs)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den > 0 else 0.0
        inter = my - slope * mx
        l = inter + slope * x_tgt
        qs = []
        for tau in LEVELS:
            v = l + z[tau] * sd
            p = 1.0 / (1.0 + math.exp(-v))
            qs.append(min(99.99, max(0.01, 100.0 * p)))
        out[i + 1] = qs
    return out

def run(forecast_fn, label):
    ans, N_now, cands = synthetic_answers()
    rows = {}
    for cid in ("p00", "p01"):
        case = load_case(cid)
        fc = forecast_fn(case)
        for variant in ("A", "B"):
            rows[(cid, variant)] = pinball_loss(ans[cid][variant], fc)
    per_variant = {}
    for variant in ("A", "B"):
        per_variant[variant] = (rows[("p00", variant)] + rows[("p01", variant)]) / 2.0
    print(f"{label}: p00 A={rows[('p00','A')]:.4f} B={rows[('p00','B')]:.4f} | "
          f"p01 A={rows[('p01','A')]:.4f} B={rows[('p01','B')]:.4f} | "
          f"mean A={per_variant['A']:.4f} B={per_variant['B']:.4f}")
    return per_variant, N_now, cands

if __name__ == "__main__":
    ans, N_now, cands = synthetic_answers()
    print("N(now) candidates (err, N, E1):", cands)
    print("chosen N(now) =", N_now)
    print("p00 answer A (pure dilution) sample:", [round(x, 4) for x in ans["p00"]["A"][:8]])
    print("p00 answer B (power-law E)  sample:", [round(x, 4) for x in ans["p00"]["B"][:8]])
    print("p00 answer A vs B, trophy 3 (Ch1): A=%.4f B=%.4f" % (ans["p00"]["A"][2], ans["p00"]["B"][2]))
    print("p00 answer A vs B, trophy 20 (fishing): A=%.4f B=%.4f" % (ans["p00"]["A"][19], ans["p00"]["B"][19]))
    print("--- baseline validation (real practice: persistence ~1.51, curve ~1.51) ---")
    run(baseline_persistence, "persistence(starter)")
    run(baseline_curve, "curve")
