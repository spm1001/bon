# Codex surface for Bon

The authored skill is `surfaces/codex/skills/bon/SKILL.md`. On Tube it is exposed as one explicit link at `~/.codex/skills/bon`; the source remains in this repository. Start a new Codex invocation to refresh skill discovery, then use `$bon` for opening, planning, board operations or closing. This does not register Claude's `/open` or `/close` commands in Codex.

The adapter routes to the maintained `skills/open`, `skills/plan`, `skills/close` and `skills/review` procedures in this checkout. Their phases and user-facing products are shared; tool names, context collection, identity, personal-section discovery and runtime-specific helpers are translated explicitly. Install the skill with this source tree available: copying only SKILL.md loses its source links. The original qualification examined installed Claude plugin 1.85.3 and Bon CLI 1.85.2.

The initial adaptation preserved board mechanics but omitted important rite outcomes, including close reflection/proposals, personal queue reconciliation and most planning/review. A natural close exposed that gap. [The parity review](parity-review-2026-09-07.md) records the correction and the verification limits. No model-specific behavioural rule is inferred from this instruction omission.

Claude breadcrumbs and unqualified transcript/capture hooks remain unused. Their purposes are handled through explicit arrival, manual context/CLI evidence and handoffs where possible; unavailable automatic ingestion/backup is disclosed separately. The adapter does not downgrade the whole rite because one runtime mechanism is absent.

The initial Codex-on-Tube installation action was infra `iw-roveji` (done). Its evidence and cold-start continuation check live in `infra/machines/tube/codex`. Broader natural-task qualification continues under infra `iw-nereci`; source parity work is Bon `bon-ziwuda`. Agents running the next natural rites own recording observed failures against those existing routes.
