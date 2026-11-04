"use client";

import React from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { useCommitmentAnalytics } from "@/hooks/useCommitments";
import {
    BarChart3,
    TrendingUp,
    ShieldAlert,
    Clock,
    Users,
    CheckCircle2,
    Sparkles,
    AlertTriangle,
    Mail,
    Calendar,
} from "lucide-react";

interface CommitmentAnalyticsModalProps {
    open: boolean;
    onClose: () => void;
}

export function CommitmentAnalyticsModal({ open, onClose }: CommitmentAnalyticsModalProps) {
    const { data: analytics, isLoading } = useCommitmentAnalytics();

    return (
        <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
            <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                    <div className="flex items-center gap-2">
                        <BarChart3 className="h-5 w-5 text-primary" />
                        <DialogTitle className="text-base font-semibold">
                            Commitment Intelligence Analytics & Insights
                        </DialogTitle>
                    </div>
                    <DialogDescription className="text-xs text-muted-foreground">
                        Operational delivery trends, direction ratios, counterparty distribution, and risk insights.
                    </DialogDescription>
                </DialogHeader>

                {isLoading || !analytics ? (
                    <div className="py-12 text-center text-xs text-muted-foreground">
                        Loading commitment analytics...
                    </div>
                ) : (
                    <div className="space-y-5 text-xs">
                        {/* Actionable Insights */}
                        {analytics.actionable_insights?.length > 0 && (
                            <div className="space-y-2">
                                <h4 className="font-semibold text-foreground flex items-center gap-1.5">
                                    <Sparkles className="h-4 w-4 text-purple-500" />
                                    Actionable AI Insights
                                </h4>
                                <div className="grid gap-2 sm:grid-cols-2">
                                    {analytics.actionable_insights.map((ins, idx) => (
                                        <div
                                            key={idx}
                                            className="rounded-lg border border-border bg-card p-3 space-y-1"
                                        >
                                            <div className="flex items-center gap-1.5 font-medium text-foreground">
                                                {ins.type === "risk" && (
                                                    <AlertTriangle className="h-3.5 w-3.5 text-rose-500" />
                                                )}
                                                {ins.type === "follow_up" && (
                                                    <Clock className="h-3.5 w-3.5 text-amber-500" />
                                                )}
                                                {ins.type === "positive" && (
                                                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                                                )}
                                                <span>{ins.title}</span>
                                            </div>
                                            <p className="text-[11px] text-muted-foreground leading-relaxed">
                                                {ins.detail}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Distribution Metrics */}
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                            {/* Direction Breakdown */}
                            <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-2">
                                <span className="font-semibold text-foreground flex items-center gap-1.5">
                                    <Users className="h-3.5 w-3.5 text-indigo-500" />
                                    By Direction
                                </span>
                                <div className="space-y-1.5 text-[11px]">
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Owed by Me:</span>
                                        <span className="font-medium text-foreground">
                                            {analytics.direction_distribution?.owed_by_me ?? 0}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Owed to Me:</span>
                                        <span className="font-medium text-foreground">
                                            {analytics.direction_distribution?.owed_to_me ?? 0}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Mutual / Other:</span>
                                        <span className="font-medium text-foreground">
                                            {(analytics.direction_distribution?.mutual ?? 0) +
                                                (analytics.direction_distribution?.unknown ?? 0)}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Source Breakdown */}
                            <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-2">
                                <span className="font-semibold text-foreground flex items-center gap-1.5">
                                    <Mail className="h-3.5 w-3.5 text-blue-500" />
                                    By Source
                                </span>
                                <div className="space-y-1.5 text-[11px]">
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Gmail:</span>
                                        <span className="font-medium text-foreground">
                                            {analytics.source_distribution?.gmail ?? 0}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Meetings:</span>
                                        <span className="font-medium text-foreground">
                                            {analytics.source_distribution?.meeting ?? 0}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Manual:</span>
                                        <span className="font-medium text-foreground">
                                            {analytics.source_distribution?.manual ?? 0}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Priority Breakdown */}
                            <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-2">
                                <span className="font-semibold text-foreground flex items-center gap-1.5">
                                    <TrendingUp className="h-3.5 w-3.5 text-emerald-500" />
                                    By Priority
                                </span>
                                <div className="space-y-1.5 text-[11px]">
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">High / Urgent:</span>
                                        <span className="font-medium text-foreground text-rose-500">
                                            {analytics.priority_distribution?.high ?? 0}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Medium:</span>
                                        <span className="font-medium text-foreground">
                                            {analytics.priority_distribution?.medium ?? 0}
                                        </span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Low:</span>
                                        <span className="font-medium text-foreground">
                                            {analytics.priority_distribution?.low ?? 0}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Top Counterparties */}
                        {analytics.top_counterparties?.length > 0 && (
                            <div className="rounded-lg border border-border p-3 space-y-2">
                                <span className="font-semibold text-foreground flex items-center gap-1.5">
                                    <Users className="h-3.5 w-3.5 text-purple-500" />
                                    Top Active Counterparties
                                </span>
                                <div className="divide-y divide-border">
                                    {analytics.top_counterparties.map((cp, idx) => (
                                        <div key={idx} className="flex items-center justify-between py-1.5">
                                            <span className="text-foreground">{cp.name}</span>
                                            <Badge variant="outline" className="text-[10px]">
                                                {cp.count} commitment{cp.count === 1 ? "" : "s"}
                                            </Badge>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

