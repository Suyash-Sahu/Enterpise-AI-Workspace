"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AiKillSwitch } from "@/components/projects/AiKillSwitch";
import { WorkService } from "@/services/work.service";
import type {
    AutomationDTO,
    AutomationPreviewDTO,
    AutomationRunDTO,
} from "@/types/project";

const EXAMPLE = "whenever a high-priority task becomes overdue, notify me and create a follow-up";

function describeRule(a: AutomationDTO): string {
    const t = a.trigger;
    const when =
        t.type === "overdue"
            ? "becomes overdue"
            : t.type === "item_created"
              ? "is created"
              : t.type === "status_changed"
                ? `status changes to ${t.to}`
                : `priority changes to ${t.to}`;
    const c = a.conditions;
    const filters = [
        c.priority?.length ? `${c.priority.join("/")} priority` : "",
        c.type?.length ? c.type.join("/").toLowerCase() : "",
        c.unassigned ? "unassigned" : "",
    ].filter(Boolean);
    const acts = a.actions.map((x) => (x.value ? `${x.type.replace("_", " ")}: ${x.value}` : x.type.replace("_", " ")));
    return `When ${filters.length ? filters.join(", ") + " " : ""}item ${when} → ${acts.join(", ")}`;
}

function PreviewView({ preview }: { preview: AutomationPreviewDTO }) {
    return (
        <div className="mt-3 space-y-2 rounded-lg border bg-muted/30 p-4 text-sm">
            <p className="font-medium">
                {preview.total_matched} item(s) match right now (limit per run: {preview.max_items_per_run}).
            </p>
            {preview.warnings.map((w) => (
                <p key={w} className={preview.would_exceed_limit && w.includes("BLOCKED") ? "text-destructive" : "text-muted-foreground"}>
                    {w}
                </p>
            ))}
            {!preview.kill_switch_on && (
                <p className="text-destructive">AI Work Automation is OFF, so nothing would run until you turn it back on.</p>
            )}
            <ul className="space-y-2">
                {preview.sample.slice(0, 5).map((s) => (
                    <li key={s.task_id} className="rounded-md border bg-background p-3">
                        <Link href={`/work/items/${s.task_id}`} className="font-medium hover:underline">
                            {s.title}
                        </Link>
                        <ul className="mt-1 text-xs text-muted-foreground">
                            {s.drafts.map((d, i) => (
                                <li key={i}>
                                    {d.explanation} · {d.autonomy_level === "n/a" ? "informational" : d.autonomy_level}
                                    {d.would_auto_execute ? " · applies automatically" : ""}
                                </li>
                            ))}
                            {s.drafts.length === 0 && <li>No change needed for this item.</li>}
                        </ul>
                    </li>
                ))}
            </ul>
        </div>
    );
}

function RuleCard({ rule, onChanged }: { rule: AutomationDTO; onChanged: () => void }) {
    const [preview, setPreview] = useState<AutomationPreviewDTO | null>(null);
    const [runs, setRuns] = useState<AutomationRunDTO[] | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [note, setNote] = useState<string | null>(null);

    async function guarded(fn: () => Promise<void>) {
        try {
            setBusy(true);
            setError(null);
            await fn();
        } catch (err) {
            setError(err instanceof Error ? err.message : "That didn't work.");
        } finally {
            setBusy(false);
        }
    }

    const doPreview = () => guarded(async () => {
        setPreview(await WorkService.previewAutomation(rule.id));
        onChanged();
    });
    const doAction = (a: "activate" | "pause" | "resume") => guarded(async () => {
        await WorkService.automationAction(rule.id, a);
        onChanged();
    });
    const doRun = () => guarded(async () => {
        const r = await WorkService.runAutomation(rule.id);
        setNote(r ? `Run ${r.status}: ${r.matched_count} matched, ${r.proposals_created} proposal(s).` : "Nothing new matched.");
        setRuns((await WorkService.getAutomation(rule.id)).runs);
    });
    const showRuns = () => guarded(async () => setRuns((await WorkService.getAutomation(rule.id)).runs));

    const pill =
        rule.status === "active"
            ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
            : rule.status === "paused"
              ? "bg-amber-500/10 text-amber-700 dark:text-amber-400"
              : "bg-muted text-muted-foreground";

    return (
        <article className="rounded-xl border p-5">
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <p className="font-medium">{describeRule(rule)}</p>
                    {rule.source_text && (
                        <p className="mt-1 truncate text-xs text-muted-foreground">&ldquo;{rule.source_text}&rdquo;</p>
                    )}
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs ${pill}`}>{rule.status}</span>
            </div>

            <div className="mt-4 flex flex-wrap gap-2 text-sm">
                <button type="button" disabled={busy} onClick={doPreview} className="rounded-md border px-3 py-1.5 hover:bg-accent disabled:opacity-50">
                    Preview (dry run)
                </button>
                {rule.status === "draft" && (
                    <button
                        type="button"
                        disabled={busy || !rule.previewed}
                        onClick={() => doAction("activate")}
                        title={rule.previewed ? "" : "Preview first"}
                        className="rounded-md bg-primary px-3 py-1.5 text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    >
                        Activate
                    </button>
                )}
                {rule.status === "active" && (
                    <>
                        <button type="button" disabled={busy} onClick={() => doAction("pause")} className="rounded-md border px-3 py-1.5 hover:bg-accent disabled:opacity-50">
                            Pause
                        </button>
                        <button type="button" disabled={busy} onClick={doRun} className="rounded-md border px-3 py-1.5 hover:bg-accent disabled:opacity-50">
                            Run now
                        </button>
                    </>
                )}
                {rule.status === "paused" && (
                    <button type="button" disabled={busy} onClick={() => doAction("resume")} className="rounded-md bg-primary px-3 py-1.5 text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                        Resume
                    </button>
                )}
                <button type="button" disabled={busy} onClick={showRuns} className="rounded-md px-3 py-1.5 text-muted-foreground hover:underline">
                    History
                </button>
            </div>

            {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
            {note && <p className="mt-3 text-sm text-muted-foreground">{note}</p>}
            {preview && <PreviewView preview={preview} />}
            {runs && (
                <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
                    {runs.length === 0 && <li>No runs yet.</li>}
                    {runs.map((r) => (
                        <li key={r.id}>
                            {r.started_at ? new Date(r.started_at).toLocaleString() : ""} · {r.status.replace(/_/g, " ")} ·{" "}
                            {r.matched_count} matched · {r.proposals_created} proposed · {r.executed_count} applied
                        </li>
                    ))}
                </ul>
            )}
        </article>
    );
}

export default function AutomationsPage() {
    const [rules, setRules] = useState<AutomationDTO[]>([]);
    const [text, setText] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [clarify, setClarify] = useState<string | null>(null);

    const [tick, setTick] = useState(0);
    const load = useCallback(() => setTick((t) => t + 1), []);

    useEffect(() => {
        let cancelled = false;
        WorkService.getAutomations()
            .then((list) => {
                if (!cancelled) setRules(list);
            })
            .catch(() => {
                if (!cancelled) setError("Unable to load automations.");
            });
        return () => {
            cancelled = true;
        };
    }, [tick]);

    async function build(e: React.FormEvent) {
        e.preventDefault();
        if (!text.trim()) return;
        try {
            setBusy(true);
            setError(null);
            setClarify(null);
            const res = await WorkService.buildAutomation(text.trim());
            if (res.needs_clarification) {
                setClarify(res.clarification ?? "I couldn't understand that rule.");
            } else {
                setText("");
                load();
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Could not build that rule.");
        } finally {
            setBusy(false);
        }
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                    <h1 className="text-2xl font-semibold tracking-tight">Automations</h1>
                    <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                        Describe a rule in plain language. Every rule starts as a draft, must be previewed before it can be
                        activated, and its actions land in your AI Inbox for approval unless you granted auto-apply.
                    </p>
                </div>
                <AiKillSwitch />
            </div>

            <form onSubmit={build} className="space-y-2 rounded-xl border p-5">
                <label htmlFor="rule-text" className="text-sm font-medium">
                    New rule
                </label>
                <div className="flex flex-col gap-3 sm:flex-row">
                    <input
                        id="rule-text"
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        maxLength={1000}
                        placeholder={EXAMPLE}
                        className="flex-1 rounded-md border bg-background px-3 py-2 text-sm"
                    />
                    <button
                        type="submit"
                        disabled={busy || !text.trim()}
                        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    >
                        {busy ? "Building…" : "Build rule"}
                    </button>
                </div>
                {clarify && <p className="text-sm text-amber-700 dark:text-amber-400">{clarify}</p>}
                {error && <p className="text-sm text-destructive">{error}</p>}
            </form>

            {rules.length === 0 ? (
                <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                    No automations yet. Try: &ldquo;{EXAMPLE}&rdquo;
                </p>
            ) : (
                <div className="space-y-4">
                    {rules.map((r) => (
                        <RuleCard key={r.id} rule={r} onChanged={load} />
                    ))}
                </div>
            )}
        </div>
    );
}
