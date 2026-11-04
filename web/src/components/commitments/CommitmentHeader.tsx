"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { Bot, Plus, RefreshCw, ScanSearch, Loader2, BarChart3 } from "lucide-react";
import { CommitmentRunDTO } from "@/types/commitment";

interface CommitmentHeaderProps {
    onScan: () => void;
    onSweep: () => void;
    onCreateManual: () => void;
    onRefresh: () => void;
    onOpenAnalytics?: () => void;
    activeRun: CommitmentRunDTO | null;
    isStartingRun?: boolean;
}

export function CommitmentHeader({
    onScan,
    onSweep,
    onCreateManual,
    onRefresh,
    onOpenAnalytics,
    activeRun,
    isStartingRun = false,
}: CommitmentHeaderProps) {
    const isBusy = isStartingRun || (activeRun && (activeRun.status === "running" || activeRun.status === "queued"));

    return (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border pb-5">
            <div>
                <div className="flex items-center gap-3">
                    <h1 className="text-2xl font-bold tracking-tight text-foreground">
                        Commitment Intelligence
                    </h1>
                    {isBusy && (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary animate-pulse">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            {activeRun?.current_stage ? activeRun.current_stage.replace(/_/g, " ") : "Processing..."}{" "}
                            ({activeRun?.progress_percent ?? 0}%)
                        </span>
                    )}
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                    Discover, track, and verify promises and deliverables across Gmail, meetings, and WorkGraph.
                </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" size="sm" onClick={onRefresh} disabled={Boolean(isBusy)}>
                    <RefreshCw className="h-4 w-4 mr-1.5" aria-hidden />
                    Refresh
                </Button>

                {onOpenAnalytics && (
                    <Button variant="outline" size="sm" onClick={onOpenAnalytics}>
                        <BarChart3 className="h-4 w-4 mr-1.5 text-muted-foreground" aria-hidden />
                        Analytics
                    </Button>
                )}

                <Button
                    variant="outline"
                    size="sm"
                    onClick={onScan}
                    disabled={Boolean(isBusy)}
                    className="border-primary/30 hover:bg-primary/5"
                >
                    <ScanSearch className="h-4 w-4 mr-1.5 text-primary" aria-hidden />
                    Scan Sources
                </Button>

                <Button
                    variant="outline"
                    size="sm"
                    onClick={onSweep}
                    disabled={Boolean(isBusy)}
                    className="border-purple-300 dark:border-purple-800 hover:bg-purple-50 dark:hover:bg-purple-950/30"
                >
                    <Bot className="h-4 w-4 mr-1.5 text-purple-600 dark:text-purple-400" aria-hidden />
                    Run AI Sweep
                </Button>

                <Button size="sm" onClick={onCreateManual}>
                    <Plus className="h-4 w-4 mr-1.5" aria-hidden />
                    New Commitment
                </Button>
            </div>
        </div>
    );
}
