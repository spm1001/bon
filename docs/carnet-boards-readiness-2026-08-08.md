# Serving bon's boards to browser-based Claude sessions — design review

**Date:** 2026-08-08 · **Status:** design-time review, banked for the bon-wutime verdict.

This is a review of our own system, deciding whether to build a thing we have not built yet. A Cowork or claude.ai session can read our repos through carnet today but cannot touch the bon boards, because those live in Dolt on tube. The question is whether to close that gap by routing board verbs through a Cloudflare Worker and a tunnel to tube — and what would need tidying first.

Two code reads this session inform it: carnet's full source, and mary-bujournal + its engine, which were built later and made several choices we should copy. File references point at our own code and are there to make the follow-up work actionable.

## The proposed shape

```
Cowork / claude.ai session
  → MCP over HTTPS + OAuth        (Worker on Cloudflare)
  → Cloudflare Tunnel             (cloudflared dials out from tube; one hostname → one local port)
  → verb daemon on tube           (wraps storage.py; the edge-tier verbs only)
  → Dolt on localhost
```

The useful property is that the browser session's sandbox never touches our network. An MCP tool call runs at the Worker, and the Worker reaches tube only down a tunnel that tube itself opened outward. Nothing new listens on the internet at our end. That pattern already runs here — the piano tunnel does exactly this, one hostname to one local port with a catch-all 404 for everything else.

## The finding that reorders the work

The tunnel leg is the sound part. The part that needs attention is carnet's own front door, and it needs attention whether or not we ever build this.

Carnet's login is a single shared password checked against `SETUP_PASSWORD`, and there is no limit on how many times it can be tried (`carnet/src/index.ts:98-124`). Successful logins are not recorded at all, and failures are logged without the caller's address, so we cannot answer "who obtained access, and when" from the logs. The board already half-knows this: `carnet-mesose`'s brief named the missing rate limit, that item was closed as superseded rather than fixed, and its replacement `carnet-japase` — the decision about one auth mechanism for Mary, Sameer and the Claudes — is still at step one. Sameer's own `carnet-piteru` from 1 August puts it plainly: carnet is the more exposed surface and should not lag BuJo.

So the sequencing is: **tidy the front door first, then decide about boards.** Adding board verbs behind an unhardened login would make the login's weakness matter considerably more than it does today.

## What BuJo already solved, and we should just copy

The mary-bujournal engine was built after carnet, and its July review left three patterns worth lifting wholesale.

**A login throttle, from birth.** BuJo's door limits attempts per address over a rolling window and checks that *before* doing the expensive verification, so a flood of attempts costs nothing (`mary-bujournal-engine/src/door/throttle.ts`). Its handoff extracted the general rule after finding its own door had shipped without one: throttle every new login surface from the start, at parity with its siblings. Carnet has no equivalent. This is the single highest-value thing to copy and it is a small amount of code.

**One credential per door, revocable on its own.** BuJo runs two Workers over one store, and each holds its own separate GitHub credential scoped to just what it needs — the door's provably cannot write the notes repo (`wrangler.door.jsonc:35-37`). The engine's understanding.md is explicit that widening carnet to also cover the journal was considered and refused, because that would dissolve the boundary the split exists to hold. That reasoning transfers directly: board verbs want a *sibling* Worker sharing carnet's code by import, not a bigger carnet. Then a problem with one door doesn't reach the other, and credentials can be replaced independently.

**Writer-stamped history.** Every BuJo write commits with a prefix naming which door made it, so the git log stays meaningful about provenance. Our equivalent is stamping origin into `created_by`/`updated_by`, which keeps Dolt's history readable about which surface changed what.

There's also a passkey ceremony sitting in `mary-bujournal-engine/src/auth/webauthn.ts`, written deliberately portable with in-code comments naming carnet as the intended second home — that's the `carnet-zecoja` backport you half-remembered. It's the eventual answer to the shared-password gate, and it's blocked behind `carnet-japase`, because passkeys are lovely for humans and unhelpful for a non-interactive Claude. That decision needs making before the code moves.

## Going hop by hop

**The caller.** A perfectly legitimate Claude can be misled by content it reads, so the verbs it can reach should be the boring ones — list, ready, show, new, done, edit — and not archive, migrate or register. Two things make mistakes survivable: every board write is a Dolt commit, so it is visible and one revert from repaired; and a size check plus a "this call would change an unreasonable number of items" tripwire in the daemon, which is the shape BuJo uses in its store (`src/journal-store.ts:26-55`) and deliberately keeps as a tripwire rather than a lock, since git is the backstop.

**The Worker's public edge.** Worth knowing for any future work here: only paths under `/mcp` are gated. Everything else falls through to the default handler with no authentication (`carnet/src/index.ts:45-62`), so a new route added without thinking is open by default. Client registration is also open, which is normal for this protocol but means the login prompt is reachable by anyone — which is precisely why the throttle matters. Also worth pinning the OAuth library to an exact version; carnet currently floats it on a caret range with no lockfile install discipline.

**Worker to tunnel.** The tunnel hostname resolves publicly, so it needs its own gate rather than relying on obscurity. Two independent ones: a Cloudflare Access service-token policy on that hostname, so only the Worker can traverse it, and a token check in the daemon itself, so an Access misconfiguration doesn't silently open the door. Give it a separate tunnel and systemd unit from piano's rather than adding ingress to the existing one, so the two can be stopped and started independently.

**The daemon on tube.** Bind to localhost. Wrap the docket package so validation, dedup, unblock-on-done and atomic writes are literally the same code every other surface runs — verbs rather than SQL, so we never re-implement bon's invariants in TypeScript and watch them drift. Log every request at this end, because this is the log we own.

**Reads versus writes.** These are asymmetric and it's the most useful thing to hold on to. Writes announce themselves — a Dolt commit, diffable and revertible. Reads leave no trace at all unless we make one. So the request log at the tube end is not bureaucracy; it's the only visibility we get into the read side.

**What the boards actually contain.** Work memory: briefs, project context, infrastructure notes, ITV project names. No credentials, by standing practice. That's the thing a read leak would expose, and it's what the residual risk is measured against.

## The Tailscale question

Tailscale can't gate this edge, and the reason is structural rather than a limitation we could engineer around: neither Cloudflare Workers nor Anthropic's MCP infrastructure can join a tailnet. The caller is outside, in every version of this design.

The alternative worth naming is dropping Cloudflare entirely and using Tailscale Funnel to expose an MCP server running directly on tube. But Funnel is also a public edge, and we'd then have to implement streaming MCP and OAuth ourselves in the daemon, losing the Worker code we already run and trust. So: Tailscale keeps carrying the private legs it already carries, and the public edge is gated by OAuth (who may call verbs) plus a service token (who may cross the tunnel) plus the daemon's own check.

## What I'd do, in order

1. **Harden carnet's login** — the throttle from BuJo, plus logging that records successes as well as failures with the caller's address. Do this regardless of the boards decision.
2. **Sibling door, not a bigger carnet** — share the code, separate the instance, the secrets and the credentials.
3. **Then the tunnel leg** — dedicated tunnel, Access service token, daemon token check.
4. **Daemon discipline** — localhost, boring verbs, docket-package validation, origin stamping, request log, the mass-change tripwire.
5. **Resolve `carnet-japase`** and the passkey follows naturally.

One adjacent tidy-up, unrelated to any of this: Dolt currently listens on all interfaces, so it's reachable across the LAN. Binding it to localhost and the Tailscale interface is a two-minute change and worth doing on its own merits.

## Where that leaves the residual

An authenticated, throttled, logged, single-tenant read path onto work memory, with writes that are attributable and revertible. What's left after all of the above is a leaked token inside its lifetime, or a legitimate Claude misusing the verbs it legitimately has — both bounded by the logs, the limited verb set, and Dolt's history. That's a reasonable place to land for this kind of content, and it's the judgement that stays Sameer's.

## Sources

- Code read of `spm1001/carnet` (this session) — login flow at `src/index.ts:98-149`, routing at `src/index.ts:45-62`, write path in `src/do.ts` / `src/github.ts`.
- Code read of `spm1001/mary-bujournal` + `mary-bujournal-engine` (this session) — `src/door/throttle.ts`, `src/auth/webauthn.ts`, `wrangler.door.jsonc:35-37`, `src/journal-store.ts:26-55`, and the two-door reasoning in `docs/understanding.md`.
- Live on tube, 2026-08-08 — `~/.cloudflared/config.yml` (the single-ingress pattern), `ss -ltnp` (Dolt's listener).
- Board context — `carnet-japase`, `carnet-piteru`, `carnet-mesose`, `bon-wutime`, `bon-hitene`.
