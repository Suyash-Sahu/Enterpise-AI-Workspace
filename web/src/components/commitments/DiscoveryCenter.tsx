"use client";

import React, { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Mail, Calendar, CheckCircle2, ChevronDown, ChevronUp, RefreshCw, AlertCircle } from "lucide-react";
import { CommitmentStatsDTO } from "@/types/commitment";

interface DiscoveryCenterProps {
    stats?: CommitmentStatsDTO;
    onTriggerScan: () => void;
    isScanning?: boolean;
}

export function DiscoveryCenter({ stats, onTriggerScan, isScanning }: DiscoveryCenterProps) {
    const [isExpanded, setIsExpanded] = useState(false);

    return (
        <Card className="border border-border/80 bg-card/60 p-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
                    <h3 className="text-sm font-semibold text-foreground">Discovery Connectors</h3>
                    <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        2 active sources
                    </span>
                </div>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="text-xs text-muted-foreground hover:text-foreground h-7"
                >
                    {isExpanded ? (
                        <>
                            <span>Hide details</span>
                            <ChevronUp className="h-3.5 w-3.5 ml-1" />
                        </>
                    ) : (
                        <>
                            <span>View source status</span>
                            <ChevronDown className="h-3.5 w-3.5 ml-1" />
                        </>
                    )}
                </Button>
            </div>

            {isExpanded && (
                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 pt-3 border-t border-border/50">
                    {/* Gmail Connector Card */}
                    <div className="rounded-lg border border-border/60 bg-background/50 p-3.5 flex flex-col justify-between">
                        <div>
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <div className="flex h-7 w-7 items-center justify-center rounded-md bg-rose-50 text-rose-600 dark:bg-rose-950/40 dark:text-rose-400">
                                        <Mail className="h-4 w-4" />
                                    </div>
                                    <div>
                                        <h4 className="text-xs font-semibold text-foreground">Gmail Intelligence</h4>
                                        <p className="text-[11px] text-muted-foreground">Inbox triage & promise detection</p>
                                    </div>
                                </div>
                                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                                    <CheckCircle2 className="h-3 w-3" />
                                    Connected
                                </span>
                            </div>

                            <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                                <div>
                                    <span className="block text-[10px] uppercase font-semibold text-muted-foreground/70">
                                        Source
                                    </span>
                                    <span className="text-foreground font-medium">Google Workspace</span>
                                </div>
                                <div>
                                    <span className="block text-[10px] uppercase font-semibold text-muted-foreground/70">
                                        Commitments
                                    </span>
                                    <span className="text-foreground font-medium">{stats?.total ?? 0} extracted</span>
                                </div>
                            </div>
                        </div>

                        <div className="mt-3 pt-2 border-t border-border/40 flex justify-end">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={onTriggerScan}
                                disabled={isScanning}
                                className="h-7 text-xs"
                            >
                                <RefreshCw className={`h-3 w-3 mr-1 ${isScanning ? "animate-spin" : ""}`} />
                                Scan Inbox
                            </Button>
                        </div>
                    </div>

                    {/* Meeting Connector Card */}
                    <div className="rounded-lg border border-border/60 bg-background/50 p-3.5 flex flex-col justify-between">
                        <div>
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
                                        <Calendar className="h-4 w-4" />
                                    </div>
                                    <div>
                                        <h4 className="text-xs font-semibold text-foreground">Meeting Intelligence</h4>
                                        <p className="text-[11px] text-muted-foreground">Action items & agreement extraction</p>
                                    </div>
                                </div>
                                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                                    <CheckCircle2 className="h-3 w-3" />
                                    Connected
                                </span>
                            </div>

                            <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                                <div>
                                    <span className="block text-[10px] uppercase font-semibold text-muted-foreground/70">
                                        Source
                                    </span>
                                    <span className="text-foreground font-medium">Meeting Transcripts</span>
                                </div>
                                <div>
                                    <span className="block text-[10px] uppercase font-semibold text-muted-foreground/70">
                                        Status
                                    </span>
                                    <span className="text-foreground font-medium">Synchronized</span>
                                </div>
                            </div>
                        </div>

                        <div className="mt-3 pt-2 border-t border-border/40 flex items-center justify-between text-[11px] text-muted-foreground">
                            <span>Auto-linked with WorkGraph</span>
                            <span className="font-medium text-foreground">Active</span>
                        </div>
                    </div>
                </div>
            )}
        </Card>
    );
}

