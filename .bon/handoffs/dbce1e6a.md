# Handoff — 2026-03-31

session_id: dbce1e6a-16de-4cc3-9759-dc24a6da58fd
purpose: Instruction shards, auto-handoff fix, skill renames (0.12.0)

## Done
- Fixed stale script finder: SCRIPTS→BON_SCRIPTS, GARDE_SCRIPTS find→ls -td (bon-venasi)
- Fixed auto-handoff quoting: temp-script replaces nohup bash -c, LLM failure falls back to mechanical (bon-cahuwo, 8 new tests)
- Built instruction shard system: 5 plugins (bon, batterie, passe, trousse, mise) each ship instructions.md, SessionStart hooks symlink into ~/.claude/rules/ (bon-gokofa)
- Trimmed global CLAUDE.md: removed batterie-specific content, now personal preferences only
- Renamed skills: bon→open, audit→review (/open, /close, /review trio)
- Created docs/system-walkthrough/ with numbered snapshots of all plugin artifacts
- Version bump to 0.12.0, pushed bon + all 4 other plugin repos + ~/.claude

## Gotchas
- Skill renames won't take effect until `batterie-update` refreshes cache from 0.11.0→0.12.0
- New hooks in batterie/passe/trousse may need explicit registration in plugin.json — bon's plugin.json lists hooks explicitly; the new plugins have hooks/ dirs but no plugin.json entries yet
- docs/system-walkthrough/ files are snapshots, not symlinks — will drift from source
- Learned: rules/*.md supports path-scoped activation via `paths:` YAML frontmatter (not used yet, all shards are unconditional)

## Next
- Run `batterie-update` to refresh plugin cache and activate 0.12.0 (renames, shard in cache)
- Check plugin.json registration for new hooks in batterie-de-savoir, passe, trousse
- Walk through docs/system-walkthrough/ together — review each snapshot for accuracy and completeness
- Consider: should walkthrough be symlinks instead of copies? Or generated?

## Reflection
**Claude observed:** The instruction shard pattern is clean — each plugin owns its rules, hooks auto-symlink on version changes, authority level matches CLAUDE.md (not downgraded to hook output). The `@context/` vs `rules/` distinction matters: @context is hand-curated composition, rules/ is plugin-managed auto-load. Both inject into system context but ownership differs.
**User noted:** Rules files support path-scoped activation via frontmatter — agent research missed this twice. User's instinct was right. Also: "review" is better than "audit" for the backlog skill name.
