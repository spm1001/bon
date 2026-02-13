# Field Report: -q/--quiet flag inconsistency across commands

**Source:** pi-config session (Feb 2026)
**Observer:** Claude working in pi harness

## Context

While scripting arc commands (marking items done, creating + closing in one flow), hit an ergonomic friction point.

## Observation

`arc new` supports `-q/--quiet` for minimal output (just prints ID):
```bash
$ arc new "title" --for parent --why X --what Y --done Z -q
arc-abc123
```

But `arc done` doesn't accept the flag:
```bash
$ arc done arc-abc123 -q
arc: error: unrecognized arguments: -q
```

This creates inconsistency. When I tried `arc done pi-fitope -q`, I expected it to work (quiet output, just success/failure signal) but got an error instead.

## Expected Behavior

**Either:**
1. **All commands support -q** — consistent across new/done/edit/etc.
2. **No commands support -q** — rely on exit codes for scripting

**My preference:** Option 1. When scripting flows like "create item → work → mark done → commit", quiet mode reduces noise. Exit codes already provide success/failure, -q just controls verbosity.

## Current Workarounds

- Redirect output: `arc done ID >/dev/null`
- Parse output: `arc done ID | grep -q "Done"`
- Just live with verbose output

None are terrible, but -q would be cleaner.

## Impact

Low severity - this is ergonomic polish, not broken functionality. But when filing items for record-keeping (create then immediately close), the asymmetry is jarring.

---

*Filed as field report per trousse conventions. Not urgent - just knowledge transfer for future consideration.*
