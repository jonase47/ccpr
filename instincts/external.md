---
name: instincts-external
description: Global instincts for external HTTP fetches (bot protection, no PII), MCP-server registration and OS-specific filename quirks. Loaded as Tier-1-global topic file alongside the slim index in `~/.claude/instincts.md`. Curated starter examples — adapt and extend through your own `/postmortem` runs.
type: instincts
scope: tier-1-global-topic
last_updated: 19.05.2026
---

# External APIs / MCP / OS-Quirks Instincts

Behavioural rules for talking to external systems: WebFetch fallback strategies under bot protection, MCP-server registration order quirks and OS-specific filename traps. Sorted by confidence (descending).

---

### G-020: WebFetch bot-protection → Playwright-MCP fallback
**Confidence: 0.5** | Last confirmed: starter set

> **Rule**: Validation/research skills with desk research on consumer-oriented platforms (Reddit, Google Trends, App-Store detail pages, niche search tools) must expect bot protection (HTTP 429 / Anubis 403 / Cloudflare challenge) as the **normal** case for direct WebFetch.
>
> **Tier flow**:
> 1. **WebFetch first** (fast, cheap, ~1-3 KB per page).
> 2. **On HTTP 429 / 403 / 404 without auth-wall**: switch to Playwright MCP (`mcp__playwright__browser_navigate` + `browser_wait_for` + `browser_snapshot` / `browser_evaluate` for targeted DOM extraction). Real browser fingerprints typically pass Anubis/Cloudflare challenges; JS-rendered content becomes readable.
> 3. **Only after both fail**: mark the data point as open + document a method recommendation for the next gate's carry-forward.
>
> **Auth-walled sources** (Apple Connect, AppFollow Pro, SensorTower Pro) stay manual stakeholder tasks regardless of tool — no point trying Playwright there.
>
> **Briefing requirement**: When prompting research agents, list both `WebFetch` AND `mcp__playwright__browser_*` in the tool guidance, otherwise the agent's tool pool may exclude Playwright by default.
>
> **Sub-rule for academic-publisher paywalls**: WebFetch on `mdpi.com`, `onlinelibrary.wiley.com`, `tandfonline.com`, `sciencedirect.com`, `springer.com`, `nature.com` returns 403/404 as the **default**, not as an edge case. Playwright does NOT help (auth-wall, not bot-wall). Tier flow for DOI sources:
> 1. Try `https://api.openalex.org/works/doi:<DOI>` for metadata + OA status.
> 2. If `oa_status: gold/green/hybrid` → fetch `oa_url` (PMC, biorxiv, repository) for full text.
> 3. If `oa_status: closed` → use the abstract from OpenAlex/CrossRef, mark transparently as "abstract-only, paywalled".
> 4. Full-text WebFetch on the publisher URL is only worth trying after steps 1–3.

---

### G-026: Avoid `skill.md` (and other SKILL system filenames) in `.claude/commands/` on macOS
**Confidence: 0.5** | Last confirmed: starter set

> **Rule**: On macOS (APFS/HFS+ default case-insensitive), the skill scanner interprets `.md` files named `skill.md` as `SKILL.md` and registers the **entire parent directory** as a single skill (skill name = directory name). All other slash-command files in the same folder become invisible.
>
> **Symptom**: `/<command>` does not appear in the slash-command picker; in the available-skills listing an entry like `commands: /skill <level> – ...` shows up — the **directory name** as the skill name carrying the content of the colliding file.
>
> **Fix**: rename the file (e.g. `skill.md` → `skill-level.md`), update internal examples + doc references (the file itself, README, how-to docs, optionally a changelog entry). Respect historical changelog entries — do not rewrite them retroactively.
>
> **Preventive rule**: Generally avoid filenames in `.claude/commands/` or `.claude/agents/` that collide with skill-system conventions (`SKILL.md`, `PLUGIN.md`, `AGENT.md`). Even lowercase is unsafe on case-insensitive filesystems.
>
> **Context**: Any project with `.claude/commands/` or `.claude/agents/` discovery on macOS. On Linux (case-sensitive ext4/btrfs) the problem does not occur, but cross-platform distributions should avoid the collision regardless.

---

### G-031: `claude mcp add` — server name as the first positional, not after `-s` / `-e` flags
**Confidence: 0.4** | Last confirmed: starter set

> **Rule**: The `claude mcp add` command expects the server name as the **first positional**, **before** flags like `-s <scope>` or `-e KEY=value` and before the `--` separator. Wrong order produces the parse error `Invalid environment variable format: <ServerName>, environment variables should be added as: -e KEY1=value1 -e KEY2=value2`, because the parser interprets the server name as the value to the last `-e` flag. The error text is misleading: it is **not** a quoting problem, it is a positional problem.
>
> **Wrong**:
> ```
> claude mcp add -s user \
>   -e XCODEBUILDMCP_SENTRY_DISABLED=true \
>   -e XCODEBUILDMCP_ENABLED_WORKFLOWS=simulator,ui-automation,debugging \
>   XcodeBuildMCP -- npx -y xcodebuildmcp@latest mcp
> ```
>
> **Right**:
> ```
> claude mcp add XcodeBuildMCP -s user \
>   -e XCODEBUILDMCP_SENTRY_DISABLED=true \
>   -e XCODEBUILDMCP_ENABLED_WORKFLOWS=simulator,ui-automation,debugging \
>   -- npx -y xcodebuildmcp@latest mcp
> ```
>
> **Mitigation**: Before every `claude mcp add` mentally check the argument order (`add <NAME> [flags] -- <cmd>`). On a parse error with "Invalid environment variable format: <NAME>", change the positional order first, **not** the quotes.
>
> **Context**: MCP-server (re-)registration with environment variables. Risk increases on re-setup after `claude mcp remove`, because the original registration is often undocumented setup output and no template exists.
