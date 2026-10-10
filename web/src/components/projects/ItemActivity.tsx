"use client";

import { useEffect, useState } from "react";

import { WorkService } from "@/services/work.service";
import type { ActivityDTO, TaskLinksDTO } from "@/types/project";

const LABELS: Record<string, string> = {
    created: "created this item",
    updated: "updated this item",
    status_changed: "changed the status",
    dependency_added: "added a link",
    dependency_removed: "removed a link",
};

type Changes = Record<string, { from: string | null; to: string }>;

function describe(e: ActivityDTO): string {
    const changes = (e.payload as { changes?: Changes } | null)?.changes;
    if (changes) {
        return Object.entries(changes)
            .map(([k, v]) => `${k}: ${v.from ?? "—"} → ${v.to}`)
            .join(", ");
    }
    const p = e.payload as { kind?: string; other?: string } | null;
    return p?.kind && p.other ? `${p.kind} ${p.other}` : "";
}

/** Read-only view of the immutable activity trail and directional links. */
export function ItemActivity({ taskId, refreshKey }: { taskId: string; refreshKey?: string }) {
    const [events, setEvents] = useState<ActivityDTO[]>([]);
    const [links, setLinks] = useState<TaskLinksDTO | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        let cancelled = false;
        Promise.all([WorkService.getActivity(taskId), WorkService.getLinks(taskId)])
            .then(([a, l]) => {
                if (!cancelled) {
                    setEvents(a);
                    setLinks(l);
                    setError(false);
                }
            })
            .catch(() => {
                if (!cancelled) setError(true);
            });
        return () => {
            cancelled = true;
        };
    }, [taskId, refreshKey]);

    return (
        <section className="rounded-xl border p-5">
            <h2 className="font-semibold">Activity</h2>

            {links && (links.blocks.length > 0 || links.relates_to.length > 0) && (
                <p className="mt-2 text-xs text-muted-foreground">
                    Blocks {links.blocks.length} · Related {links.relates_to.length} · Blocked by{" "}
                    {links.blocked_by.length}
                </p>
            )}

            {error ? (
                <p className="mt-3 text-sm text-destructive">Unable to load activity.</p>
            ) : events.length === 0 ? (
                <p className="mt-3 text-sm text-muted-foreground">No activity yet.</p>
            ) : (
                <ul className="mt-3 space-y-2 text-sm">
                    {events.map((e) => (
                        <li key={e.id} className="flex flex-wrap items-baseline gap-x-2">
                            <span className="font-medium">{e.actor}</span>
                            <span>{LABELS[e.event_type] ?? e.event_type}</span>
                            <span className="text-xs text-muted-foreground">{describe(e)}</span>
                            <span className="ml-auto text-xs text-muted-foreground">
                                {new Date(e.created_at).toLocaleString()}
                            </span>
                        </li>
                    ))}
                </ul>
            )}
        </section>
    );
}
