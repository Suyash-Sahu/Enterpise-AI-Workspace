"use client";

import React from "react";
import {
    Sparkles,
    Mail,
    Reply,
    CheckSquare,
    Calendar,
    ShieldAlert,
    ArrowRight,
    ArrowUpRight,
} from "lucide-react";
import { SuggestedActionItem } from "@/types/automation";
import Link from "next/link";

interface BriefSuggestedActionsProps {
    actions?: (string | SuggestedActionItem)[];
}

export function BriefSuggestedActions({ actions = [] }: BriefSuggestedActionsProps) {
    if (actions.length === 0) {
        return null;
    }

    const normalizeAction = (action: string | SuggestedActionItem): SuggestedActionItem => {
        if (typeof action === "string") {
            let actionType = "general";
            const lower = action.toLowerCase();
            if (lower.includes("email") || lower.includes("reply")) actionType = "reply_email";
            else if (lower.includes("task") || lower.includes("overdue")) actionType = "open_task";
            else if (lower.includes("meeting") || lower.includes("schedule")) actionType = "prepare_meeting";
            else if (lower.includes("commitment")) actionType = "review_commitment";

            return {
                id: `act-${Math.random().toString(36).substring(7)}`,
                title: action,
                description: action,
                priority: lower.includes("overdue") || lower.includes("urgent") ? "urgent" : "high",
                action_type: actionType,
                reason: "Derived from morning briefing analysis",
            };
        }
        return action;
    };

    const getActionIcon = (actionType?: string) => {
        switch (actionType) {
            case "reply_email":
                return <Reply className="h-4 w-4 text-sky-600 dark:text-sky-400" />;
            case "open_email":
                return <Mail className="h-4 w-4 text-sky-600 dark:text-sky-400" />;
            case "open_task":
            case "complete_task":
                return <CheckSquare className="h-4 w-4 text-amber-600 dark:text-amber-400" />;
            case "prepare_meeting":
                return <Calendar className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />;
            case "review_commitment":
                return <ShieldAlert className="h-4 w-4 text-rose-600 dark:text-rose-400" />;
            default:
                return <Sparkles className="h-4 w-4 text-violet-600 dark:text-violet-400" />;
        }
    };

    const getPriorityBadge = (priority?: string) => {
        const p = (priority || "medium").toLowerCase();
        if (p === "urgent" || p === "critical") {
            return (
                <span className="rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-bold text-rose-700 dark:bg-rose-950/60 dark:text-rose-300">
                    Urgent
                </span>
            );
        }
        if (p === "high") {
            return (
                <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
                    High
                </span>
            );
        }
        return (
            <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                Recommended
            </span>
        );
    };

    const getActionDestination = (item: SuggestedActionItem) => {
        const type = item.action_type || "";
        if (type.includes("email")) {
            if (item.source_reference && item.source_reference.startsWith("https://")) {
                return { href: item.source_reference, external: true, label: "Open in Gmail" };
            }
            return { href: "/inbox", external: false, label: "View in Inbox" };
        }
        if (type.includes("task")) {
            return { href: "/work", external: false, label: "Go to Tasks" };
        }
        if (type.includes("meeting")) {
            return { href: "#agenda-section", external: false, label: "View Agenda" };
        }
        if (type.includes("commitment")) {
            return { href: "/work/commitments", external: false, label: "Review Commitments" };
        }
        return { href: "/work", external: false, label: "Take Action" };
    };

    return (
        <div className="space-y-3">
            <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-violet-500" />
                <h4 className="text-sm font-semibold uppercase tracking-wider text-zinc-600 dark:text-zinc-400">
                    Recommended Actions
                </h4>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {actions.map((rawAction, idx) => {
                    const action = normalizeAction(rawAction);
                    const dest = getActionDestination(action);

                    return (
                        <div
                            key={action.id || idx}
                            className="group flex flex-col justify-between rounded-xl border border-zinc-200/80 bg-white p-4 shadow-xs transition-all duration-200 hover:border-zinc-300 hover:shadow-sm dark:border-zinc-800/80 dark:bg-zinc-900/60 dark:hover:border-zinc-700"
                        >
                            <div className="space-y-2">
                                <div className="flex items-center justify-between gap-2">
                                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-100 dark:bg-zinc-800">
                                        {getActionIcon(action.action_type)}
                                    </div>
                                    {getPriorityBadge(action.priority)}
                                </div>

                                <div>
                                    <h5 className="text-sm font-semibold text-zinc-900 group-hover:text-violet-600 dark:text-zinc-100 dark:group-hover:text-violet-400">
                                        {action.title}
                                    </h5>
                                    {action.reason && (
                                        <p className="mt-1 line-clamp-2 text-xs text-zinc-500 dark:text-zinc-400">
                                            {action.reason}
                                        </p>
                                    )}
                                </div>
                            </div>

                            <div className="mt-4 pt-3 border-t border-zinc-100 dark:border-zinc-800/70">
                                {dest.external ? (
                                    <a
                                        href={dest.href}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex w-full items-center justify-between rounded-lg bg-zinc-50 px-3 py-1.5 text-xs font-semibold text-zinc-700 transition hover:bg-zinc-100 hover:text-zinc-900 dark:bg-zinc-800/60 dark:text-zinc-300 dark:hover:bg-zinc-800"
                                    >
                                        <span>{dest.label}</span>
                                        <ArrowUpRight className="h-3.5 w-3.5" />
                                    </a>
                                ) : (
                                    <Link
                                        href={dest.href}
                                        className="inline-flex w-full items-center justify-between rounded-lg bg-zinc-50 px-3 py-1.5 text-xs font-semibold text-zinc-700 transition hover:bg-zinc-100 hover:text-zinc-900 dark:bg-zinc-800/60 dark:text-zinc-300 dark:hover:bg-zinc-800"
                                    >
                                        <span>{dest.label}</span>
                                        <ArrowRight className="h-3.5 w-3.5" />
                                    </Link>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
