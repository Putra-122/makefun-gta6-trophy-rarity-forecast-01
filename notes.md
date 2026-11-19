# gta6-trophy-rarity-forecast-01 — entry notes

## Competition
- **Slug:** gta6-trophy-rarity-forecast-01 — "Forecast how many GTA VI players earn
  each trophy in week one". $250, escrowed, top 20 places ($50/$35/$25/$10x7/$7x10).
- **Deadline (final case cut):** 2026-11-21T11:30:00Z. Final target 2026-11-26T00:00:00Z.
- **Entry:** program (`main.py`, Python 3.13, stdlib only) in a public GitHub repo.
- **Scoring:** mean pinball loss on the logit scale over 55 trophies x 5 quantiles.
  A prize needs a loss strictly below the best house entry.
- **House baselines:** persistence (kit starter) ~1.51 and curve ~1.51 on practice;
  house AI model forecast (superbot) made once for practice, once for the final
  at 2026-11-21T09:30Z.
- **Submissions at pick:** 6,021 (6,039 by 2026-11-20 00:00 UTC). Dev leaderboard
  top scores (0.001-0.03) exploit the practice-case leak (the rules state the
  04:30 refresh N=3,868); this entry is a genuine model, not a leak exploit.

## Model (main.py)
Earners/players decomposition: rate_i(t) = E_i(t) / N(t).
- N(t): power-law fit in log-time when history shows distinct N (exponential
  cross-check, better fit kept); flat/stale history -> prior multiplier
  (1 + 4.5*sqrt(horizon_h)), sigma 0.6 (first refresh multiplied N ~6x).
- E_i(t): per-trophy power law in log-time when history is rich, capped by N;
  flat history -> new earners from newly tracked players, p_i = tier_a * rate_i
  (bronze 0.35, silver 0.20, gold 0.08, platinum 0.03).
- The ~100% trophy (trophy 2) pinned near 100%. Quantiles logistic on the
  logit scale; sigma wider when history is stale, narrower when rich.
- Deterministic, offline, stdlib only. Runtime ~0.04s per case (limit 8s).
  Output validated: 55 rows, unique ids, 5 finite numbers 0-100, non-decreasing,
  6,209 bytes (limit 65,536). Two runs identical.

## Local backtest (backtest.py)
Synthetic practice answers grounded in the rules (04:30 refresh N=3,868) and the
19 Nov 23:12 Exophase snapshot (players-tracked recovered EXACTLY as N=20,000
from integer constraints on all 55 rates). Two variants:
- A: pure dilution (E frozen across the refresh).
- B: power-law E growth interpolated in log-time to the snapshot.
Validation: persistence scores 1.46 on variant B vs the real ~1.51, so B is
close to the real answers.

| forecaster | variant A | variant B |
|---|---|---|
| persistence (kit starter) | 1.688 | 1.464 |
| curve baseline | 1.688 | 1.464 |
| **this entry** | **0.545** | **0.421** |

~3.1-3.5x better than both house baselines on both variants. Gate cleared:
clearly beats the baselines -> submit.

## Repo / submission
- **Repo:** https://github.com/Putra-122/makefun-gta6-trophy-rarity-forecast-01
- **Commit SHA:** 0a154ac6f798a56a6a8e99ac40afb9a849090b61 (main.py unchanged since 992c2e07b741849efc1160bb64c23f043849b1a8) (main.py, LICENSE MIT,
  README.md, .makefun/owner.json wallet xfazjnk39LekFTxvEGhGVcAtmdpCtQYbx4KzztVeFbU)
- **Quota (checked 2026-11-20 ~00:00 UTC):** day cap 3, taken 0, left 3;
  hard limit 20 left; can_submit true.

## Remaining steps (PARENT must run these — see below)
The transcript bundle must be run from the top-level (parent) agent:
- This subagent's usage rows are written only once its run completes, so the
  SELECT must be re-run after this run ends, with both agent ids.
- The parent session carries the user's actual opening prompt
  ("Garap make.fun aja cari yang lu bisa"); the bundle dry-run flags the
  prompt/parent-chain as missing if run from the subagent alone.
- Bundle also needs --harness-version and --effort (new requirement for
  entries received from 17 Nov 2026); --effort default is the documented
  choice. --mcp none (no MCP servers used in this build).

Commands for the parent (run from inside the unpacked kit dir):
1. SELECT (muse.db), agent ids '75eb15b5-976d-438d-adb4-19419e9d109e' (this
   subagent) and 'de223499-7943-4501-b8ab-6e8cc28a2785' (parent), write rows
   unchanged, one JSON object per line, to ~/workspace/makefun/gta6-usage.jsonl:
   SELECT u.agent_id AS agent_id, u.message_id AS message_id, u.created_at AS
   created_at, u.input_tokens AS input_tokens, u.output_tokens AS output_tokens,
   a.model AS model FROM agent.agent_message_token_usage u JOIN agent.agents a
   ON a.agent_id = u.agent_id WHERE u.agent_id IN ('75eb15b5-976d-438d-adb4-19419e9d109e',
   'de223499-7943-4501-b8ab-6e8cc28a2785') ORDER BY u.created_at DESC LIMIT 500
2. Bundle:
   cd ~/workspace/makefun/gta6-trophy-kit/gta6-trophy-rarity-forecast-01-kit
   node cli/makefun.mjs bundle --repo ~/workspace/makefun/entry-gta6-trophy \
     --out ~/workspace/makefun/gta6-bundle-v1.tar.gz \
     --muse-usage ~/workspace/makefun/gta6-usage.jsonl \
     --harness Muse --harness-version <VERSION> --provider ipnext \
     --model ipnext/avocado-5.17-v1 --effort default --mcp none
3. Submit (curl, x-api-key header, key from ~/workspace/makefun/credentials.json):
   the kit's submit command or the API; retry after 60s on a transient 500
   (500s don't consume quota). Then read the real practice score from the
   dev leaderboard / entry status and iterate if needed (quota 3/day).

## Outcome
- Local grade: 0.545 (A) / 0.421 (B) vs baselines 1.688 / 1.464. READY.
- Submission: NOT YET SUBMITTED — pending parent-side bundle + submit
  (usage rows + parent session required). Submission ID / claim: TBD.
