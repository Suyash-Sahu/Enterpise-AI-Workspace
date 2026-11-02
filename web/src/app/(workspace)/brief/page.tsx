"use client";

import React, { useState } from "react";
import { toast } from "sonner";
import {
    Loader2,
    Mail,
    Calendar as CalendarIcon,
    ListTodo,
    Handshake,
    Lightbulb,
    RefreshCw,
    Sparkles,
    Globe,
    Clock,
    LayoutDashboard,
} from "lucide-react";

import PageHeader from "@/components/shared/PageHeader";
import DataState from "@/components/shared/DataState";
import EmptyState from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";

import BriefOverview from "@/components/brief/BriefOverview";
import BriefAiSummary from "@/components/brief/BriefAiSummary";
import { BriefSuggestedActions } from "@/components/brief/BriefSuggestedActions";
import BriefEmailIntelligence from "@/components/brief/BriefEmailIntelligence";
import { BriefCalendarAgenda } from "@/components/brief/BriefCalendarAgenda";
import { BriefTasksDeadlines } from "@/components/brief/BriefTasksDeadlines";
import { BriefCommitments } from "@/components/brief/BriefCommitments";

import { useLatestDigest, useRunDigestNow } from "@/hooks/useAutomations";
import { DigestPayload, TaskDigestItem, CalendarDigestItem, EmailDigestItem } from "@/types/automation";

type ActiveSection = "all" | "emails" | "calendar" | "tasks" | "commitments";

export default function MorningBriefPage() {
    const { data, isLoading, isError, error, refetch, isFetching } = useLatestDigest();
    const runNow = useRunDigestNow();
    const [activeSection, setActiveSection] = useState<ActiveSection>("all");

    const digest = (data?.digest as DigestPayload | undefined) ?? undefined;

    const formatGeneratedTime = (isoString?: string) => {
        if (!isoString) return "";
        try {
            const date = new Date(isoString);
            return date.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                timeZone: digest?.timezone || undefined,
            });
        } catch {
            return isoString;
        }
    };

    const formatCurrentDate = (isoDate?: string) => {
        try {
            const d = isoDate ? new Date(isoDate) : new Date();
            return d.toLocaleDateString("en-US", {
                weekday: "long",
                month: "long",
                day: "numeric",
                year: "numeric",
                timeZone: digest?.timezone || undefined,
            });
        } catch {
            return isoDate || new Date().toDateString();
        }
    };

    // Normalize email items
    const emailItems: EmailDigestItem[] =
        digest?.emails?.items ||
        digest?.unread_email?.items ||
        [
            ...(digest?.emails?.today || []),
            ...(digest?.emails?.yesterday || []),
            ...(digest?.emails?.older || []),
        ];

    // Normalize calendar items
    const calendarItems: CalendarDigestItem[] =
        digest?.calendar?.events ||
        digest?.today_events?.items ||
        [];

    const calendarConflicts =
        digest?.calendar?.conflicts ||
        digest?.today_events?.conflicts ||
        [];

    const nextCalendarEvent =
        digest?.calendar?.next_event ||
        digest?.today_events?.next_event ||
        null;

    const calendarRequiresReauth =
        digest?.calendar?.requires_reauth ||
        digest?.today_events?.requires_reauth ||
        false;

    const calendarAvailable =
        digest?.today_events?.available ?? (digest?.source_status?.calendar !== "disconnected");

    // Normalize tasks
    const overdueTasks: TaskDigestItem[] =
        digest?.tasks?.overdue ||
        digest?.overdue_tasks?.items ||
        [];

    const dueTodayTasks: TaskDigestItem[] =
        digest?.tasks?.due_today ||
        digest?.upcoming_deadlines?.due_today ||
        [];

    const upcomingTasks: TaskDigestItem[] =
        digest?.tasks?.upcoming ||
        digest?.upcoming_deadlines?.items ||
        [];

    const within3DaysTasks: TaskDigestItem[] =
        digest?.upcoming_deadlines?.within_3_days || [];

    const within7DaysTasks: TaskDigestItem[] =
        digest?.upcoming_deadlines?.within_7_days || [];

    // Normalize commitments
    const atRiskCommitments =
        digest?.commitments?.at_risk ||
        digest?.at_risk_commitments?.items ||
        [];

    // Normalize suggested actions
    const suggestedActions = digest?.suggested_actions || [];

    return (
        <div className="space-y-6 pb-12">
            {/* Header with Title, Date, Timezone & Action Buttons */}
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                <div>
                    <div className="flex flex-wrap items-center gap-2.5">
                        <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
                            Morning Brief
                        </h1>
                        {digest?.timezone && (
                            <span className="inline-flex items-center gap-1 rounded-full border border-zinc-200/80 bg-zinc-100/70 px-2.5 py-0.5 text-xs font-medium text-zinc-600 dark:border-zinc-800 dark:bg-zinc-800/80 dark:text-zinc-300">
                                <Globe className="h-3 w-3 text-zinc-400" />
                                {digest.timezone}
                            </span>
                        )}
                        {digest?.generated_at && (
                            <span className="inline-flex items-center gap-1 rounded-full border border-zinc-200/80 bg-zinc-50 px-2.5 py-0.5 text-xs text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
                                <Clock className="h-3 w-3" />
                                Generated {formatGeneratedTime(digest.generated_at)}
                            </span>
                        )}
                    </div>
                    <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                        {formatCurrentDate(digest?.date)} &bull; Unified executive overview across your emails, agenda, tasks, and commitments.
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        disabled={isFetching}
                        onClick={() => {
                            refetch();
                            toast.info("Refreshed latest brief");
                        }}
                        className="gap-1.5"
                    >
                        <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
                        <span>Refresh</span>
                    </Button>

                    <Button
                        size="sm"
                        disabled={runNow.isPending}
                        onClick={() =>
                            runNow.mutate(undefined, {
                                onSuccess: () => {
                                    refetch();
                                    toast.success("Morning Brief successfully generated");
                                },
                                onError: () => toast.error("Could not generate the brief. Please try again."),
                            })
                        }
                        className="gap-1.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-sm hover:from-indigo-500 hover:to-violet-500"
                    >
                        {runNow.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Sparkles className="h-4 w-4" />
                        )}
                        <span>{runNow.isPending ? "Generating Brief..." : "Generate Now"}</span>
                    </Button>
                </div>
            </div>

            <DataState
                isLoading={isLoading}
                isError={isError && (error as { status?: number })?.status !== 404}
                error={error}
                isEmpty={!data}
                onRetry={() => refetch()}
                resource="your morning brief"
                empty={
                    <EmptyState
                        icon={<Sparkles className="h-10 w-10 text-indigo-500" />}
                        title="No Morning Brief generated yet"
                        description="Click 'Generate Now' above to build your unified daily brief from Gmail, Google Calendar, active tasks, and commitments."
                    />
                }
            >
                {digest && (
                    <div className="space-y-6">
                        {/* 1. Overview Metrics Cards */}
                        <BriefOverview
                            digest={digest}
                            onSelectMetric={(metric: string) => {
                                if (metric === "unread" || metric === "important" || metric === "emails") setActiveSection("emails");
                                else if (metric === "tasks") setActiveSection("tasks");
                                else if (metric === "events" || metric === "calendar") setActiveSection("calendar");
                            }}
                        />

                        {/* 2. AI Daily Summary & Grounded Insights */}
                        <BriefAiSummary digest={digest} />

                        {/* 3. Section Navigation Tabs */}
                        <div className="flex flex-wrap items-center gap-1.5 border-b border-zinc-200/80 pb-3 dark:border-zinc-800/80">
                            <button
                                onClick={() => setActiveSection("all")}
                                className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                                    activeSection === "all"
                                        ? "bg-zinc-900 text-white shadow-xs dark:bg-white dark:text-zinc-900"
                                        : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800"
                                }`}
                            >
                                <LayoutDashboard className="h-3.5 w-3.5" />
                                <span>Complete Dashboard</span>
                            </button>

                            <button
                                onClick={() => setActiveSection("emails")}
                                className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                                    activeSection === "emails"
                                        ? "bg-zinc-900 text-white shadow-xs dark:bg-white dark:text-zinc-900"
                                        : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800"
                                }`}
                            >
                                <Mail className="h-3.5 w-3.5" />
                                <span>Inbox Intelligence</span>
                                {emailItems.length > 0 && (
                                    <span className="rounded-full bg-zinc-200/80 px-1.5 py-0.2 text-[10px] font-bold text-zinc-700 dark:bg-zinc-700 dark:text-zinc-300">
                                        {emailItems.length}
                                    </span>
                                )}
                            </button>

                            <button
                                onClick={() => setActiveSection("calendar")}
                                className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                                    activeSection === "calendar"
                                        ? "bg-zinc-900 text-white shadow-xs dark:bg-white dark:text-zinc-900"
                                        : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800"
                                }`}
                            >
                                <CalendarIcon className="h-3.5 w-3.5" />
                                <span>Schedule</span>
                                {calendarItems.length > 0 && (
                                    <span className="rounded-full bg-zinc-200/80 px-1.5 py-0.2 text-[10px] font-bold text-zinc-700 dark:bg-zinc-700 dark:text-zinc-300">
                                        {calendarItems.length}
                                    </span>
                                )}
                            </button>

                            <button
                                onClick={() => setActiveSection("tasks")}
                                className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                                    activeSection === "tasks"
                                        ? "bg-zinc-900 text-white shadow-xs dark:bg-white dark:text-zinc-900"
                                        : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800"
                                }`}
                            >
                                <ListTodo className="h-3.5 w-3.5" />
                                <span>Tasks & Deadlines</span>
                                {overdueTasks.length > 0 && (
                                    <span className="rounded-full bg-rose-100 px-1.5 py-0.2 text-[10px] font-bold text-rose-700 dark:bg-rose-950/60 dark:text-rose-300">
                                        {overdueTasks.length} overdue
                                    </span>
                                )}
                            </button>

                            <button
                                onClick={() => setActiveSection("commitments")}
                                className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                                    activeSection === "commitments"
                                        ? "bg-zinc-900 text-white shadow-xs dark:bg-white dark:text-zinc-900"
                                        : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800"
                                }`}
                            >
                                <Handshake className="h-3.5 w-3.5" />
                                <span>Commitments</span>
                                {atRiskCommitments.length > 0 && (
                                    <span className="rounded-full bg-amber-100 px-1.5 py-0.2 text-[10px] font-bold text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
                                        {atRiskCommitments.length} at risk
                                    </span>
                                )}
                            </button>
                        </div>

                        {/* 4. Suggested Actions */}
                        {suggestedActions.length > 0 && (activeSection === "all" || activeSection === "tasks") && (
                            <section className="space-y-2">
                                <BriefSuggestedActions actions={suggestedActions} />
                            </section>
                        )}

                        {/* 5. Detailed Sections */}
                        {(activeSection === "all" || activeSection === "emails") && (
                            <section id="emails-section" className="space-y-3 pt-2">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <Mail className="h-4 w-4 text-sky-600 dark:text-sky-400" />
                                        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                                            Email Intelligence
                                        </h3>
                                    </div>
                                    <span className="text-xs text-zinc-500 dark:text-zinc-400">
                                        Categorized by urgency & priority
                                    </span>
                                </div>
                                <BriefEmailIntelligence digest={digest} />
                            </section>
                        )}

                        {(activeSection === "all" || activeSection === "calendar") && (
                            <section id="agenda-section" className="space-y-3 pt-2">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <CalendarIcon className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                                        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                                            Today&apos;s Schedule & Agenda
                                        </h3>
                                    </div>
                                    <span className="text-xs text-zinc-500 dark:text-zinc-400">
                                        Chronological timeline & meeting links
                                    </span>
                                </div>
                                <BriefCalendarAgenda
                                    events={calendarItems}
                                    conflicts={calendarConflicts}
                                    nextEvent={nextCalendarEvent}
                                    requiresReauth={calendarRequiresReauth}
                                    available={calendarAvailable}
                                    reason={digest.today_events?.reason}
                                    timezone={digest.timezone}
                                />
                            </section>
                        )}

                        {(activeSection === "all" || activeSection === "tasks") && (
                            <section id="tasks-section" className="space-y-3 pt-2">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <ListTodo className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                                        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                                            Tasks & Upcoming Deadlines
                                        </h3>
                                    </div>
                                    <span className="text-xs text-zinc-500 dark:text-zinc-400">
                                        Overdue items, due today, and near-term milestones
                                    </span>
                                </div>
                                <BriefTasksDeadlines
                                    overdue={overdueTasks}
                                    dueToday={dueTodayTasks}
                                    upcoming={upcomingTasks}
                                    within3Days={within3DaysTasks}
                                    within7Days={within7DaysTasks}
                                    timezone={digest.timezone}
                                />
                            </section>
                        )}

                        {(activeSection === "all" || activeSection === "commitments") && (
                            <section id="commitments-section" className="space-y-3 pt-2">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <Handshake className="h-4 w-4 text-rose-600 dark:text-rose-400" />
                                        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                                            At-Risk Commitments & Follow-ups
                                        </h3>
                                    </div>
                                    <span className="text-xs text-zinc-500 dark:text-zinc-400">
                                        Deliverables requiring attention or follow-up
                                    </span>
                                </div>
                                <BriefCommitments
                                    commitments={atRiskCommitments}
                                    timezone={digest.timezone}
                                />
                            </section>
                        )}
                    </div>
                )}
            </DataState>
        </div>
    );
}
