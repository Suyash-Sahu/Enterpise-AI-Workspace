"use client";

import React, { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CommitmentRunDTO } from "@/types/commitment";
import {
    Loader2,
    CheckCircle2,
    AlertTriangle,
    XCircle,
    StopCircle,
    ChevronDown,
    ChevronUp,
    Bot,
    ScanSearch,
    Clock,
} from "lucide-react";

interface CommitmentRunMonitorProps {
    run: CommitmentRunDTO | null;
    onCancel?: () => void;
    onDismiss?: () => void;
    isCancelling?: boolean;
}

export function CommitmentRunMonitor({
    run,
    onCancel,
    onDismiss,
    isCancelling = false,
}: CommitmentRunMonitorProps) {
    const [showStages, setShowStages] = useState(true);
    const [elapsedSeconds, setElapsedSeconds] = useState(0);

    const isRunning = run && (run.status === "running" || run.status === "queued");

    // Elapsed timer
    useEffect(() => {
        if (!run || !run.started_at) {
            setElapsedSeconds(0);
            return;
        }

        const start = new Date(run.started_at).getTime();
        const update = () => {
            const end = run.completed_at ? new Date(run.completed_at).getTime() : Date.now();
            setElapsedSeconds(Math.max(0, Math.floor((end - start) / 1000)));
        };

        update();
        if (isRunning) {
            const interval = setInterval(update, 1000);
            return () => clearInterval(interval);
        }
    }, [run?.started_at, run?.completed_at, isRunning]);

    if (!run) return null;

    const formatSeconds = (sec: number) => {
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        return `${m}:${s < 10 ? "0" : ""}${s}`;
    };

    const isSweep = run.run_type === "sweep";

    return (
        <Card className="overflow-hidden border-primary/40 bg-card shadow-sm">
            {/* Header / Primary status bar */}
            <div className="p-4 sm:p-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-3">
                        <div
                            className={`flex h-10 w-10 items-center justify-center rounded-xl ${
                                isSweep
                                    ? "bg-purple-100 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300"
                                    : "bg-primary/10 text-primary"
                            }`}
                        >
                            {isSweep ? (
                                <Bot className="h-5 w-5" />
                            ) : (
                                <ScanSearch className="h-5 w-5" />
                            )}
                        </div>
                        <div>
                            <div className="flex items-center gap-2">
                                <h3 className="text-sm font-semibold text-foreground">
                                    {isSweep ? "Autonomous AI Sweep" : "Commitment Discovery Scan"}
                                </h3>
                                <span className="rounded bg-muted px-2 py-0.5 text-[10px] font-mono text-muted-foreground">
                                    {run.id}
                                </span>
                            </div>
                            <p className="text-xs text-muted-foreground mt-0.5">
                                {run.current_stage
                                    ? `Stage: ${run.current_stage.replace(/_/g, " ")}`
                                    : run.status}
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <span className="flex items-center gap-1 text-xs text-muted-foreground mr-2 font-mono">
                            <Clock className="h-3.5 w-3.5" />
                            {formatSeconds(elapsedSeconds)}
                        </span>

                        {isRunning && onCancel && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={onCancel}
                                disabled={isCancelling}
                                className="h-8 border-rose-200 text-rose-600 hover:bg-rose-50 dark:border-rose-900 dark:text-rose-400"
                            >
                                <StopCircle className="h-3.5 w-3.5 mr-1" />
                                {isCancelling ? "Cancelling..." : "Cancel"}
                            </Button>
                        )}

                        {!isRunning && onDismiss && (
                            <Button variant="ghost" size="sm" onClick={onDismiss} className="h-8 text-xs">
                                Dismiss
                            </Button>
                        )}

                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowStages(!showStages)}
                            className="h-8 px-2 text-muted-foreground"
                        >
                            {showStages ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </Button>
                    </div>
                </div>

                {/* Real Progress Bar */}
                <div className="mt-4 space-y-1.5">
                    <div className="flex justify-between text-xs font-medium">
                        <span className="text-muted-foreground">
                            {isRunning ? (
                                <span className="inline-flex items-center gap-1.5 text-primary">
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    Execution in progress...
                                </span>
                            ) : run.status === "completed" ? (
                                <span className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                                    <CheckCircle2 className="h-3.5 w-3.5" />
                                    Execution complete
                                </span>
                            ) : run.status === "completed_with_warnings" ? (
                                <span className="inline-flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                                    <AlertTriangle className="h-3.5 w-3.5" />
                                    Completed with warnings
                                </span>
                            ) : run.status === "cancelled" ? (
                                <span className="inline-flex items-center gap-1.5 text-zinc-500">
                                    Cancelled by user
                                </span>
                            ) : (
                                <span className="inline-flex items-center gap-1.5 text-rose-600 dark:text-rose-400">
                                    <XCircle className="h-3.5 w-3.5" />
                                    Execution failed
                                </span>
                            )}
                        </span>
                        <span className="font-semibold text-foreground font-mono">{run.progress_percent}%</span>
                    </div>

                    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                        <div
                            className={`h-full transition-all duration-300 rounded-full ${
                                run.status === "failed"
                                    ? "bg-rose-500"
                                    : run.status === "completed_with_warnings"
                                    ? "bg-amber-500"
                                    : run.status === "cancelled"
                                    ? "bg-zinc-400"
                                    : "bg-primary"
                            }`}
                            style={{ width: `${Math.max(3, run.progress_percent)}%` }}
                        />
                    </div>
                </div>

                {/* Counter metrics bar */}
                <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4 rounded-lg bg-muted/30 p-2.5 text-xs">
                    <div>
                        <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Processed</span>
                        <span className="font-semibold text-foreground font-mono">
                            {run.processed_items} / {run.total_items}
                        </span>
                    </div>
                    <div>
                        <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Found</span>
                        <span className="font-semibold text-foreground font-mono">{run.commitments_found}</span>
                    </div>
                    <div>
                        <span className="text-muted-foreground block text-[10px] uppercase font-semibold">New Records</span>
                        <span className="font-semibold text-emerald-600 dark:text-emerald-400 font-mono">
                            +{run.created_count}
                        </span>
                    </div>
                    <div>
                        <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Updated</span>
                        <span className="font-semibold text-blue-600 dark:text-blue-400 font-mono">
                            {run.updated_count}
                        </span>
                    </div>
                </div>

                {/* Warnings / Errors banner */}
                {run.warnings && run.warnings.length > 0 && (
                    <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50/50 p-2.5 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300">
                        <div className="font-semibold flex items-center gap-1.5 mb-1">
                            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                            <span>Warnings ({run.warnings.length})</span>
                        </div>
                        <ul className="list-disc list-inside space-y-0.5 text-[11px] opacity-90">
                            {run.warnings.slice(0, 3).map((w, idx) => (
                                <li key={idx} className="truncate">{w}</li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>

            {/* Stages checklist accordion */}
            {showStages && run.stages && run.stages.length > 0 && (
                <div className="border-t border-border/60 bg-muted/15 p-4 sm:p-5">
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                        Execution Pipeline Stages
                    </h4>
                    <div className="space-y-2">
                        {run.stages.map((stg) => {
                            const isStgRunning = stg.status === "running";
                            const isStgDone = stg.status === "completed";
                            const isStgFailed = stg.status === "failed";

                            return (
                                <div
                                    key={stg.id}
                                    className={`flex items-center justify-between rounded-lg border p-2.5 text-xs transition-colors ${
                                        isStgRunning
                                            ? "border-primary/50 bg-primary/5 font-medium text-foreground"
                                            : isStgDone
                                            ? "border-border/40 bg-card text-muted-foreground"
                                            : isStgFailed
                                            ? "border-rose-300 bg-rose-50/30 text-rose-700 dark:border-rose-900/40 dark:text-rose-300"
                                            : "border-transparent bg-transparent text-muted-foreground/60"
                                    }`}
                                >
                                    <div className="flex items-center gap-2.5 min-w-0">
                                        {isStgRunning ? (
                                            <Loader2 className="h-4 w-4 animate-spin text-primary shrink-0" />
                                        ) : isStgDone ? (
                                            <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                                        ) : isStgFailed ? (
                                            <XCircle className="h-4 w-4 text-rose-500 shrink-0" />
                                        ) : (
                                            <div className="h-4 w-4 rounded-full border border-border/80 shrink-0" />
                                        )}
                                        <span className="truncate">{stg.stage_name.replace(/_/g, " ")}</span>
                                    </div>

                                    <div className="flex items-center gap-3 shrink-0">
                                        {stg.total_count > 0 && (
                                            <span className="text-[11px] font-mono text-muted-foreground">
                                                {stg.processed_count} / {stg.total_count}
                                            </span>
                                        )}
                                        <span
                                            className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${
                                                isStgRunning
                                                    ? "bg-primary text-primary-foreground"
                                                    : isStgDone
                                                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                                                    : isStgFailed
                                                    ? "bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300"
                                                    : "bg-muted text-muted-foreground"
                                            }`}
                                        >
                                            {stg.status}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </Card>
    );
}

