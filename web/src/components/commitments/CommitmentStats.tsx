"use client";

import React from "react";
import { Card } from "@/components/ui/card";
import { CommitmentStatsDTO } from "@/types/commitment";
import {
    Clock,
    AlertTriangle,
    XCircle,
    CheckCircle2,
    TrendingUp,
    Sparkles,
    Users,
    Layers,
} from "lucide-react";

interface CommitmentStatsProps {
    stats?: CommitmentStatsDTO;
    activeFilter?: string;
    onSelectFilter?: (status: string) => void;
}

export function CommitmentStats({ stats, activeFilter, onSelectFilter }: CommitmentStatsProps) {
    if (!stats) return null;

    const cards = [
        {
            key: "all",
            label: "Total Tracked",
            value: stats.total,
            icon: Layers,
            color: "text-foreground",
            bg: "bg-muted/40",
            border: "border-border",
            activeBorder: "ring-2 ring-primary",
        },
        {
            key: "pending",
            label: "Pending",
            value: stats.pending,
            icon: Clock,
            color: "text-blue-600 dark:text-blue-400",
            bg: "bg-blue-50/50 dark:bg-blue-950/20",
            border: "border-blue-200/60 dark:border-blue-900/40",
            activeBorder: "ring-2 ring-blue-500",
        },
        {
            key: "at_risk",
            label: "At Risk",
            value: stats.at_risk,
            icon: AlertTriangle,
            color: "text-amber-600 dark:text-amber-400",
            bg: "bg-amber-50/50 dark:bg-amber-950/20",
            border: "border-amber-200/60 dark:border-amber-900/40",
            activeBorder: "ring-2 ring-amber-500",
        },
        {
            key: "overdue",
            label: "Overdue",
            value: stats.overdue,
            icon: XCircle,
            color: "text-rose-600 dark:text-rose-400",
            bg: "bg-rose-50/50 dark:bg-rose-950/20",
            border: "border-rose-200/60 dark:border-rose-900/40",
            activeBorder: "ring-2 ring-rose-500",
        },
    ];

    return (
        <div className="space-y-3">
            {/* 4 Primary Cards */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {cards.map((c) => {
                    const Icon = c.icon;
                    const isActive = activeFilter === c.key;
                    return (
                        <Card
                            key={c.key}
                            onClick={() => onSelectFilter?.(c.key)}
                            className={`p-4 transition-all duration-150 cursor-pointer hover:shadow-sm ${c.bg} ${c.border} ${
                                isActive ? c.activeBorder : ""
                            }`}
                        >
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-medium text-muted-foreground">{c.label}</span>
                                <Icon className={`h-4 w-4 ${c.color}`} />
                            </div>
                            <div className="mt-2 flex items-baseline gap-2">
                                <span className="text-2xl font-bold tracking-tight text-foreground">{c.value}</span>
                            </div>
                        </Card>
                    );
                })}
            </div>

            {/* 4 Secondary Quick Metrics */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 text-xs">
                <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-card p-2.5">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                    <div>
                        <span className="text-muted-foreground">Completed: </span>
                        <span className="font-semibold text-foreground">{stats.completed}</span>
                    </div>
                </div>

                <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-card p-2.5">
                    <TrendingUp className="h-4 w-4 text-primary shrink-0" />
                    <div>
                        <span className="text-muted-foreground">Completion Rate: </span>
                        <span className="font-semibold text-foreground">{stats.completion_rate}%</span>
                    </div>
                </div>

                <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-card p-2.5">
                    <Sparkles className="h-4 w-4 text-purple-500 shrink-0" />
                    <div>
                        <span className="text-muted-foreground">Discovered This Week: </span>
                        <span className="font-semibold text-foreground">{stats.newly_discovered_this_week}</span>
                    </div>
                </div>

                <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-card p-2.5">
                    <Users className="h-4 w-4 text-indigo-500 shrink-0" />
                    <div>
                        <span className="text-muted-foreground">Awaiting Others: </span>
                        <span className="font-semibold text-foreground">{stats.awaiting_others}</span>
                    </div>
                </div>
            </div>
        </div>
    );
}

