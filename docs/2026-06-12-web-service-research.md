# Research note — bon's web service (the two-faces design)

*2026-06-12, from a Cowork session, answering the research asks in the 2026-06-12 brief. Each section ends with a recommendation. Claims verified against documentation current as of today; anything inferred rather than documented is flagged.*

## 1. Can claude.ai / Cowork connect to a self-hosted remote MCP? (the load-bearing one)

**Yes, and the terms are now precisely documented.** Custom connectors via remote MCP are available on Claude.ai, Cowork, Claude Desktop, and mobile, on every plan including Free (Free is capped at one custom connector). The feature is in beta. ([Get started with custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp))

**The fact that shapes everything: the connection originates from Anthropic's cloud, not your device — even for Cowork and Claude Desktop.** The help centre is explicit: "Even though Cowork and Claude Desktop run on your computer, remote connectors are configured and brokered through your Claude account. The connection to your MCP server originates from Anthropic's servers, not from your machine's network interface." So the docket MCP must be reachable over public HTTPS from Anthropic's egress range, `160.79.104.0/21`. A service that lives only on the tailnet is invisible to every Claude surface except Claude Code running on a tailnet machine. ([Network requirements](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp), [Network reference](https://claude.com/docs/connectors/building/authentication#network-reference))

**Cowork vs claude.ai chat: no difference.** The auth docs state the same infrastructure backs Claude.ai, Desktop, mobile, Claude Code, and Cowork. One connector configuration serves all surfaces. ([Authentication for connectors](https://claude.com/docs/connectors/building/authentication))

**Auth terms.** From the [supported authentication types table](https://claude.com/docs/connectors/building/authentication#supported-authentication-types):

- `none` (authless) — **supported**. This is the floor.
- `oauth_dcr` (OAuth 2.0 + Dynamic Client Registration, RFC 7591) — supported out of the box.
- `oauth_cimd` (OAuth 2.0 + Client ID Metadata Document, from the 2025-11-25 MCP spec) — supported out of the box.
- `static_bearer` (user-pasted bearer token) — **not yet supported**. Community reports confirm tokens in query strings (`?token=...`) are also rejected ([GitHub issue](https://github.com/anthropics/claude-ai-mcp/issues/112), [sunpeak write-up](https://sunpeak.ai/blogs/claude-connector-oauth-authentication/)).
- Pure machine-to-machine `client_credentials` — not supported; every connection requires user consent.

The OAuth callback for hosted surfaces is `https://claude.ai/api/mcp/auth_callback`; Claude Code uses a loopback redirect instead, so an authorization server must accept both if both vehicles will connect. Token refresh happens reactively on 401 with proactive refresh up to five minutes before expiry. ([Callback URLs](https://claude.com/docs/connectors/building/authentication#callback-urls))

**The least-machinery bridge from a Tailscale-private hezza: `tailscale funnel`.** Funnel routes public internet traffic to a local service with automatic Let's Encrypt certificates — no port forwarding, no reverse-proxy VPS, no DNS work. Constraints worth knowing before committing ([Tailscale Funnel docs](https://tailscale.com/kb/1223/funnel)):

- Hostname is fixed to your tailnet domain: `hezza.<tailnet>.ts.net`. Ports 443, 8443, 10000 only. TLS only. Beta, with non-configurable bandwidth limits (fine for JSON verbs; not a file server).
- A port is either Serve (tailnet-only) **or** Funnel (public) — never both. This is a feature for us, not a bug: see §5.
- Funnel supports the [PROXY protocol](https://tailscale.com/docs/reference/tailscale-cli/funnel#use-the-proxy-protocol), so the app can see the real client IP — meaning the MCP endpoint can refuse anything not from `160.79.104.0/21` at the application layer. Cheap, effective hardening.
- Don't rely on hostname obscurity: Let's Encrypt certificates are published to [Certificate Transparency logs](https://letsencrypt.org/docs/ct-logs/), so the funnel hostname is discoverable by anyone who looks. (Inference from how CT works, not a Tailscale doc claim.)

**Recommendation:** treat "public HTTPS, cloud-originated" as a hard constraint and bridge with `tailscale funnel` — it is one command, gives valid certs, and the PROXY-protocol IP allowlist plus OAuth (§5) covers the exposure it creates.

## 2. MCP streamable HTTP, and one process serving both faces

**Spec status.** Streamable HTTP is the standard remote transport in the current MCP spec (version 2025-11-25); it replaced the older HTTP+SSE transport from 2024-11-05, which is retained only for backwards compatibility. The transport is a single endpoint (e.g. `/mcp`) accepting POST and GET, with optional SSE streaming inside it; the 2025-11-25 revision added an explicit requirement to return 403 for invalid Origin headers and allows servers to disconnect SSE streams at will (clients poll). ([Transports, 2025-11-25 spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), [changelog](https://modelcontextprotocol.info/specification/2025-11-25/changelog/)) Claude supports Streamable HTTP and the legacy transport, and explicitly says legacy is being deprecated — build Streamable HTTP only. Also useful for verb design: hosted surfaces have a 300-second tool timeout and a ~150,000-character tool result cap. ([Building custom connectors](https://claude.com/docs/connectors/building))

**One process is the documented happy path, not a hack.** FastMCP (v3, the `gofastmcp.com` framework) serves Streamable HTTP via `mcp.run(transport="http")` and lets you hang ordinary HTTP routes off the same server with `@mcp.custom_route("/...", methods=["GET"])` — "custom routes are served by the same web server as your MCP endpoint. They're available at the root of your domain while the MCP endpoint is at `/mcp/`." For more control, `mcp.http_app()` returns an ASGI app you mount inside a Starlette/FastAPI application alongside GUI routes, run under one uvicorn. ([Running your server — FastMCP](https://gofastmcp.com/deployment/running-server)) The official `modelcontextprotocol/python-sdk` can do the same mounting but has documented friction (307-redirect and lifespan issues when mounting `streamable_http_app` into an existing app: [#1168](https://github.com/modelcontextprotocol/python-sdk/issues/1168), [#1367](https://github.com/modelcontextprotocol/python-sdk/issues/1367)).

So the shape is: one process, one Starlette app — `/mcp` (agents, pull), `/` (board HTML), `/events` (SSE change feed), `/api/...` (the same verbs as JSON for the GUI's fetch calls). One writer inside; both faces are thin.

**Recommendation:** FastMCP v3 with `custom_route` (or `http_app()` mounted in Starlette if the GUI routes outgrow decorators), Streamable HTTP only, MCP at `/mcp`, GUI and SSE as siblings in the same process.

## 3. SSE for a tiny single-writer app

**The reconnection idiom is built into the protocol and fits the change feed exactly.** If the server stamps each SSE event with a monotonically increasing `id:` field, the browser's native `EventSource` reconnects automatically after a drop and sends the last seen id as a `Last-Event-ID` header; the server replays everything after it. Since the docket already has a single append-only change feed with ordered entries, replay is one SQL query — no buffering machinery, no gap-detection logic. ([MDN: Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events))

**Least-JavaScript GUI options**, in increasing machinery:

1. **Vanilla `EventSource` + a small render function.** Zero dependencies, auto-reconnect for free, ~30 lines. Events carry `{id, verb, actor, ts}`; the handler re-fetches or patches the affected item.
2. **htmx + its [SSE extension](https://htmx.org/extensions/sse/).** The current extension is fetch-based (POST, headers, cookies possible), tracks `Last-Event-ID` itself, reconnects with exponential backoff. Pairs with server-rendered HTML fragments: the server pushes a re-rendered item card, htmx swaps it in. Good if you want rendering logic to live server-side in one place.
3. Alpine.js — client-side reactivity without a build step, but it solves a state-management problem this app barely has.

The opinionated call: with one writer and a coarse item grain, events are rare and whole-item granular. Vanilla `EventSource` re-fetching the item (or just re-fetching `list` — the board is small) is the boring, debuggable floor. htmx becomes attractive the moment the GUI is server-rendered anyway, because then there is exactly one renderer for first paint and for updates.

**Recommendation:** server-rendered board + htmx SSE extension swapping item fragments, with vanilla `EventSource` as the fallback position if htmx feels like one dependency too many after driving the mock.

## 4. Prior art worth stealing from

**[Nullboard](https://github.com/apankrat/nullboard)** (4.1k stars) is the closest spiritual neighbour: a single-HTML-file kanban "focused on compactness and readability." Lessons that transfer directly: nearly all controls hidden until hover/focus (calm chrome, ADHD-friendly density); everything edits in place with auto-save (no modal forms); long notes collapse to their first line so the board stays one-glance scannable; a deliberately narrow-but-legible typeface (Barlow) buys real density. Its confessed caveat is the counter-lesson: written for desktop keyboard/mouse, "essentially untested on mobile" — our mock must not inherit that.

**[Kanboard](https://kanboard.org/)** — minimalist PHP board that runs happily on a Raspberry Pi; the lesson is that boring tech plus a small surface outlives feature-rich rivals ([survey](https://ones.com/blog/7-best-self-hosted-kanban-board-solutions-that-operate-without-cloud-sync/)). **tasks.php** stores everything in one JSON text file — grain validation for "the store is small, stop over-engineering it" ([awesome-selfhosted list](https://thehomelab.wiki/books/helpful-tools-resources/page/awesome-selfhosted-task-management-to-do-lists)). **Wekan** does real-time multi-client updates and is the cautionary tale: Meteor + MongoDB to push card changes — the machinery the SSE-not-CRDTs decision avoids.

**One genuinely new find: interactive connectors / MCP Apps.** Claude surfaces can now render interactive UI *from a connector* directly in the conversation — "live, interactive apps — like dashboards, **task boards**, or design tools — right in the chat," as inline cards or fullscreen views, using the same permissions as the connector. ([Use interactive connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp), [MCP Apps docs](https://claude.com/docs/connectors/building)) This means the docket MCP could *eventually* carry a rendered board into Cowork itself — the GUI face and the MCP face converging on one connector. Not for now (it's new, and the standalone GUI is the decided chapter), but it strengthens the contract's bet: verbs first, faces are interchangeable.

**Recommendation:** steal Nullboard's density habits (hidden controls, in-place edit, collapse-to-first-line), design phone-first where Nullboard didn't, and file "board-as-MCP-App inside Cowork" as a Someday/Maybe on the docket.

## 5. Auth posture, ranked by machinery

| # | Posture | Machinery | What it gets you | Killed by |
|---|---------|-----------|------------------|-----------|
| 1 | **Tailnet-only** (`tailscale serve`) | none | GUI face on every device running Tailscale, incl. phone; TLS for free | Connector terms: Anthropic's cloud can't reach it — **MCP face impossible** (§1) |
| 2 | **Funnel + authless MCP** | one command | Working connector today | Anyone who finds the URL can write to the board; CT logs make the hostname findable. Survivable for a toy *if* path is unguessable + PROXY-protocol IP allowlist; not for real briefs |
| 3 | **Funnel + OAuth (DCR)** | moderate, mostly library | The supported, durable answer | Nothing — this is what the terms want. FastMCP ships [auth providers](https://fastmcp.wiki/en/servers/auth/oauth-proxy) (OAuth Proxy for non-DCR IdPs, RemoteAuthProvider for DCR-native ones), and [fastmcp-personal-auth](https://github.com/crumrine/fastmcp-personal-auth) is a drop-in OAuth 2.1 + DCR + PKCE provider for personal servers, no external IdP, tested against Claude.ai/Desktop/mobile/Code |
| 4 | OAuth device flow | moderate | — | Not part of the connector flow at all: Claude initiates authorization-code with DCR/CIMD and its own callback URL; there is no device-flow option to plug into ([auth docs](https://claude.com/docs/connectors/building/authentication)). Eliminated |
| 5 | Token-in-URL | trivial | — | Explicitly unsupported (`static_bearer` "not yet supported"; query-param tokens rejected — §1), and leaks via logs/referrers anyway. Eliminated |

The Serve/Funnel port exclusivity (§1) enables a clean **split-horizon** posture: the human face stays tailnet-only via `tailscale serve` on 443 (no public exposure for the surface that renders everything), while only the MCP endpoint goes public via funnel on 8443 — both proxying into the same single process. The GUI face never takes on public-internet risk; the MCP face carries OAuth.

**Recommendation:** split-horizon as the target — GUI over Serve (tailnet-only), MCP over Funnel on 8443 with FastMCP's DCR-compliant OAuth (fastmcp-personal-auth or equivalent) plus PROXY-protocol IP allowlisting to `160.79.104.0/21`; permit funnel+authless-with-secret-path only as a days-long bootstrapping posture while wiring OAuth, never with real briefs flowing.

---

## Sources

- [Get started with custom connectors using remote MCP — Claude Help Center](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)
- [Authentication for connectors — Claude docs](https://claude.com/docs/connectors/building/authentication)
- [Building custom connectors — Claude docs](https://claude.com/docs/connectors/building)
- [MCP spec 2025-11-25: Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) · [changelog](https://modelcontextprotocol.info/specification/2025-11-25/changelog/)
- [Running your server — FastMCP](https://gofastmcp.com/deployment/running-server) · [OAuth Proxy — FastMCP](https://fastmcp.wiki/en/servers/auth/oauth-proxy)
- [python-sdk mounting friction: #1168](https://github.com/modelcontextprotocol/python-sdk/issues/1168) · [#1367](https://github.com/modelcontextprotocol/python-sdk/issues/1367)
- [Tailscale Funnel docs](https://tailscale.com/kb/1223/funnel) · [funnel CLI / PROXY protocol](https://tailscale.com/docs/reference/tailscale-cli/funnel)
- [Let's Encrypt CT logs](https://letsencrypt.org/docs/ct-logs/)
- [MDN: Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) · [htmx SSE extension](https://htmx.org/extensions/sse/)
- [Nullboard](https://github.com/apankrat/nullboard) · [Kanboard survey](https://ones.com/blog/7-best-self-hosted-kanban-board-solutions-that-operate-without-cloud-sync/) · [awesome-selfhosted task lists](https://thehomelab.wiki/books/helpful-tools-resources/page/awesome-selfhosted-task-management-to-do-lists)
- [fastmcp-personal-auth](https://github.com/crumrine/fastmcp-personal-auth) · [claude-ai-mcp bearer issue #112](https://github.com/anthropics/claude-ai-mcp/issues/112) · [sunpeak: Claude connector OAuth](https://sunpeak.ai/blogs/claude-connector-oauth-authentication/)
