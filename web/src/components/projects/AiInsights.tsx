"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Sparkles } from "lucide-react";

import { WorkService } from "@/services/work.service";
import type { CommandResultDTO, FocusPlanDTO, RiskReportDTO } from "@/types/project";

const SEVERITY_STYLE: Record<string, string> = {
    high: "bg-destructive/10 text-destructive",
    medium: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
    low: "bg-muted text-muted-foreground",
};

/** Ask-or-tell bar: reads answer immediately; anything that would change work becomes an inbox proposal. */
export function AiCommandBar() {
    const [command, setCommand] = useState("");
    const [busy, setBusy] = useState(false);
    const [result, setResult] = useState<CommandResultDTO | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function submit(e: React.FormEvent) {
        e.preventDefault();
        if (!command.trim()) return;
        try {
            setBusy(true);
            setError(null);
            setResult(await WorkService.runCommand(command.trim()));
        } catch (err) {
            setResult(null);
            setError(err instanceof Error ? err.message : "Command failed.");
        } finally {
            setBusy(false);
        }
    }

    const list = result?.data.items ?? result?.data.candidates ?? result?.data.blockers ?? [];

    return (
        <section className="rounded-xl border p-5">
            <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
                <div className="relative flex-1">
                    <Sparkles className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <input
                        value={command}
                        onChange={(e) => setCommand(e.target.value)}
                        maxLength={2000}
                        aria-label="AI command"
                        placeholder={'Try: "what\'s blocking Login?" or "create a bug: checkout fails, urgent"'}
                        className="w-full rounded-md border bg-background py-2 pl-9 pr-3 text-sm"
                    />
                </div>
                <button
                    type="submit"
                    disabled={busy || !command.trim()}
                    className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                    {busy ? "Working…" : "Ask AI"}
                </button>
            </form>

            {error && <p className="mt-3 text-sm text-destructive">{error}</p>}

            {result && (
                <div className="mt-4 space-y-2 text-sm">
                    <p>{result.answer}</p>
                    {list.length > 0 && (
                        <ul className="divide-y rounded-md border">
                            {list.map((t) => (
                                <li key={t.id}>
                                    <Link href={`/work/items/${t.id}`} className="flex justify-between gap-3 p-2.5 hover:bg-accent/40">
                                        <span className="truncate">{t.title}</span>
                                        <span className="shrink-0 text-xs text-muted-foreground">
                                            {String(t.status).replace("_", " ")} · {t.priority}
                                        </span>
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    )}
                    {result.mode === "proposal" && (
                        <Link href="/work/inbox" className="inline-block font-medium hover:underline">
                            Review in AI Inbox →
                        </Link>
                    )}
                </div>
            )}
        </section>
    );
}

/** Explained daily focus plan + risk & blocker radar. Read-only; nothing here changes work. */
export function AiInsights() {
    const [plan, setPlan] = useState<FocusPlanDTO | null>(null);
    const [risks, setRisks] = useState<RiskReportDTO | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [note, setNote] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        Promise.all([WorkService.getFocusPlan(), WorkService.getRisks()])
            .then(([p, r]) => {
                if (!cancelled) {
                    setPlan(p);
                    setRisks(r);
                }
            })
            .catch(() => {
                if (!cancelled) setError("Unable to load AI insights.");
            });
        return () => {
            cancelled = true;
        };
    }, []);

    async function publish() {
        try {
            const created = await WorkService.scanRisks();
            setNote(created.length ? `${created.length} alert(s) added to your AI Inbox.` : "No new alerts to add.");
        } catch (err) {
            setNote(err instanceof Error ? err.message : "Could not publish alerts.");
        }
    }

    if (error) return <p className="text-sm text-destructive">{error}</p>;

    return (
        <div className="grid gap-6 lg:grid-cols-2">
            <section className="space-y-3">
                <h2 className="text-lg font-semibold">Today&apos;s focus</h2>
                <p className="text-sm text-muted-foreground">{plan?.summary ?? "Loading…"}</p>
                <ol className="space-y-2">
                    {plan?.items.map((i) => (
                        <li key={i.task_id} className="rounded-lg border p-3">
                            <Link href={`/work/items/${i.task_id}`} className="font-medium hover:underline">
                                {i.title}
                            </Link>
                            <p className="mt-1 text-xs text-muted-foreground">{i.reasons.join(" · ")}</p>
                        </li>
                    ))}
                </ol>
                {plan && plan.waiting.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                        Waiting on something else: {plan.waiting.slice(0, 3).map((w) => w.title).join(", ")}
                        {plan.waiting.length > 3 ? ` +${plan.waiting.length - 3} more` : ""}
                    </p>
                )}
            </section>

            <section className="space-y-3">
                <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold">Risk &amp; blocker radar</h2>
                    {risks && risks.risks.length > 0 && (
                        <button type="button" onClick={publish} className="text-xs font-medium hover:underline">
                            Send to AI Inbox
                        </button>
                    )}
                </div>
                {note && <p className="text-xs text-muted-foreground">{note}</p>}
                {risks && risks.risks.length === 0 && (
                    <p className="text-sm text-muted-foreground">No risks found.</p>
                )}
                <ul className="space-y-2">
                    {risks?.risks.slice(0, 8).map((r) => (
                        <li key={`${r.type}-${r.task_id}`} className="rounded-lg border p-3">
                            <div className="flex items-center gap-2">
                                <span className={`rounded-full px-2 py-0.5 text-xs ${SEVERITY_STYLE[r.severity]}`}>
                                    {r.severity}
                                </span>
                                <Link href={`/work/items/${r.task_id}`} className="truncate font-medium hover:underline">
                                    {r.title}
                                </Link>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">{r.detail}</p>
                        </li>
                    ))}
                </ul>
            </section>
        </div>
    );
}
