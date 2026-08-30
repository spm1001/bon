# The personal half — accent files and variation points (bon-hedatu)

The four rites (open, close, plan, review) ship as a byte-identical team core. What a given operator wants woven into them — their dispatch queue, their archive paths, their ranking habits — lives in a **personal half**: `~/.claude/mit-accent.md` on their machine, read by the rites at designated points and nowhere else. User-facing vocabulary stays rite names only ("your open"); the variation points get boring machine names, like hook events.

## The four laws

1. **Complete without.** A machine with no accent file — or an accent without the relevant section — runs every rite complete and silent. An empty slot is never nagged; there is no "you could configure this" line, ever. The only sanctioned growth path is cultivation at close (law 1's other half): when a session has *observed* the operator doing something rite-shaped by hand, the close's Reflect may propose capturing it — from observed habits only, never from empty slots.
2. **Designated points only.** An accent fills its named slots; the spine is not overridable. No accent text can skip a phase, change a gate, or reorder the rite.
3. **Broken half = one line.** An accent that exists but cannot be read, or errors mid-run, degrades to the team spine with ONE plain line ("personal half unreadable — running the team spine"), never banners; self-heal where safe.
4. **Writes are treaty-bound.** An accent section may authorise writes into its owner's own systems of record (their task manager, their notes) — but only where the accent itself records that sanction, in the owner's words, with its date. No written treaty in the accent = the slot is read-only.

## File format

`~/.claude/mit-accent.md`, four sections, one per rite, keyed by the personal variation-point ids — named by OWNERSHIP, uniformly (settled by the operator, 2026-08-30): `open.personal`, `close.personal`, `plan.personal`, `review.personal`. Dotted to match the shipped `review.populate-queue` convention; deliberately "personal" and not "-local", because local means per-machine on this estate (settings.local.json) and this split is per-person. These four ids are the ONLY keys the rites parse. Everything inside a section — sub-headings, pet names, structure — is the operator's own prose, replaceable without touching core or format.

```markdown
# Accent — <owner>

## open.personal
<what to render between the hierarchy and the direction pick>

## close.personal
<what to do before the close-out proposal, including any write sanctions,
 and — if this estate keeps an always-on guidance corpus — where capture
 routes lessons to it>

## plan.personal
<nothing designated yet — reserved>

## review.personal
<the dispatch queue's name and lane names + any semantics pointer;
 canonical pyramid exemplar paths; where drafts land; where runs archive
 durably; a canonical loop map if this operator keeps one>
```

A rite reads its own `## <rite>.personal` section only. **Step sockets are a different species from personal sections:** a step socket (`review.populate-queue`, bon-veleru) is stage direction naming a pluggable step inside the spine; a personal section is the operator's content that fills the rite's designated points. The population step's personal content — which queue, which lanes — lives in `review.personal` like everything else.

## How a rite reads it

The session hooks emit `ACCENT=<path>` when the file exists (open-context.sh, close-context.sh); the review and plan skills check for the file directly. The skill text at each variation point says what to do with the section and what "absent" means — always: skip silently, rite complete.

## The worked example — Sameer's accent

The first accent is the operator this split extracted (see `docs/accent-audit-2026-08-30.md` for the tissue audit that fed it). His halves, in sketch — the live file is `~/.claude/mit-accent.md` on his machines, not this repo, and the names he gives their contents inside that file are his own:

- **open.personal** — renders a three-line digest of his Todoist dispatch queue (sectioned status lanes, drag-order semantics from a pointer his accent carries), loud when his book is missing its queue, silent on a stranger's book.
- **close.personal** — reads the same queue at close and, under his recorded tell-after sanctions (2026-08-09/13/28), ticks completed lines, adds clean-case successor lines, and rewords stale ones; also names where capture routes always-on-guidance lessons on his estate.
- **review.personal** — queue and lane names, pyramid exemplar paths, draft and durable-archive locations, and a canonical loop map, all on his estate's own paths.

Why the split exists: before it, every teammate's /open tried his queue — a teammate hit a permanent "Project '& Toolmaking' not found" nag on 2026-08-11 — and a teammate whose own book legitimately carried a same-named project would have had their queue rendered under his lane semantics, silently. The core carries no operator's furniture; each accent carries exactly its owner's.
