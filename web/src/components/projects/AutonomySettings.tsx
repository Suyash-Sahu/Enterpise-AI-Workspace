"use client";

import { useEffect, useState } from "react";

import { WorkService } from "@/services/work.service";
import type { AutonomyLevel, MutatingKind } from "@/types/project";

const KINDS: { kind: MutatingKind; label: string }[] = [
    { kind: "create_item", label: "Create work items" },
    { kind: "update_item", label: "Change work items" },
    { kind: "link_items", label: "Link work items" },
];

const LEVELS: { level: AutonomyLevel; label: string; help: string }[] = [
    { level: "L0", label: "L0 · Observe", help: "AI may not propose this action here." },
    { level: "L1", label: "L1 · Suggest (default)", help: "AI proposes; nothing happens until you approve." },
    { level: "L2", label: "L2 · Execute with approval", help: "Treated like L1: approval is always required." },
    { level: "L3", label: "L3 · Auto-apply", help: "AI applies this action without asking. Only for this project and action." },
];

/**
 * Per-(project, action) autonomy. There is deliberately no global setting: L3 must be
 * granted one project and one action at a time, and destructive actions are not offered.
 */
export function AutonomySettings({ projectId }: { projectId: string }) {
    const [levels, setLevels] = useState<Record<string, AutonomyLevel>>({});
    const [busy, setBusy] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        WorkService.getAiSettings()
            .then((s) => {
                if (cancelled) return;
                const next: Record<string, AutonomyLevel> = {};
                for (const g of s.grants) if (g.project_id === projectId) next[g.action_kind] = g.level;
                setLevels(next);
            })
            .catch(() => {
                if (!cancelled) setError("Unable to load autonomy settings.");
            });
        return () => {
            cancelled = true;
        };
    }, [projectId]);

    async function change(kind: MutatingKind, level: AutonomyLevel) {
        if (
            level === "L3" &&
            !window.confirm(
                `Let AI ${KINDS.find((k) => k.kind === kind)?.label.toLowerCase()} in this project WITHOUT asking you first?`,
            )
        ) {
            return;
        }
        try {
            setBusy(kind);
            setError(null);
            await WorkService.setAutonomy(projectId, kind, level);
            setLevels((cur) => ({ ...cur, [kind]: level }));
        } catch (err) {
            setError(err instanceof Error ? err.message : "Could not change that setting.");
        } finally {
            setBusy(null);
        }
    }

    return (
        <section className="rounded-xl border p-5">
            <h2 className="font-semibold">AI autonomy</h2>
            <p className="mt-1 text-sm text-muted-foreground">
                Every AI action needs your approval by default. You can allow specific actions to apply automatically in
                this project only.
            </p>
            <div className="mt-4 space-y-3">
                {KINDS.map(({ kind, label }) => {
                    const current = levels[kind] ?? "L1";
                    return (
                        <div key={kind} className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                            <label htmlFor={`autonomy-${kind}`} className="text-sm font-medium">
                                {label}
                            </label>
                            <select
                                id={`autonomy-${kind}`}
                                value={current}
                                disabled={busy === kind}
                                onChange={(e) => change(kind, e.target.value as AutonomyLevel)}
                                className="rounded-md border bg-background px-3 py-1.5 text-sm"
                                title={LEVELS.find((l) => l.level === current)?.help}
                            >
                                {LEVELS.map((l) => (
                                    <option key={l.level} value={l.level}>
                                        {l.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                    );
                })}
            </div>
            {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        </section>
    );
}
