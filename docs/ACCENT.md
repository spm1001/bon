# The personal half — accent files and variation points (bon-hedatu)

The four rites (open, close, plan, review) ship as a byte-identical team core. What a given operator wants woven into them — their dispatch queue, their archive paths, their ranking habits — lives in a **personal half**: `~/.claude/mit-accent.md` on their machine, read by the rites at designated points and nowhere else. User-facing vocabulary stays rite names only ("your open"); the variation points get boring machine names, like hook events.

## The four laws

1. **Complete without.** A machine with no accent file — or an accent without the relevant section — runs every rite complete and silent. An empty slot is never nagged; there is no "you could configure this" line, ever. The only sanctioned growth path is cultivation at close (law 1's other half): when a session has *observed* the operator doing something rite-shaped by hand, the close's Reflect may propose capturing it — from observed habits only, never from empty slots.
2. **Designated points only.** An accent fills its named slots; the spine is not overridable. No accent text can skip a phase, change a gate, or reorder the rite.
3. **Broken half = one line.** An accent that exists but cannot be read, or errors mid-run, degrades to the team spine with ONE plain line ("personal half unreadable — running the team spine"), never banners; self-heal where safe.
4. **Writes are treaty-bound.** An accent section may authorise writes into its owner's own systems of record (their task manager, their notes) — but only where the accent itself records that sanction, in the owner's words, with its date. No written treaty in the accent = the slot is read-only.

## File format

`~/.claude/mit-accent.md`, four top-level headings, one per rite:

```markdown
# Accent — <owner>

## open
### open.compass
<what to render between the hierarchy and the direction pick>

## close
### close.tap
<what to do at close's queue-tap slot, including any write sanctions>
### close.capture-routing
<where this estate routes always-on-guidance lessons>

## plan
<nothing designated yet — reserved>

## review
### review.queue        <the dispatch queue's name, lane names, semantics pointer>
### review.exemplars    <canonical pyramid exemplar paths on this estate>
### review.draft-path   <where pyramid drafts land>
### review.archive      <where review runs archive durably>
### review.loop-map     <canonical stockpot/loop map, if this operator keeps one>
```

Section names under each rite heading are the variation points. A rite reads its own `## <rite>` heading only.

## How a rite reads it

The session hooks emit `ACCENT=<path>` when the file exists (open-context.sh, close-context.sh); the review and plan skills check for the file directly. The skill text at each variation point says what to do with the section and what "absent" means — always: skip silently, rite complete.

## The worked example — Sameer's accent

The first accent is the operator this split extracted (see `docs/accent-audit-2026-08-30.md` for the tissue audit that fed it). His halves, in sketch — the live file is `~/.claude/mit-accent.md` on his machines, not this repo:

- **open.compass** — renders a three-line compass from his `& Toolmaking` Todoist dispatch queue (sectioned status lanes, drag-order semantics from his `~/.claude/loop.md`), loud when his book is missing its queue, silent on a stranger's book.
- **close.tap** — reads the same queue at close and, under his recorded tell-after sanctions (2026-08-09/13/28), ticks completed lines, adds clean-case successor lines, and rewords stale ones.
- **review.\*** — queue name and lane names (`Up Next` / `With Sameer`), pyramid exemplars under `~/scratch` and `~/notes/raw/claude/bon-audit-*/`, drafts to `~/scratch`, durable archive to `~/notes/raw/claude/bon-audit-{date}/`, stockpot loop map at `~/notes/practices/stockpot-map.html`.

Why the split exists: before it, every teammate's /open tried his queue — a teammate hit a permanent "Project '& Toolmaking' not found" nag on 2026-08-11 — and a teammate whose own book legitimately carried a same-named project would have had their queue rendered under his lane semantics, silently. The core carries no operator's furniture; each accent carries exactly its owner's.
