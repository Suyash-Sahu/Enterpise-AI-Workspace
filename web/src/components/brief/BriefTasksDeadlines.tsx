"use client";

import React, { useState } from "react";
import {
    CheckCircle2,
    Clock,
    AlertCircle,
    Calendar,
    FolderKanban,
    ChevronRight,
    ArrowUpRight,
    ShieldAlert,
} from "lucide-react";
import { TaskDigestItem } from "@/types/automation";
import Link from "next/link";

interface BriefTasksDeadlinesProps {
    overdue?: TaskDigestItem[];
    dueToday?: TaskDigestItem[];
    upcoming?: TaskDigestItem[];
    within3Days?: TaskDigestItem[];
    within7Days?: TaskDigestItem[];
    timezone?: string;
}

type TabType = "overdue" | "today" | "3days" | "7days" | "all";

export function BriefTasksDeadlines({
    overdue = [],
    dueToday = [],
    upcoming = [],
    within3Days = [],
    within7Days = [],
    timezone,
}: BriefTasksDeadlinesProps) {
    const [activeTab, setActiveTab] = useState<TabType>(
        overdue.length > 0 ? "overdue" : dueToday.length > 0 ? "today" : "3days"
    );

    // Compute subsets if not already separated
    const derivedWithin3Days =
        within3Days.length > 0
            ? within3Days
            : upcoming.filter((t) => (t.overdue_days !== undefined ? t.overdue_days <= 3 : true));
    const derivedWithin7Days =
        within7Days.length > 0
            ? within7Days
            : upcoming.filter((t) => (t.overdue_days !== undefined ? t.overdue_days <= 7 : true));

    const formatDate = (isoString?: string) => {
        if (!isoString) return "No due date";
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

    const getPriorityBadge = (priority?: string) => {
        const p = (priority || "medium").toLowerCase();
        if (p === "urgent" || p === "critical") {
            return (
                <span className="inline-flex items-center rounded-md bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700 dark:bg-rose-950/60 dark:text-rose-300">
                    Urgent
                </span>
            );
        }
        if (p === "high") {
            return (
                <span className="inline-flex items-center rounded-md bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700 dark:bg-amber-950/60 dark:text-amber-300">
                    High
                </span>
            );
        }
        if (p === "medium") {
            return (
                <span className="inline-flex items-center rounded-md bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-950/60 dark:text-blue-300">
                    Medium
                </span>
            );
        }
        return (
            <span className="inline-flex items-center rounded-md bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                Low
            </span>
        );
    };

    const getCurrentItems = (): { items: TaskDigestItem[]; emptyMessage: string; isOverdue: boolean } => {
        switch (activeTab) {
            case "overdue":
                return {
                    items: overdue,
                    emptyMessage: "No overdue tasks! You're completely up to date.",
                    isOverdue: true,
                };
            case "today":
                return {
                    items: dueToday,
                    emptyMessage: "No tasks due today.",
                    isOverdue: false,
                };
            case "3days":
                return {
                    items: derivedWithin3Days,
                    emptyMessage: "No tasks due within the next 3 days.",
                    isOverdue: false,
                };
            case "7days":
                return {
                    items: derivedWithin7Days,
                    emptyMessage: "No tasks due within the next 7 days.",
                    isOverdue: false,
                };
            case "all":
            default:
                return {
                    items: [...overdue, ...dueToday, ...upcoming],
                    emptyMessage: "No pending tasks recorded.",
                    isOverdue: false,
                };
        }
    };

    const { items, emptyMessage, isOverdue } = getCurrentItems();

    const tabs: { id: TabType; label: string; count: number; alert?: boolean }[] = [
        { id: "overdue", label: "Overdue", count: overdue.length, alert: overdue.length > 0 },
        { id: "today", label: "Due Today", count: dueToday.length },
        { id: "3days", label: "Next 3 Days", count: derivedWithin3Days.length },
        { id: "7days", label: "Next 7 Days", count: derivedWithin7Days.length },
        { id: "all", label: "All Active", count: overdue.length + dueToday.length + upcoming.length },
    ];

    return (
        <div className="space-y-4">
            {/* Filter Tabs */}
            <div className="flex flex-wrap items-center gap-1.5 rounded-xl bg-zinc-100/90 p-1 dark:bg-zinc-900/90">
                {tabs.map((tab) => {
                    const isActive = activeTab === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                                isActive
                                    ? tab.alert
                                        ? "bg-rose-600 text-white shadow-sm"
                                        : "bg-white text-zinc-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-100"
                                    : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
                            }`}
                        >
                            <span>{tab.label}</span>
                            <span
                                className={`rounded-full px-1.5 py-0.2 text-[10px] font-bold ${
                                    isActive
                                        ? tab.alert
                                            ? "bg-rose-700 text-white"
                                            : "bg-zinc-100 text-zinc-800 dark:bg-zinc-700 dark:text-zinc-200"
                                        : tab.alert
                                        ? "bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300"
                                        : "bg-zinc-200/80 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                                }`}
                            >
                                {tab.count}
                            </span>
                        </button>
                    );
                })}
            </div>

            {/* Task Cards List */}
            {items.length === 0 ? (
                <div className="rounded-2xl border border-zinc-200/80 bg-zinc-50/50 p-8 text-center dark:border-zinc-800 dark:bg-zinc-900/30">
                    <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400">
                        <CheckCircle2 className="h-6 w-6" />
                    </div>
                    <p className="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">{emptyMessage}</p>
                </div>
            ) : (
                <div className="space-y-2.5">
                    {items.map((task, idx) => {
                        const isTaskOverdue =
                            isOverdue ||
                            (task.overdue_days !== undefined && task.overdue_days > 0) ||
                            overdue.some((o) => o.id === task.id);

                        return (
                            <div
                                key={task.id || idx}
                                className={`group flex items-center justify-between gap-4 rounded-xl border p-4 transition-all duration-200 ${
                                    isTaskOverdue
                                        ? "border-rose-200/90 bg-rose-50/20 hover:border-rose-300 hover:bg-rose-50/40 dark:border-rose-950/60 dark:bg-rose-950/10 dark:hover:border-rose-900"
                                        : "border-zinc-200/80 bg-white hover:border-zinc-300 hover:shadow-xs dark:border-zinc-800/80 dark:bg-zinc-900/60 dark:hover:border-zinc-700"
                                }`}
                            >
                                <div className="min-w-0 flex-1 space-y-1.5">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h5 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                                            {task.title}
                                        </h5>
                                        {getPriorityBadge(task.priority)}

                                        {isTaskOverdue && (
                                            <span className="inline-flex items-center gap-1 rounded-md bg-rose-600 px-2 py-0.5 text-xs font-semibold text-white">
                                                <AlertCircle className="h-3 w-3" />
                                                Overdue
                                                {task.overdue_days && task.overdue_days > 0
                                                    ? ` (${task.overdue_days}d)`
                                                    : ""}
                                            </span>
                                        )}
                                    </div>

                                    {task.description && (
                                        <p className="line-clamp-1 text-xs text-zinc-500 dark:text-zinc-400">
                                            {task.description}
                                        </p>
                                    )}

                                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500 dark:text-zinc-400">
                                        <span className="inline-flex items-center gap-1">
                                            <Calendar className="h-3.5 w-3.5 text-zinc-400" />
                                            <span>Due: {formatDate(task.due_date)}</span>
                                        </span>

                                        {task.project && (
                                            <span className="inline-flex items-center gap-1">
                                                <FolderKanban className="h-3.5 w-3.5 text-zinc-400" />
                                                <span className="max-w-[180px] truncate">{task.project}</span>
                                            </span>
                                        )}

                                        {task.status && (
                                            <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 uppercase dark:bg-zinc-800 dark:text-zinc-400">
                                                {task.status}
                                            </span>
                                        )}
                                    </div>
                                </div>

                                <div className="shrink-0">
                                    <Link
                                        href={`/work${task.project_id ? `?project=${task.project_id}` : ""}`}
                                        className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 bg-zinc-50 px-2.5 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-zinc-100 hover:text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
                                    >
                                        <span>View</span>
                                        <ArrowUpRight className="h-3.5 w-3.5" />
                                    </Link>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
