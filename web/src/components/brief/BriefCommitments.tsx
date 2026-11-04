"use client";

import React from "react";
import {
    ShieldAlert,
    CheckCircle2,
    Calendar,
    User,
    FileText,
    ExternalLink,
    AlertOctagon,
} from "lucide-react";
import { CommitmentDigestItem } from "@/types/automation";
import Link from "next/link";

interface BriefCommitmentsProps {
    commitments?: CommitmentDigestItem[];
    timezone?: string;
}

export function BriefCommitments({ commitments = [], timezone }: BriefCommitmentsProps) {
    const formatDate = (isoString?: string) => {
        if (!isoString) return "No due date specified";
        try {
            const date = new Date(isoString);
            return date.toLocaleDateString([], {
                month: "short",
                day: "numeric",
                year: "numeric",
                timeZone: timezone || undefined,
            });
        } catch {
            return isoString;
        }
    };

    if (commitments.length === 0) {
        return (
            <div className="rounded-2xl border border-zinc-200/80 bg-zinc-50/50 p-8 text-center dark:border-zinc-800 dark:bg-zinc-900/30">
                <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400">
                    <CheckCircle2 className="h-6 w-6" />
                </div>
                <h4 className="mt-2 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    No At-Risk Commitments
                </h4>
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                    All outbound promises and promised deliverables are on schedule with no overdue risk.
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {commitments.map((item, idx) => {
                const isOverdue =
                    item.status?.toLowerCase() === "overdue" ||
                    (item.risk_reason && item.risk_reason.toLowerCase().includes("overdue"));

                return (
                    <div
                        key={item.id || idx}
                        className="group rounded-xl border border-amber-200/80 bg-gradient-to-r from-amber-50/40 via-white to-amber-50/10 p-4 transition-all duration-200 hover:border-amber-300 dark:border-amber-950/50 dark:from-amber-950/15 dark:via-zinc-900/80 dark:to-amber-950/10 dark:hover:border-amber-800/60"
                    >
                        <div className="flex items-start justify-between gap-4">
                            <div className="min-w-0 flex-1 space-y-2">
                                <div className="flex flex-wrap items-center gap-2">
                                    <span
                                        className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold ${
                                            isOverdue
                                                ? "bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300"
                                                : "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
                                        }`}
                                    >
                                        <ShieldAlert className="h-3 w-3" />
                                        {isOverdue ? "Overdue Commitment" : "At Risk"}
                                    </span>

                                    {item.priority && (
                                        <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 uppercase dark:bg-zinc-800 dark:text-zinc-400">
                                            {item.priority}
                                        </span>
                                    )}
                                </div>

                                <h5 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                                    {item.description}
                                </h5>

                                {item.risk_reason && (
                                    <div className="rounded-lg bg-amber-50/80 px-2.5 py-1.5 text-xs text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
                                        <span className="font-semibold">Risk Factor: </span>
                                        {item.risk_reason}
                                    </div>
                                )}

                                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500 dark:text-zinc-400">
                                    {item.due_date && (
                                        <span className="inline-flex items-center gap-1">
                                            <Calendar className="h-3.5 w-3.5 text-zinc-400" />
                                            <span>Promised date: {formatDate(item.due_date)}</span>
                                        </span>
                                    )}

                                    {item.responsible_party && (
                                        <span className="inline-flex items-center gap-1">
                                            <User className="h-3.5 w-3.5 text-zinc-400" />
                                            <span>Party: {item.responsible_party}</span>
                                        </span>
                                    )}

                                    {item.source_ref && (
                                        <span className="inline-flex items-center gap-1">
                                            <FileText className="h-3.5 w-3.5 text-zinc-400" />
                                            <span className="max-w-[200px] truncate">
                                                Ref: {item.source_ref}
                                            </span>
                                        </span>
                                    )}
                                </div>
                            </div>

                            <div className="shrink-0 self-center">
                                <Link
                                    href="/commitments"
                                    className="inline-flex items-center gap-1 rounded-lg border border-amber-300/80 bg-amber-50/60 px-3 py-1.5 text-xs font-semibold text-amber-800 transition hover:bg-amber-100 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-300 dark:hover:bg-amber-900/60"
                                >
                                    <span>Review</span>
                                    <ExternalLink className="h-3 w-3 opacity-70" />
                                </Link>
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
