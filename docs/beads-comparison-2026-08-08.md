# Bon and Beads — a family history (2026-08-08)

Deep comparison of bon with Steve Yegge's Beads, run 2026-08-08 with Sameer. Method: four parallel subagents (beads git archaeology on a full clone; beads current-state from source + beads.gascity.com + web; a 45-board quantitative sweep of bon usage; estate lineage archaeology across ~/notes, ~/.claude and this repo's history), plus primary reads of Beads' README/AGENT_INSTRUCTIONS at HEAD `6b39bcd` and bon's understanding.md/CONTRACT.md. Quant working files were at `/tmp/bon-audit/` (ephemeral); the regeneration recipe is "read every `.bon` under ~/repos + ~/.claude + ~/notes; JSONL raw, Dolt via `bon list --all --jsonl` merged with `--someday`".

## The headline: not parallel histories — a fork

Bon is a beads descendant, and the record is complete:

| | Beads (Yegge) | This estate |
|---|---|---|
| 2025-10-11 | First public commit — a human CLI tool, SQLite | |
| 2025-10-15 | Day-four pivot: "Give your coding agent a memory upgrade" | |
| 2025-10-18 | | First contact, day seven — Sameer asks claude.ai about equipping Claude with a bd skill |
| Nov–Dec 2025 | Hash IDs unlock multi-agent; Gas Town gestates | Yegge's actual `bd` binary runs estate-wide (`mise-qa6`, `ssm-bz4`…), plus a homegrown skill layer and bidirectional "hub sync" in `spm1001/claude-beads` (archived, on GitHub) |
| 2026-01-14 | Dolt backend lands in beads (experimental) | |
| 2026-01-24 | | Breaking point: hub sync decommissioned as root cause of cross-repo corruption; ~450 orphaned issues cleaned. Partly self-inflicted (our sync), partly bd's dual SQLite/JSONL drift |
| 2026-01-25 | | Arc designed and built in one day (SPEC.md, "InnerPlan"), migration via `bd export \| migrate.py` consuming genuine Yegge schema |
| 2026-02-14 | v0.50.0: Dolt default; daemon deleted (~19,663 lines) | Arc → Bon (kitchen-brigade renaming); Beads acknowledgement added to README |
| 2026-04-02 | v1.0.0; repo moves to gastownhall org | ~19 boards migrate to shared Dolt on hezza |

The near-miss: beads' Dolt backend landed eleven days before arc was born — we left as they started fixing what broke us. The founding rejections (arc SPEC.md summary table) were independent of the corruption anyway: 86 commands → 12, dual store → JSONL only, daemon → none, priorities → ordering, Agile vocabulary → GTD ("'blocker' creates panic, 'P0' triggers urgency"). The required `brief {why,what,done}` was arc's own invention.

**Lineage correction (Sameer, this session): the Dolt adoption was also inheritance, not convergence.** Yegge mentioned Dolt; Sameer asked a Claude to investigate; bon tried it. Three things crossed the fork: agent-first ergonomics (acknowledged in README), JSONL as a first-class format, and Dolt.

## What each became

**Beads**: a swarm organ. 10,503 commits / 5,432 PRs in ten months; 26,129 stars, 466 contributors, ~712K LOC Go, ~115 CLI commands, 123 releases. ~64% of commits are Yegge + his named agent personas (`beads/crew/emma`, `mayor`, `gastown/polecats/nux`); by 2026 development itself runs on the Gas Town swarm. Now Dolt-only ("issues.jsonl is an export, not the database"), with 19 dependency-edge types (open vocabulary), leases/heartbeats/CAS for claims, custom statuses with behavioural categories, formulas→molecules→wisps workflow chemistry, gates for async waits, `bd remember`/`bd prime` memory, semantic compaction ("permanent graceful decay"), sync to six external trackers, federation. Every subsystem it invented for itself (daemon, JSONL sync, 3-way merge, tombstones) was eventually deleted in favour of buying the property from Dolt. Company: Gas City, Inc. (Chris Sells CEO, Julian Knutsen CTO, Yegge advisor) selling a commercial Beads Team Server; a January 2026 $GAS memecoin wobble; a community claim that beads influenced Anthropic's Tasks feature.

**Bon**: a partnership organ. ~3,950 LOC Python, 23 commands, 679 tests. Estate usage at 2026-08-08: **3,398 items across 45 boards (26 JSONL / 19 Dolt), 82.3% done, 601 open**. Adoption measured separately (docs/adoption-2026-08-04.md): 68% of substantive sessions since March 2026, 14:1 use-to-maintenance. Briefs are essays: median 726 chars of why/what/done, `how` on 62%. Quiet multi-human edges: Rupert Coghlan 52 items, Judi Hu 45, on ITV boards.

**The bimodal-population finding** (the session's sharpest quant result): median create→done lag is 0.9 days and 51.8% of items close within 24h of creation — yet open items have median age 19d, p90 83d. Two populations share one tool: a live work-journal (file-the-step, do-the-step — GTD's loop compressed to minutes, healthy) and an aspirational backlog aging on a different clock. Development consequence: spend on the fast loop's ergonomics and on tail-aging tools (staleness, VEIL/PARK, desire questions); never on prioritisation machinery — the population that would need it doesn't wait. The done-per-week stream is the treaty table's raw material.

Other quant notables: `badly` 2 uses and `someday` 6 estate-wide (both brand new — hipapu watches); tactical on 26.4% of items (`stepped` is the top mutation verb, 794); done_note on 54.7% of done items; 41% of outcomes childless (capture-generously residue); 25% of actions standalone; three boards squat on the `bon-` prefix (bon, piano, mit-agentic-sales — bon-kafono tracks); dead boards with open items: mit-agentic-sales (8 open, idle since May), mit-world-cup (29 open, idle since mid-July), mit-sales-lead-agent (13 open, idle since 06 Jul).

## The deep contrasts

- **Where enforcement sits.** Bon's brief is schema — every write path refuses empty why/what/done (the moat that beat GitHub Issues, 2026-07-21). Beads' only required field is a 255-char title; the rest is advisory `bd lint` plus exhortation: `bd prime` injects "🚨 SESSION CLOSE PROTOCOL 🚨 … you MUST run this checklist". Their company now sells governance for a data layer that can't refuse an empty brief.
- **Register.** Bon went through deliberate register reform (MANDATORY-scoring dismantled, threat framing measured as corner-cutting fuel). Beads ships sirens at agents it says "enjoy working with Beads". Two theories of agent psychology; we hold the published evidence.
- **What memory is.** Beads: structured data plus decay (atomic `bd remember` facts, compaction of month-old closed work, TTL'd wisps). Bon: synthesised prose (handoffs, understanding.md rewritten with judgment each open, "For Claudes to come"). They built the hippocampus's pruning; we built its consolidation. Beads has no rite; bon has no decay.
- **Where workflow lives.** Beads puts repeatable process in data (TOML formulas cooked into dependency-ordered molecules, gated on CI and humans). Bon puts it in liturgy (skills: /open, /close, /review, /plan, publish). Conway's law both ways: a swarm needs machine-readable process; a partnership can afford liturgy.
- **Who decides.** Beads: "the graph — not a human dispatcher — decides what is workable next." Bon: truth verifies mechanically, desire is adjudicated by the human; falsifiers are human-authored or honestly absent; Todoist stays Sameer's book. Convergent organ: `bd human <id>` is a flag-for-human-decision queue — the TRUTH/DESIRE split productised by the swarm world.
- **Concurrency.** Beads is ahead (swarm reality beat it in early): leases+heartbeats, `bd reclaim`, atomic claims, CAS guards. Bon's answer this session (bon-tedabo): CAS adopted (`bon step --expect N`, fails loud); leases/auto-reclaim rejected — long-idle sessions are normal here and an idle-but-alive session can't heartbeat, so expiry would automate the civelu conscription.

## Adjudications (Sameer, 2026-08-08)

| Candidate | Verdict | Landed as |
|---|---|---|
| Commit↔item citation convention + orphans check | Adopted — also serves as discovered-from provenance with zero schema change (lineage in `--why` is write-once provenance, not rot-prone state; commit refs make genealogy git-derivable; Dolt logs argv anyway) | bon-nenine, suite 1.38.0; first live run found 2 real cited-but-open items (cewemo, wivuti), 14% organic coverage baseline |
| Tactical CAS guards | Adopted; TTL/lease auto-reclaim explicitly rejected | bon-tedabo, suite 1.39.0; doctor gained stale-claim advisories (visibility only) |
| `defer_until` date tickler | Parked — someday is 6 items old; let a review ceremony produce adoption evidence first | No item; revisit alongside bon-hipapu |
| Compaction / memory decay | Refused — "storage is free and grep is fast"; done briefs are provenance; read-time cost lives in subagent surveys | No item |
| Priorities, labels, external-tracker sync, orchestration | Standing refusals, vindicated by beads' own trajectory (115 commands against their written "30+ is a discoverability problem"; their v0.62 "Beads Is Now Standalone" cut the same docket/orchestrator seam our CONTRACT.md draws) | — |

## Sources

- Beads clone at `6b39bcd` (2026-08-07): README.md, AGENT_INSTRUCTIONS.md, CHANGELOG.md, NEWSLETTER.md, engdocs/PROJECT_CHARTER.md, internal/types/types.go
- https://beads.gascity.com/ · https://gascity.com/ · Yegge's "Welcome to Gas City" (Medium) · GitHub API repos/steveyegge/beads (2026-08-08)
- Arc founding spec: `git show 3a31af6:SPEC.md` · migration `git show d7a7b65:scripts/migrate.py` · rename `git show 3a1873d:RENAME_PLAN.md` · acknowledgement `ef54e42`
- Estate lineage: `~/notes/raw/claude/distilled/handoff-850c6637.md` (hub-sync decommission), `handoff-348c3370.md` (arc design), `~/notes/raw/claude/chats/2025-10-18 1116 …` (first contact), `~/notes/raw/pre-itv/Work/Archive/CLAUDE (5).md` (bd-era workspace)
- Bon side: `.bon/understanding.md`, `docs/CONTRACT.md`, `docs/adoption-2026-08-04.md`; quantitative sweep of 45 boards, 2026-08-08
