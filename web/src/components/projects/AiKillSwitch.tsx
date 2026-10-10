"use client";

import { useEffect, useState } from "react";
import { Power } from "lucide-react";

import { WorkService } from "@/services/work.service";

/**
 * "AI Work Automation [ON/OFF]" (PRD §6.4). Without projectId this is the
 * user-level switch (AMOF Work has no organizations, so that is the widest
 * scope); with projectId it is that project's switch. OFF blocks new AI
 * proposals/automation runs and cancels pending ones; existing work is untouched.
 */
export function AiKillSwitch({ projectId }: { projectId?: string }) {
    const [userOn, setUserOn] = useState(true);
    const [projectOn, setProjectOn] = useState(true);
    const [busy, setBusy] = useState(false);
    const [note, setNote] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        WorkService.getAiSettings()
            .then((s) => {
                if (cancelled) return;
                setUserOn(s.switches.user);
                setProjectOn(projectId ? (s.switches.projects[projectId] ?? true) : true);
            })
            .catch(() => {
                if (!cancelled) setError("Unable to load AI settings.");
            });
        return () => {
            cancelled = true;
        };
    }, [projectId]);

    const scopedOn = projectId ? projectOn : userOn;
    const effectiveOn = userOn && projectOn;

    async function toggle() {
        const next = !scopedOn;
        if (!next && !window.confirm("Turn OFF AI Work Automation? Pending AI proposals will be cancelled.")) {
            return;
        }
        try {
            setBusy(true);
            setError(null);
            const res = await WorkService.setKillSwitch(next, projectId);
            if (projectId) setProjectOn(next);
            else setUserOn(next);
            setNote(next ? "AI automation is ON." : `AI automation is OFF. ${res.cancelled} pending item(s) cancelled.`);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to change the switch.");
        } finally {
            setBusy(false);
        }
    }

    return (
        <div className="flex flex-wrap items-center gap-3">
            <button
                type="button"
                onClick={toggle}
                disabled={busy}
                aria-pressed={scopedOn}
                className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50 ${
                    effectiveOn ? "hover:bg-accent" : "border-destructive/40 bg-destructive/5 text-destructive"
                }`}
            >
                <Power className="h-4 w-4" />
                AI Work Automation: {scopedOn ? "ON" : "OFF"}
            </button>
            {projectId && !userOn && (
                <span className="text-xs text-destructive">Also OFF at the account level.</span>
            )}
            {note && <span className="text-xs text-muted-foreground">{note}</span>}
            {error && <span className="text-xs text-destructive">{error}</span>}
        </div>
    );
}
