/**
 * Arc Harness — Structural enforcement for Arc-tracked sessions
 *
 * A Pi extension that replaces honour-system CLAUDE.md instructions with
 * code that runs. Enforces session lifecycle, gates tool execution,
 * injects state after compaction, validates turns, and renders the
 * Centre Pompidou display — the building shows its own pipes.
 *
 * Install: copy to .pi/extensions/arc-harness.ts (project) or
 *          ~/.pi/agent/extensions/arc-harness.ts (global)
 *
 * Requires: arc CLI in PATH, .arc/ directory in project root.
 */

import type { ExtensionAPI, ExtensionContext } from "@mariozechner/pi-coding-agent";
import { Text, truncateToWidth } from "@mariozechner/pi-tui";

// ─── State Machine ──────────────────────────────────────────────────────

type SessionPhase = "init" | "context_loaded" | "working" | "checkpoint" | "closing";

interface HarnessState {
	phase: SessionPhase;

	// Arc state
	arcPresent: boolean;
	arcPrefix: string;
	arcItems: ArcItem[];
	currentAction: string | null;    // ID of action being worked
	currentOutcome: string | null;   // ID of parent outcome
	tacticalActive: boolean;
	tacticalStep: number;
	tacticalTotal: number;
	itemsCompletedThisSession: string[];

	// Skills
	skillsRequired: Map<string, string[]>; // tool pattern → skill files needed
	skillsLoaded: Set<string>;             // skill files read this session

	// Token tracking
	turnCount: number;
	tokenEstimate: number;
	checkpointThreshold: number;       // percentage (0-100)
	checkpointNeeded: boolean;
	lastCheckpointTurn: number;

	// Obligations
	drawDownDone: boolean;             // has the agent read the brief + set up tactical?
	handoffWritten: boolean;
	pendingObligations: string[];

	// Display
	sessionLabel: string;
}

interface ArcItem {
	id: string;
	type: "outcome" | "action";
	title: string;
	status: "open" | "done";
	parent?: string | null;
	waiting_for?: string | null;
	tactical?: { steps: string[]; current: number } | null;
	brief?: { why: string; what: string; done: string };
	order?: number;
}

// ─── Defaults & Config ──────────────────────────────────────────────────

const DEFAULT_CHECKPOINT_THRESHOLD = 75; // percent of token budget
const TOKEN_PER_TURN_ESTIMATE = 4000;    // rough heuristic
const TOKEN_BUDGET = 200000;             // Claude's context window ballpark

// Skill gate rules: tool name patterns → required skill files
const DEFAULT_SKILL_GATES: Record<string, string[]> = {
	// Example: if you have a "xlsx" skill that should be read before
	// creating spreadsheets, add it here:
	// "create_spreadsheet": ["skills/xlsx.md"],
};

// ─── Helpers ────────────────────────────────────────────────────────────

function createInitialState(): HarnessState {
	return {
		phase: "init",
		arcPresent: false,
		arcPrefix: "arc",
		arcItems: [],
		currentAction: null,
		currentOutcome: null,
		tacticalActive: false,
		tacticalStep: 0,
		tacticalTotal: 0,
		itemsCompletedThisSession: [],
		skillsRequired: new Map(Object.entries(DEFAULT_SKILL_GATES)),
		skillsLoaded: new Set(),
		turnCount: 0,
		tokenEstimate: 0,
		checkpointThreshold: DEFAULT_CHECKPOINT_THRESHOLD,
		checkpointNeeded: false,
		lastCheckpointTurn: 0,
		drawDownDone: false,
		handoffWritten: false,
		pendingObligations: [],
		sessionLabel: "",
	};
}

/**
 * Run arc CLI and return stdout, or null on failure.
 */
async function arcCommand(args: string[], cwd?: string): Promise<string | null> {
	const { execFile } = await import("node:child_process");
	const { promisify } = await import("node:util");
	const execFileAsync = promisify(execFile);
	try {
		const result = await execFileAsync("arc", args, {
			cwd: cwd || process.cwd(),
			timeout: 5000,
		});
		return result.stdout.trim();
	} catch {
		return null;
	}
}

/**
 * Parse arc list --json output into items.
 */
function parseArcJson(jsonStr: string): ArcItem[] {
	try {
		const data = JSON.parse(jsonStr);
		const items: ArcItem[] = [];
		for (const outcome of data.outcomes || []) {
			const { actions, ...rest } = outcome;
			items.push(rest as ArcItem);
			for (const action of actions || []) {
				items.push(action as ArcItem);
			}
		}
		for (const standalone of data.standalone || []) {
			items.push(standalone as ArcItem);
		}
		return items;
	} catch {
		return [];
	}
}

/**
 * Load current Arc state from disk.
 */
async function loadArcState(state: HarnessState): Promise<void> {
	const fs = await import("node:fs");

	// Check .arc/ exists
	if (!fs.existsSync(".arc")) {
		state.arcPresent = false;
		return;
	}
	state.arcPresent = true;

	// Load prefix
	try {
		state.arcPrefix = fs.readFileSync(".arc/prefix", "utf-8").trim() || "arc";
	} catch {
		state.arcPrefix = "arc";
	}

	// Load all items (including done, for full state)
	const allJson = await arcCommand(["list", "--all", "--json"]);
	if (allJson) {
		state.arcItems = parseArcJson(allJson);
	}

	// Check for active tactical
	const currentOutput = await arcCommand(["show", "--current"]);
	if (currentOutput) {
		// Parse "Working: <title> (<id>)"
		const match = currentOutput.match(/Working:\s+(.+?)\s+\(([^)]+)\)/);
		if (match) {
			state.currentAction = match[2];
			state.tacticalActive = true;
			// Find tactical details from items
			const item = state.arcItems.find((i) => i.id === match[2]);
			if (item?.tactical) {
				state.tacticalStep = item.tactical.current;
				state.tacticalTotal = item.tactical.steps.length;
			}
			// Find parent outcome
			if (item?.parent) {
				state.currentOutcome = item.parent;
			}
		}
	}

	// Derive session label
	if (state.currentAction) {
		const action = state.arcItems.find((i) => i.id === state.currentAction);
		if (action) {
			state.sessionLabel = `${state.currentAction} "${action.title}"`;
		}
	} else {
		const openOutcomes = state.arcItems.filter((i) => i.type === "outcome" && i.status === "open");
		if (openOutcomes.length === 1) {
			state.sessionLabel = `${openOutcomes[0].id} "${openOutcomes[0].title}"`;
		} else {
			state.sessionLabel = `${openOutcomes.length} open outcomes`;
		}
	}
}

/**
 * Build obligations list based on current state.
 */
function deriveObligations(state: HarnessState): string[] {
	const obligations: string[] = [];

	if (state.phase === "working" && state.currentAction && !state.drawDownDone) {
		obligations.push(`Draw down ${state.currentAction} (arc show → arc work → arc step)`);
	}

	if (state.tacticalActive && state.tacticalStep < state.tacticalTotal) {
		const action = state.arcItems.find((i) => i.id === state.currentAction);
		if (action?.tactical) {
			const currentStepName = action.tactical.steps[state.tacticalStep] || "current step";
			obligations.push(`Complete: ${currentStepName} → then run arc step`);
		}
	}

	if (state.checkpointNeeded) {
		obligations.push("Checkpoint: token budget at threshold, save state");
	}

	if (state.phase === "closing" && !state.handoffWritten) {
		obligations.push("Write handoff notes before session close");
	}

	return obligations;
}

// ─── Rogers Display ─────────────────────────────────────────────────────

/**
 * Render the Centre Pompidou display — the visible state machine.
 *
 * Both Claude and the human can see:
 *   where in the workflow they are,
 *   what obligations are pending,
 *   what gates are coming next,
 *   which skills are loaded,
 *   token budget and checkpoint thresholds.
 */
function renderRogers(state: HarnessState, width: number, theme: any): string[] {
	const lines: string[] = [];

	if (!state.arcPresent) {
		return [theme.fg("dim", "  [arc-harness] No .arc/ directory detected")];
	}

	const w = Math.max(width, 60);

	// Phase indicators
	const phases: { key: SessionPhase; label: string }[] = [
		{ key: "init", label: "OPEN" },
		{ key: "context_loaded", label: "LOADED" },
		{ key: "working", label: "WORKING" },
		{ key: "checkpoint", label: "CHECKPOINT" },
		{ key: "closing", label: "CLOSING" },
	];

	const phaseStr = phases
		.map((p) => {
			if (p.key === state.phase) {
				return theme.fg("accent", theme.bold(`[${p.label}]`));
			}
			const phaseOrder = phases.map((x) => x.key);
			const currentIdx = phaseOrder.indexOf(state.phase);
			const thisIdx = phaseOrder.indexOf(p.key);
			if (thisIdx < currentIdx) {
				return theme.fg("success", `*${p.label}`);
			}
			return theme.fg("dim", p.label);
		})
		.join(theme.fg("borderMuted", " -> "));

	// Token budget bar
	const tokenPct = Math.min(100, Math.round((state.tokenEstimate / TOKEN_BUDGET) * 100));
	const barLen = 10;
	const filled = Math.round((tokenPct / 100) * barLen);
	const bar = "=".repeat(filled) + "-".repeat(barLen - filled);
	const tokenColor = tokenPct > state.checkpointThreshold ? "error" : tokenPct > 60 ? "warning" : "success";
	const tokenStr = theme.fg(tokenColor, `[${bar}]`) + theme.fg("muted", ` ${tokenPct}%`);

	// Arc status
	const openOutcomes = state.arcItems.filter((i) => i.type === "outcome" && i.status === "open");
	const totalActions = state.arcItems.filter((i) => i.type === "action");
	const doneActions = totalActions.filter((i) => i.status === "done");
	const arcStatus = theme.fg("muted", `Arc: ${doneActions.length}/${totalActions.length} actions done, ${openOutcomes.length} outcomes open`);

	// Skills
	const skillsStr =
		state.skillsLoaded.size > 0
			? Array.from(state.skillsLoaded)
					.map((s) => theme.fg("accent", `[${s.replace(/.*\//, "").replace(/\.md$/, "")}]`))
					.join(" ")
			: theme.fg("dim", "[none]");

	// Current work
	let workStr = "";
	if (state.currentAction) {
		const action = state.arcItems.find((i) => i.id === state.currentAction);
		if (action) {
			workStr = theme.fg("text", action.title);
			if (state.tacticalActive) {
				workStr += theme.fg("muted", ` (step ${state.tacticalStep + 1}/${state.tacticalTotal})`);
			}
		}
	}

	// Next gate
	let nextGate = "";
	if (!state.drawDownDone && state.currentAction) {
		nextGate = "draw-down (arc show -> arc work)";
	} else if (state.checkpointNeeded) {
		nextGate = "checkpoint (save state)";
	} else if (tokenPct > state.checkpointThreshold - 10) {
		nextGate = `checkpoint at ${state.checkpointThreshold}%`;
	} else {
		nextGate = "none imminent";
	}

	// Obligations
	const obligations = deriveObligations(state);
	state.pendingObligations = obligations;

	// Build display
	const border = theme.fg("borderMuted", "-".repeat(w - 4));
	const title = state.sessionLabel
		? theme.fg("accent", ` SESSION: ${state.sessionLabel} `)
		: theme.fg("accent", " ARC HARNESS ");

	lines.push("");
	lines.push(truncateToWidth(`  ${theme.fg("borderMuted", "+-")}${title}${border}`, w));
	lines.push(truncateToWidth(`  ${theme.fg("borderMuted", "|")}  ${phaseStr}`, w));
	lines.push(truncateToWidth(`  ${theme.fg("borderMuted", "|")}`, w));
	if (workStr) {
		lines.push(truncateToWidth(`  ${theme.fg("borderMuted", "|")}  Working: ${workStr}`, w));
	}
	lines.push(truncateToWidth(`  ${theme.fg("borderMuted", "|")}  Skills: ${skillsStr}  Tokens: ${tokenStr}`, w));
	lines.push(truncateToWidth(`  ${theme.fg("borderMuted", "|")}  ${arcStatus}`, w));
	lines.push(truncateToWidth(`  ${theme.fg("borderMuted", "|")}  Next gate: ${theme.fg("warning", nextGate)}`, w));

	if (obligations.length > 0) {
		lines.push(truncateToWidth(`  ${theme.fg("borderMuted", "|")}`, w));
		lines.push(truncateToWidth(`  ${theme.fg("borderMuted", "|")}  ${theme.fg("warning", "Pending:")}`, w));
		for (const ob of obligations) {
			lines.push(truncateToWidth(`  ${theme.fg("borderMuted", "|")}  ${theme.fg("dim", "- " + ob)}`, w));
		}
	}

	lines.push(truncateToWidth(`  ${theme.fg("borderMuted", "+" + "-".repeat(w - 5))}`, w));
	lines.push("");

	return lines;
}

// ─── Context Injection ──────────────────────────────────────────────────

/**
 * Build the state summary injected into context before each LLM call.
 * This survives compaction because the extension re-injects it.
 */
function buildContextInjection(state: HarnessState): string {
	if (!state.arcPresent) return "";

	const lines: string[] = [];
	lines.push("=== ARC HARNESS STATE (auto-injected, do not remove) ===");
	lines.push(`Phase: ${state.phase}`);
	lines.push(`Turn: ${state.turnCount}`);

	if (state.currentAction) {
		const action = state.arcItems.find((i) => i.id === state.currentAction);
		lines.push(`Working on: ${state.currentAction} — ${action?.title || "unknown"}`);
		if (state.tacticalActive) {
			lines.push(`Tactical: step ${state.tacticalStep + 1}/${state.tacticalTotal}`);
			if (action?.tactical) {
				const step = action.tactical.steps[state.tacticalStep];
				if (step) lines.push(`Current step: ${step}`);
			}
		}
	}

	const tokenPct = Math.min(100, Math.round((state.tokenEstimate / TOKEN_BUDGET) * 100));
	lines.push(`Token budget: ~${tokenPct}%`);

	if (state.checkpointNeeded) {
		lines.push("!! CHECKPOINT NEEDED — save state before continuing !!");
	}

	const obligations = deriveObligations(state);
	if (obligations.length > 0) {
		lines.push("");
		lines.push("Pending obligations:");
		for (const ob of obligations) {
			lines.push(`  - ${ob}`);
		}
	}

	// Ready work summary
	const readyActions = state.arcItems.filter(
		(i) => i.type === "action" && i.status === "open" && !i.waiting_for,
	);
	if (readyActions.length > 0 && !state.currentAction) {
		lines.push("");
		lines.push("Ready actions:");
		for (const a of readyActions.slice(0, 5)) {
			lines.push(`  ${a.id}: ${a.title}`);
		}
		if (readyActions.length > 5) {
			lines.push(`  ... and ${readyActions.length - 5} more`);
		}
	}

	lines.push("=== END HARNESS STATE ===");
	return lines.join("\n");
}

// ─── Main Extension ─────────────────────────────────────────────────────

export default function arcHarness(pi: ExtensionAPI) {
	let state = createInitialState();

	// ── State reconstruction from session history ──

	const reconstructState = async (ctx: ExtensionContext) => {
		state = createInitialState();
		await loadArcState(state);

		// Scan session for harness state markers
		for (const entry of ctx.sessionManager.getBranch()) {
			if (entry.type !== "message") continue;
			const msg = entry.message;

			// Track tool results to detect arc commands and skill reads
			if (msg.role === "toolResult") {
				// Detect arc CLI usage
				if (msg.toolName === "bash") {
					const text = typeof msg.content === "string" ? msg.content : "";
					if (text.includes("arc step")) {
						state.drawDownDone = true;
					}
					if (text.includes("arc work")) {
						state.drawDownDone = true;
					}
				}

				// Detect file reads (skill loading)
				if (msg.toolName === "read_file" || msg.toolName === "readFile") {
					const details = msg.details as any;
					const filePath = details?.path || details?.file_path || "";
					if (typeof filePath === "string" && filePath.includes("skill")) {
						state.skillsLoaded.add(filePath);
					}
				}
			}

			state.turnCount++;
		}

		state.tokenEstimate = state.turnCount * TOKEN_PER_TURN_ESTIMATE;

		// Determine phase
		if (state.currentAction && state.drawDownDone) {
			state.phase = "working";
		} else if (state.arcPresent) {
			state.phase = "context_loaded";
		}

		// Check if checkpoint needed
		const tokenPct = (state.tokenEstimate / TOKEN_BUDGET) * 100;
		if (tokenPct >= state.checkpointThreshold) {
			state.checkpointNeeded = true;
		}
	};

	// ── Session lifecycle ──

	pi.on("session_start", async (_event, ctx) => {
		await reconstructState(ctx);
	});

	pi.on("session_switch", async (_event, ctx) => {
		await reconstructState(ctx);
	});

	pi.on("session_fork", async (_event, ctx) => {
		await reconstructState(ctx);
	});

	pi.on("session_tree", async (_event, ctx) => {
		await reconstructState(ctx);
	});

	pi.on("session_compact", async (_event, ctx) => {
		// Critical: re-inject state after compaction wipes context
		await loadArcState(state);
		// State persists in the extension's memory — the LLM will get it
		// via the context event on the next turn.
	});

	// ── Before agent start: inject Arc context ──

	pi.on("before_agent_start", async (_event, ctx) => {
		if (!state.arcPresent) return;

		// Refresh Arc state from disk (may have changed since session start)
		await loadArcState(state);

		if (state.phase === "init") {
			state.phase = "context_loaded";
		}
	});

	// ── Context: modify messages before LLM call ──

	pi.on("context", async (event, _ctx) => {
		if (!state.arcPresent) return;

		// Inject harness state as a system-level reminder
		const injection = buildContextInjection(state);
		if (injection && event.messages) {
			// Add as a system message at the end of the message array
			event.messages.push({
				role: "user",
				content: `<arc-harness>\n${injection}\n</arc-harness>`,
			});
		}
	});

	// ── Tool call interception: skill gates ──

	pi.on("tool_call", async (event, ctx) => {
		if (!state.arcPresent) return;

		const toolName = event.name || "";

		// Check skill gates
		for (const [pattern, requiredSkills] of state.skillsRequired) {
			if (toolName.includes(pattern)) {
				const unloaded = requiredSkills.filter((s) => !state.skillsLoaded.has(s));
				if (unloaded.length > 0) {
					// Notify — in a production harness you could block the tool call
					ctx.ui.notify(
						`Skill gate: read ${unloaded.join(", ")} before using ${toolName}`,
						"warning",
					);
				}
			}
		}

		// Track arc CLI calls
		if (toolName === "bash" || toolName === "execute_bash") {
			const args = event.arguments || {};
			const command = typeof args.command === "string" ? args.command : "";

			if (command.includes("arc step")) {
				// Will be verified after execution in turn_end
			}
			if (command.includes("arc done")) {
				const idMatch = command.match(/arc done\s+(\S+)/);
				if (idMatch) {
					state.itemsCompletedThisSession.push(idMatch[1]);
				}
			}
			if (command.includes("arc work")) {
				state.drawDownDone = true;
			}
		}
	});

	// ── Turn tracking ──

	pi.on("turn_start", async (_event, _ctx) => {
		state.turnCount++;
		state.tokenEstimate = state.turnCount * TOKEN_PER_TURN_ESTIMATE;
	});

	pi.on("turn_end", async (_event, ctx) => {
		if (!state.arcPresent) return;

		// Refresh Arc state to see if anything changed
		await loadArcState(state);

		// Check for phase transitions
		if (state.currentAction && state.drawDownDone && state.phase === "context_loaded") {
			state.phase = "working";
		}

		// Token checkpoint check
		const tokenPct = (state.tokenEstimate / TOKEN_BUDGET) * 100;
		if (tokenPct >= state.checkpointThreshold && !state.checkpointNeeded) {
			state.checkpointNeeded = true;
			state.phase = "checkpoint";
			ctx.ui.notify(
				`Token budget at ~${Math.round(tokenPct)}%. Checkpoint recommended.`,
				"warning",
			);
		}

		// Post-turn validation: if tactical steps active, check progress
		if (state.tacticalActive && state.currentAction) {
			const action = state.arcItems.find((i) => i.id === state.currentAction);
			if (action?.tactical) {
				const newStep = action.tactical.current;
				if (newStep > state.tacticalStep) {
					state.tacticalStep = newStep;
					// Step advanced — good
				}
			}
		}
	});

	// ── Session shutdown validation ──

	pi.on("session_shutdown", async (_event, ctx) => {
		if (!state.arcPresent) return;

		state.phase = "closing";

		// Validate: were items completed properly?
		if (state.currentAction && state.tacticalActive) {
			const action = state.arcItems.find((i) => i.id === state.currentAction);
			if (action && action.status === "open" && action.tactical) {
				const remaining = action.tactical.steps.length - action.tactical.current;
				if (remaining > 0) {
					ctx.ui.notify(
						`Session closing with ${remaining} tactical steps remaining on ${state.currentAction}. Consider filing handoff.`,
						"warning",
					);
				}
			}
		}
	});

	// ── Commands ──

	pi.registerCommand("harness", {
		description: "Show arc harness state and obligations",
		handler: async (_args, ctx) => {
			if (!ctx.hasUI) {
				ctx.ui.notify("Harness requires interactive mode", "error");
				return;
			}

			// Refresh state
			await loadArcState(state);

			await ctx.ui.custom<void>((_tui, theme, _kb, done) => {
				return {
					handleInput(data: string) {
						// Any key dismisses
						done();
					},
					render(width: number): string[] {
						return renderRogers(state, width, theme);
					},
				};
			});
		},
	});

	pi.registerCommand("obligations", {
		description: "Show pending harness obligations",
		handler: async (_args, ctx) => {
			const obligations = deriveObligations(state);
			if (obligations.length === 0) {
				ctx.ui.notify("No pending obligations", "info");
			} else {
				ctx.ui.notify(
					"Obligations:\n" + obligations.map((o) => `  - ${o}`).join("\n"),
					"warning",
				);
			}
		},
	});

	pi.registerCommand("gate", {
		description: "Check gate status (skills, draw-down, checkpoint)",
		handler: async (_args, ctx) => {
			const gates: string[] = [];

			// Skill gates
			for (const [pattern, requiredSkills] of state.skillsRequired) {
				const unloaded = requiredSkills.filter((s) => !state.skillsLoaded.has(s));
				if (unloaded.length > 0) {
					gates.push(`Skill gate [${pattern}]: need ${unloaded.join(", ")}`);
				}
			}

			// Draw-down gate
			if (state.currentAction && !state.drawDownDone) {
				gates.push(`Draw-down gate: ${state.currentAction} needs arc show -> arc work`);
			}

			// Checkpoint gate
			const tokenPct = Math.round((state.tokenEstimate / TOKEN_BUDGET) * 100);
			if (state.checkpointNeeded) {
				gates.push(`Checkpoint gate: at ${tokenPct}%, threshold is ${state.checkpointThreshold}%`);
			}

			if (gates.length === 0) {
				ctx.ui.notify("All gates clear", "info");
			} else {
				ctx.ui.notify("Active gates:\n" + gates.map((g) => `  ! ${g}`).join("\n"), "warning");
			}
		},
	});

	// ── Widget: persistent Rogers display ──
	// Rendered after every agent turn via the turn_end event.
	// Shows phase, obligations, budget — the pipes are visible.

	pi.on("turn_end", async (_event, ctx) => {
		if (!state.arcPresent || !ctx.hasUI) return;

		// Update the persistent widget
		ctx.ui.setWidget("arc-harness", (_width, theme) => {
			const lines = renderRogers(state, _width, theme);
			return new Text(lines.join("\n"), 0, 0);
		});
	});

	// Also set widget on session start
	pi.on("session_start", async (_event, ctx) => {
		if (!state.arcPresent || !ctx.hasUI) return;

		ctx.ui.setWidget("arc-harness", (_width, theme) => {
			const lines = renderRogers(state, _width, theme);
			return new Text(lines.join("\n"), 0, 0);
		});
	});

	// ── LLM Tool: harness_status ──
	// Gives the LLM a way to query harness state programmatically.

	pi.registerTool({
		name: "harness_status",
		label: "Harness Status",
		description:
			"Query the arc harness state. Returns current phase, obligations, " +
			"token budget, active work, and gate status. Use this to understand " +
			"what the harness expects before proceeding.",
		parameters: {},

		async execute() {
			await loadArcState(state);
			const obligations = deriveObligations(state);
			const tokenPct = Math.min(100, Math.round((state.tokenEstimate / TOKEN_BUDGET) * 100));

			const status = {
				phase: state.phase,
				arc_present: state.arcPresent,
				current_action: state.currentAction,
				current_outcome: state.currentOutcome,
				tactical_active: state.tacticalActive,
				tactical_step: state.tacticalActive ? `${state.tacticalStep + 1}/${state.tacticalTotal}` : null,
				draw_down_done: state.drawDownDone,
				token_budget_pct: tokenPct,
				checkpoint_needed: state.checkpointNeeded,
				skills_loaded: Array.from(state.skillsLoaded),
				items_completed_this_session: state.itemsCompletedThisSession,
				obligations,
				open_outcomes: state.arcItems
					.filter((i) => i.type === "outcome" && i.status === "open")
					.map((i) => ({ id: i.id, title: i.title })),
				ready_actions: state.arcItems
					.filter((i) => i.type === "action" && i.status === "open" && !i.waiting_for)
					.map((i) => ({ id: i.id, title: i.title, parent: i.parent })),
			};

			return {
				content: [{ type: "text", text: JSON.stringify(status, null, 2) }],
				details: status,
			};
		},

		renderCall(_args, theme) {
			return new Text(theme.fg("toolTitle", theme.bold("harness_status")), 0, 0);
		},

		renderResult(result, _opts, theme) {
			const details = result.details as any;
			if (!details) {
				return new Text(theme.fg("dim", "No harness data"), 0, 0);
			}

			const phaseColor = details.checkpoint_needed ? "error" : "success";
			let text = theme.fg(phaseColor, `[${details.phase}]`);
			text += theme.fg("muted", ` ${details.token_budget_pct}% tokens`);

			if (details.current_action) {
				text += `\n${theme.fg("accent", details.current_action)}`;
				if (details.tactical_step) {
					text += theme.fg("muted", ` step ${details.tactical_step}`);
				}
			}

			if (details.obligations.length > 0) {
				text += `\n${theme.fg("warning", "Obligations:")}`;
				for (const ob of details.obligations) {
					text += `\n  ${theme.fg("dim", "- " + ob)}`;
				}
			}

			return new Text(text, 0, 0);
		},
	});
}
