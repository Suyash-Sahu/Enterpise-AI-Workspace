"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { AiKillSwitch } from "@/components/projects/AiKillSwitch";
import { WorkService } from "@/services/work.service";
import type { ProposalDTO, ProposalKind, ProposalStatus } from "@/types/project";

const MUTATING: ProposalKind[] = ["create_item", "update_item", "link_items"];
const EDITABLE: ProposalKind[] = ["create_item", "update_item"];

const FILTERS: { label: string; value: ProposalStatus | "ALL" }[] = [
    { label: "Pending", value: "PENDING" },
    { label: "Executed", value: "EXECUTED" },
    { label: "Rejected", value: "REJECTED" },
    { label: "All", value: "ALL" },
];

const KIND_LABELS: Record<ProposalKind, string> = {
    create_item: "New work item",
    update_item: "Change to a work item",
    link_items: "Link between items",
    duplicate_warning: "Possible duplicate",
    risk_alert: "Risk alert",
    sprint_plan: "Planning suggestion",
};

/** Untrusted text (emails, meetings, comments) only ever reaches the DOM as escaped React text. */
function PayloadView({ payload }: { payload: Record<string, unknown> }) {
    const entries = Object.entries(payload).filter(([k]) => k !== "proposal_id");
    return (
        <dl className="mt-3 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[8rem_1fr]">
            {entries.map(([k, v]) => (
                <div key={k} className="contents">
                    <dt className="text-xs text-muted-foreground">{k}</dt>
                    <dd className="break-words">
                        {typeof v === "string" ? v : JSON.stringify(v)}
                    </dd>
                </div>
            ))}
        </dl>
    );
}

function ProposalCard({
    proposal,
    onDecide,
}: {
    proposal: ProposalDTO;
    onDecide: (id: string, approve: boolean, edited?: Record<string, unknown>) => Promise<void>;
}) {
    const [editing, setEditing] = useState(false);
    const [title, setTitle] = useState(String(proposal.payload.title ?? ""));
    const [priority, setPriority] = useState(String(proposal.payload.priority ?? ""));
    const [busy, setBusy] = useState(false);

    const mutating = MUTATING.includes(proposal.kind);
    const pending = proposal.status === "PENDING";

    async function decide(approve: boolean) {
        setBusy(true);
        try {
            const edited: Record<string, unknown> = {};
            if (editing) {
                if (title && title !== proposal.payload.title) edited.title = title;
                if (priority && priority !== proposal.payload.priority) edited.priority = priority;
            }
            await onDecide(proposal.id, approve, Object.keys(edited).length ? edited : undefined);
        } finally {
            setBusy(false);
        }
    }

    return (
        <article className="rounded-xl border p-5">
            <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full bg-muted px-2.5 py-1 font-medium">{KIND_LABELS[proposal.kind]}</span>
                <span className="text-muted-foreground">by {proposal.agent} agent</span>
                {proposal.confidence != null && (
                    <span className="text-muted-foreground">
                        · confidence {Math.round(proposal.confidence * 100)}%
                    </span>
                )}
                {proposal.privacy_tier && (
                    <span className="text-muted-foreground">· {proposal.privacy_tier}</span>
                )}
                <span className="ml-auto rounded-full border px-2 py-0.5">{proposal.status}</span>
            </div>

            {proposal.explanation && <p className="mt-3 text-sm">{proposal.explanation}</p>}

            {editing ? (
                <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_10rem]">
                    <input
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        maxLength={255}
                        aria-label="Title"
                        className="rounded-md border bg-background px-3 py-2 text-sm"
                    />
                    <select
                        value={priority}
                        onChange={(e) => setPriority(e.target.value)}
                        aria-label="Priority"
                        className="rounded-md border bg-background px-3 py-2 text-sm"
                    >
                        <option value="">Priority</option>
                        {["low", "medium", "high", "urgent"].map((p) => (
                            <option key={p} value={p}>
                                {p}
                            </option>
                        ))}
                    </select>
                </div>
            ) : (
                <PayloadView payload={proposal.payload} />
            )}

            {proposal.error && <p className="mt-3 text-sm text-destructive">{proposal.error}</p>}
            {proposal.status === "EXECUTED" && typeof proposal.result?.task_id === "string" && (
                <p className="mt-3 text-sm">
                    <Link href={`/work/items/${proposal.result.task_id}`} className="font-medium hover:underline">
                        Open resulting item →
                    </Link>
                </p>
            )}

            {pending && (
                <div className="mt-4 flex flex-wrap gap-2">
                    <button
                        type="button"
                        disabled={busy}
                        onClick={() => decide(true)}
                        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    >
                        {mutating ? "Approve & apply" : "Acknowledge"}
                    </button>
                    {EDITABLE.includes(proposal.kind) && (
                        <button
                            type="button"
                            disabled={busy}
                            onClick={() => setEditing((v) => !v)}
                            className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent disabled:opacity-50"
                        >
                            {editing ? "Cancel edit" : "Edit"}
                        </button>
                    )}
                    <button
                        type="button"
                        disabled={busy}
                        onClick={() => decide(false)}
                        className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent disabled:opacity-50"
                    >
                        {mutating ? "Reject" : "Dismiss"}
                    </button>
                </div>
            )}
        </article>
    );
}

export default function InboxPage() {
    const [filter, setFilter] = useState<ProposalStatus | "ALL">("PENDING");
    const [items, setItems] = useState<ProposalDTO[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [tick, setTick] = useState(0);
    const load = useCallback(() => setTick((t) => t + 1), []);

    useEffect(() => {
        let cancelled = false;
        WorkService.getInbox(filter === "ALL" ? undefined : filter)
            .then((list) => {
                if (cancelled) return;
                setItems(list);
                setLoading(false);
            })
            .catch(() => {
                if (cancelled) return;
                setError("Unable to load the AI inbox.");
                setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [filter, tick]);

    async function onDecide(id: string, approve: boolean, edited?: Record<string, unknown>) {
        try {
            setError(null);
            await WorkService.decideProposal(id, approve, edited);
        } catch (err) {
            // e.g. 423 (kill switch), 403 (policy), 400 (already decided / expired)
            setError(err instanceof Error ? err.message : "Could not apply that decision.");
        }
        load();
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                    <h1 className="text-2xl font-semibold tracking-tight">AI Inbox</h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Everything the AI proposes lands here. Nothing changes your work until you approve it.
                    </p>
                </div>
                <AiKillSwitch />
            </div>

            <div className="flex flex-wrap gap-2">
                {FILTERS.map((f) => (
                    <button
                        key={f.value}
                        type="button"
                        onClick={() => {
                            setLoading(true);
                            setFilter(f.value);
                        }}
                        className={`rounded-full border px-3 py-1 text-sm ${
                            filter === f.value ? "bg-primary text-primary-foreground" : "hover:bg-accent"
                        }`}
                    >
                        {f.label}
                    </button>
                ))}
            </div>

            {error && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    {error}
                </div>
            )}

            {loading ? (
                <p className="text-sm text-muted-foreground">Loading…</p>
            ) : items.length === 0 ? (
                <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                    Nothing here. AI suggestions will appear when you use Smart Capture or the AI command bar.
                </p>
            ) : (
                <div className="space-y-4">
                    {items.map((p) => (
                        <ProposalCard key={p.id} proposal={p} onDecide={onDecide} />
                    ))}
                </div>
            )}
        </div>
    );
}
