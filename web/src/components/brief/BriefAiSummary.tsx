"use client";

import { useState } from "react";
import { Sparkles, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, Target, ShieldCheck } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DigestPayload } from "@/types/automation";

interface BriefAiSummaryProps {
    digest?: DigestPayload;
}

export default function BriefAiSummary({ digest }: BriefAiSummaryProps) {
    const [isExpanded, setIsExpanded] = useState(true);

    const aiSummary = digest?.ai_summary;
    const summaryText = typeof digest?.summary === "string" 
        ? (aiSummary?.text || digest.summary) 
        : (aiSummary?.text || digest?.summary?.text || "Your daily briefing has been compiled from your connected workspace tools.");

    const priorities = aiSummary?.priorities || (typeof digest?.summary === "object" ? digest?.summary?.priorities : []) || [];
    const warnings = aiSummary?.warnings || (typeof digest?.summary === "object" ? digest?.summary?.warnings : []) || [];
    const focus = aiSummary?.focus;

    // Calendar conflicts also treated as immediate warnings
    const conflicts = digest?.calendar?.conflicts || digest?.today_events?.conflicts || [];
    const allWarnings = [
        ...warnings,
        ...conflicts.map((c) => `Calendar conflict: "${c.event_a}" overlaps with "${c.event_b}".`),
    ];

    return (
        <Card className="relative overflow-hidden border-primary/20 bg-gradient-to-br from-card via-card to-primary/5 p-5 shadow-sm">
            {/* Header / Badges */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-3">
                <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
                        <Sparkles className="h-4 w-4" />
                    </div>
                    <span className="text-sm font-bold text-foreground">AI Daily Briefing & Priorities</span>
                    <Badge variant="outline" className="gap-1 border-primary/30 bg-primary/5 text-[10px] text-primary">
                        <ShieldCheck className="h-3 w-3" /> Grounded in Records
                    </Badge>
                </div>

                <div className="flex items-center gap-2">
                    {focus && (
                        <div className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex">
                            <Target className="h-3.5 w-3.5 text-primary" />
                            <span className="font-medium text-foreground">Today's Focus:</span>
                            <span className="truncate max-w-[240px] text-primary font-semibold">{focus}</span>
                        </div>
                    )}
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs text-muted-foreground"
                        onClick={() => setIsExpanded(!isExpanded)}
                    >
                        {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                        <span className="ml-1">{isExpanded ? "Collapse" : "Expand"}</span>
                    </Button>
                </div>
            </div>

            {/* Summary Text Body */}
            <div className="mt-3">
                <p className="text-sm leading-relaxed text-foreground/90 whitespace-pre-line font-medium">
                    {summaryText}
                </p>
            </div>

            {/* Expanded details: Top Priorities & Warnings */}
            {isExpanded && (
                <div className="mt-4 space-y-3 pt-3 border-t border-border/40">
                    {allWarnings.length > 0 && (
                        <div className="space-y-1.5 rounded-lg border border-destructive/20 bg-destructive/5 p-3">
                            <div className="flex items-center gap-1.5 text-xs font-semibold text-destructive">
                                <AlertTriangle className="h-3.5 w-3.5" />
                                <span>Critical Alerts & Warnings</span>
                            </div>
                            <ul className="space-y-1 pl-5 text-xs text-destructive/90 list-disc">
                                {allWarnings.map((w, idx) => (
                                    <li key={idx}>{w}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {priorities.length > 0 && (
                        <div className="space-y-2">
                            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                Recommended Focus Areas
                            </span>
                            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                {priorities.map((p, idx) => (
                                    <div
                                        key={idx}
                                        className="flex items-start gap-2 rounded-md border border-border/60 bg-background/50 p-2.5 text-xs text-foreground"
                                    >
                                        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                                        <span className="font-medium">{p}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </Card>
    );
}
