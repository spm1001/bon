# Handoff — 2026-04-04 (cross-repo seed)

session_id: seeded from ~/Repos session on Mac
purpose: Fond architecture — bon's session lifecycle is being redesigned

## Now

### Gotchas
- This is a CROSS-REPO handoff seeded from a design session in batterie-de-savoir. Read the design brief first: ~/Repos/batterie/batterie-de-savoir/docs/fond-architecture.md
- The bon items live in batterie-de-savoir (bds-gorite), not here. Actions bds-fitipe (handoff template + /close), bds-hemune (/open), and bds-vabeda (auto-handoff + routing) are the bon-repo workstreams.
- /close currently produces 6 outputs. The new design: one handoff with two zones (Now/Compost), bon updates, commit. That's it.
- The auto-handoff.sh has a background Opus call via ccconv that races the next /open. Strip it — mechanical only.
- Contributions (.bon/contributions/) are being retired as a separate pipeline. The Learned section in the handoff replaces them.

### Risks
- /close is a complex skill with many interdependencies. Changing the handoff format affects /open, auto-handoff.sh, garde's extraction pipeline, and any Claude that reads handoffs.
- 15 pending contribution files exist across repos. They need processing before the contributions pipeline is retired.

### Next
- Start with bds-fitipe: design the two-zone handoff template, then update /close to produce it
- Then bds-hemune: update /open to read the new format and synthesize Learned into understanding.md
- Then bds-vabeda: strip Opus from auto-handoff, add scratch-to-target routing

### Commands
```bash
# Read the design brief
cat ~/Repos/batterie/batterie-de-savoir/docs/fond-architecture.md

# See the bon hierarchy
cd ~/Repos/batterie/batterie-de-savoir && bon show bds-gorite

# Current /close skill
cat ~/.claude/plugins/cache/*/bon/*/skills/close/SKILL.md | head -100

# Current auto-handoff
cat ~/.claude/plugins/cache/*/bon/*/hooks/session-end.sh
cat ~/.claude/plugins/cache/*/bon/*/scripts/auto-handoff.sh
```

## Compost

### Done
- Audited memory files across Mac and Hezza (25 vs 22 project memory dirs, 15 frozen overlapping repos)
- Analysed CC source: autoDream, memory recall (Sonnet selector), team memory, canonical git root keying
- Compared all four knowledge layers for tafelmusik (understanding.md, MEMORY.md topics, handoffs, garde extractions)
- Identified ~90% duplication between handoffs and staged garde extractions
- Discovered contributions are consumed and deleted by /open (not missing — working as designed)
- Designed two-zone handoff format, overnight composting, scratch routing
- Filed bds-gorite outcome with 5 actions in batterie-de-savoir

### Reflection
The handoff is already the richest session artifact — written with full context, pre-structured, pre-reflected. Making it the primary artifact and deriving everything else from it eliminates duplication without losing quality. The key insight: contributions (Learned section) should stay as a separate cognitive act within the handoff because the framing "what transcends this session" produces architecturally different content than "what happened in this session." And /open's synthesis of Learned into understanding.md isn't busywork — it's onboarding that builds the new Claude's mental model.

### Learned
The session lifecycle has three temporal rhythms that shouldn't be conflated: rapid-cycle (30 /close+/open pairs per day, needs instant orientation), overnight (daily composting of handoffs into understanding.md + garde), and Anthropic's background (autoDream consolidating MEMORY.md from transcripts). Each rhythm serves different knowledge: rapid carries operational context (Gotchas/Next), overnight carries durable insight (Learned→understanding.md, Done→garde), and Anthropic's carries typed observations (feedback/project/reference memories). The handoff's two-zone structure maps directly to the first two rhythms. Anthropic's system feeds itself from the handoff content in the session transcript — we don't need to write to MEMORY.md, just write a rich handoff.
