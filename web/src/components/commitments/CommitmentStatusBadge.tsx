"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import {
    CommitmentStatus,
    CommitmentDirection,
    CommitmentPriority,
    VerificationStatus,
} from "@/types/commitment";
import {
    ArrowUpRight,
    ArrowDownLeft,
    Handshake,
    HelpCircle,
    CheckCircle2,
    Clock,
    AlertTriangle,
    XCircle,
    ShieldCheck,
    ShieldAlert,
} from "lucide-react";

export function CommitmentStatusBadge({ status }: { status?: CommitmentStatus | string }) {
    const s = (status || "pending").toLowerCase();

    switch (s) {
        case "completed":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 border border-emerald-200/60 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/40">
                    <CheckCircle2 className="h-3 w-3" />
                    Completed
                </span>
            );
        case "at_risk":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700 border border-amber-200/60 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/40">
                    <AlertTriangle className="h-3 w-3" />
                    At Risk
                </span>
            );
        case "overdue":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-medium text-rose-700 border border-rose-200/60 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/40">
                    <XCircle className="h-3 w-3" />
                    Overdue
                </span>
            );
        case "dismissed":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-500 border border-zinc-200 dark:bg-zinc-800/60 dark:text-zinc-400 dark:border-zinc-700">
                    Dismissed
                </span>
            );
        default:
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700 border border-blue-200/60 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800/40">
                    <Clock className="h-3 w-3" />
                    Pending
                </span>
            );
    }
}

export function CommitmentDirectionBadge({ direction }: { direction?: CommitmentDirection | string }) {
    const d = (direction || "owed_by_me").toLowerCase();

    switch (d) {
        case "owed_by_me":
            return (
                <span className="inline-flex items-center gap-1 rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300">
                    <ArrowUpRight className="h-3 w-3" />
                    Owed by Me
                </span>
            );
        case "owed_to_me":
            return (
                <span className="inline-flex items-center gap-1 rounded-md bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-950/40 dark:text-purple-300">
                    <ArrowDownLeft className="h-3 w-3" />
                    Owed to Me
                </span>
            );
        case "mutual":
            return (
                <span className="inline-flex items-center gap-1 rounded-md bg-teal-50 px-2 py-0.5 text-xs font-medium text-teal-700 dark:bg-teal-950/40 dark:text-teal-300">
                    <Handshake className="h-3 w-3" />
                    Mutual
                </span>
            );
        default:
            return (
                <span className="inline-flex items-center gap-1 rounded-md bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                    <HelpCircle className="h-3 w-3" />
                    Unknown
                </span>
            );
    }
}

export function CommitmentPriorityBadge({ priority }: { priority?: CommitmentPriority | string }) {
    const p = (priority || "medium").toLowerCase();

    switch (p) {
        case "high":
            return (
                <span className="rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-rose-800 dark:bg-rose-950/60 dark:text-rose-300">
                    High
                </span>
            );
        case "low":
            return (
                <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                    Low
                </span>
            );
        default:
            return (
                <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
                    Med
                </span>
            );
    }
}

export function CommitmentVerificationBadge({ status }: { status?: VerificationStatus | string }) {
    const v = (status || "unverified").toLowerCase();

    switch (v) {
        case "verified":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                    <ShieldCheck className="h-3 w-3" />
                    Verified
                </span>
            );
        case "verification_pending":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
                    <Clock className="h-3 w-3" />
                    Verifying...
                </span>
            );
        case "rejected":
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-medium text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
                    <ShieldAlert className="h-3 w-3" />
                    Rejected
                </span>
            );
        default:
            return (
                <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                    Unverified
                </span>
            );
    }
}

