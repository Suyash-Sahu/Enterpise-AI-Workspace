"use client";

import React from "react";
import {
    Calendar as CalendarIcon,
    Clock,
    MapPin,
    Video,
    Users,
    AlertTriangle,
    ExternalLink,
    CheckCircle2,
    RefreshCw,
    Sparkles,
} from "lucide-react";
import { CalendarDigestItem } from "@/types/automation";
import Link from "next/link";

interface BriefCalendarAgendaProps {
    events?: CalendarDigestItem[];
    conflicts?: { event_a: string; event_b: string }[];
    nextEvent?: CalendarDigestItem | null;
    requiresReauth?: boolean;
    available?: boolean;
    reason?: string;
    timezone?: string;
}

export function BriefCalendarAgenda({
    events = [],
    conflicts = [],
    nextEvent,
    requiresReauth = false,
    available = true,
    reason,
    timezone,
}: BriefCalendarAgendaProps) {
    const formatTime = (isoString?: string) => {
        if (!isoString) return "";
        try {
            const date = new Date(isoString);
            return date.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                timeZone: timezone || undefined,
            });
        } catch {
            return isoString;
        }
    };

    const formatDuration = (startStr?: string, endStr?: string) => {
        if (!startStr || !endStr) return "";
        try {
            const start = new Date(startStr);
            const end = new Date(endStr);
            const diffMin = Math.round((end.getTime() - start.getTime()) / (1000 * 60));
            if (diffMin <= 0) return "";
            if (diffMin < 60) return `${diffMin}m`;
            const hours = Math.floor(diffMin / 60);
            const mins = diffMin % 60;
            return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
        } catch {
            return "";
        }
    };

    const isNext = (item: CalendarDigestItem) => {
        if (!nextEvent) return false;
        if (nextEvent.id && item.id && nextEvent.id === item.id) return true;
        return nextEvent.title === item.title && nextEvent.start === item.start;
    };

    // 1. Reauth / Scope Required State
    if (requiresReauth || (reason && reason.toLowerCase().includes("reauth"))) {
        return (
            <div className="rounded-2xl border border-amber-200/80 bg-gradient-to-br from-amber-50/70 via-white to-amber-50/40 p-6 dark:border-amber-900/50 dark:from-amber-950/20 dark:via-zinc-900/60 dark:to-amber-950/10">
                <div className="flex items-start gap-4">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
                        <AlertTriangle className="h-6 w-6" />
                    </div>
                    <div className="flex-1 space-y-2">
                        <h4 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                            Google Calendar Permission Required
                        </h4>
                        <p className="text-sm text-zinc-600 dark:text-zinc-400">
                            AMOF requires read access to your Google Calendar events (
                            <code className="rounded bg-amber-100/60 px-1 py-0.5 text-xs font-mono text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
                                calendar.events.readonly
                            </code>
                            ) to display your daily schedule and meeting preparation notes.
                        </p>
                        <div className="pt-2">
                            <Link
                                href="/settings/integrations"
                                className="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-amber-700 active:scale-95 dark:bg-amber-600 dark:hover:bg-amber-500"
                            >
                                <RefreshCw className="h-4 w-4" />
                                Reconnect Google Workspace
                            </Link>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // 2. Unavailable State (Disabled or disconnected)
    if (!available) {
        return (
            <div className="rounded-2xl border border-zinc-200/80 bg-zinc-50/60 p-6 text-center dark:border-zinc-800 dark:bg-zinc-900/40">
                <CalendarIcon className="mx-auto h-8 w-8 text-zinc-400 dark:text-zinc-600" />
                <h4 className="mt-2 text-sm font-semibold text-zinc-800 dark:text-zinc-200">
                    Calendar Integration Unavailable
                </h4>
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                    {reason || "Connect Google Calendar in workspace integrations to view your agenda."}
                </p>
                <div className="mt-4">
                    <Link
                        href="/settings/integrations"
                        className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                    >
                        Check Integrations
                    </Link>
                </div>
            </div>
        );
    }

    // 3. Empty Agenda
    if (events.length === 0) {
        return (
            <div className="rounded-2xl border border-zinc-200/80 bg-gradient-to-br from-white via-zinc-50/50 to-white p-8 text-center dark:border-zinc-800/80 dark:from-zinc-900/60 dark:via-zinc-950/40 dark:to-zinc-900/60">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 ring-1 ring-emerald-200/60 dark:bg-emerald-950/30 dark:text-emerald-400 dark:ring-emerald-800/40">
                    <CheckCircle2 className="h-6 w-6" />
                </div>
                <h4 className="mt-3 text-base font-semibold text-zinc-900 dark:text-zinc-100">
                    Clear Calendar Today
                </h4>
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                    No scheduled meetings for today. You have uninterrupted focus time!
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Overlap / Conflict Alert */}
            {conflicts.length > 0 && (
                <div className="flex items-center gap-3 rounded-xl border border-rose-200/80 bg-rose-50/70 p-3.5 text-sm text-rose-800 dark:border-rose-900/40 dark:bg-rose-950/20 dark:text-rose-300">
                    <AlertTriangle className="h-5 w-5 shrink-0 text-rose-600 dark:text-rose-400" />
                    <div>
                        <span className="font-semibold">Schedule Conflict Detected: </span>
                        {conflicts.map((c, i) => (
                            <span key={i}>
                                &quot;{c.event_a}&quot; overlaps with &quot;{c.event_b}&quot;{i < conflicts.length - 1 ? "; " : ""}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Timeline / Agenda List */}
            <div className="relative space-y-3.5 before:absolute before:bottom-3 before:left-5 before:top-3 before:w-0.5 before:bg-zinc-200 dark:before:bg-zinc-800">
                {events.map((event, idx) => {
                    const isNextEvent = isNext(event);
                    const duration = formatDuration(event.start, event.end);

                    return (
                        <div
                            key={event.id || `${event.title}-${idx}`}
                            className={`group relative flex gap-4 rounded-2xl border p-4.5 transition-all duration-200 ${
                                isNextEvent
                                    ? "border-indigo-300/80 bg-gradient-to-r from-indigo-50/80 via-white to-indigo-50/30 shadow-sm dark:border-indigo-800/60 dark:from-indigo-950/25 dark:via-zinc-900/80 dark:to-indigo-950/15"
                                    : "border-zinc-200/80 bg-white hover:border-zinc-300 dark:border-zinc-800/80 dark:bg-zinc-900/60 dark:hover:border-zinc-700"
                            }`}
                        >
                            {/* Time Pill on Left */}
                            <div className="relative z-10 flex w-24 shrink-0 flex-col items-center justify-center rounded-xl bg-zinc-100/90 py-2.5 text-center dark:bg-zinc-800/80">
                                {event.is_all_day ? (
                                    <span className="text-xs font-semibold uppercase tracking-wider text-zinc-700 dark:text-zinc-300">
                                        All Day
                                    </span>
                                ) : (
                                    <>
                                        <span className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                                            {formatTime(event.start)}
                                        </span>
                                        {event.end && (
                                            <span className="text-[11px] text-zinc-500 dark:text-zinc-400">
                                                to {formatTime(event.end)}
                                            </span>
                                        )}
                                        {duration && (
                                            <span className="mt-1 rounded-full bg-zinc-200/70 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-700/60 dark:text-zinc-300">
                                                {duration}
                                            </span>
                                        )}
                                    </>
                                )}
                            </div>

                            {/* Details */}
                            <div className="min-w-0 flex-1 space-y-2">
                                <div className="flex flex-wrap items-center gap-2">
                                    <h4 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                                        {event.title || "Untitled Meeting"}
                                    </h4>

                                    {isNextEvent && (
                                        <span className="inline-flex items-center gap-1 rounded-full bg-indigo-600 px-2.5 py-0.5 text-xs font-semibold text-white shadow-sm">
                                            <Clock className="h-3 w-3" />
                                            Next Up
                                        </span>
                                    )}

                                    {event.is_all_day && (
                                        <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                                            Full Day
                                        </span>
                                    )}
                                </div>

                                {event.description && (
                                    <p className="line-clamp-2 text-xs text-zinc-600 dark:text-zinc-400">
                                        {event.description}
                                    </p>
                                )}

                                {/* Location & Participants & Prep Notes */}
                                <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-zinc-500 dark:text-zinc-400">
                                    {event.location && (
                                        <span className="inline-flex items-center gap-1">
                                            <MapPin className="h-3.5 w-3.5 text-zinc-400" />
                                            <span className="max-w-[200px] truncate">{event.location}</span>
                                        </span>
                                    )}

                                    {event.participants && event.participants.length > 0 && (
                                        <span className="inline-flex items-center gap-1">
                                            <Users className="h-3.5 w-3.5 text-zinc-400" />
                                            <span>
                                                {event.participants.length} attendee{event.participants.length > 1 ? "s" : ""}
                                            </span>
                                        </span>
                                    )}
                                </div>

                                {event.prep_notes && (
                                    <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-2.5 text-xs text-indigo-900 dark:border-indigo-950/60 dark:bg-indigo-950/30 dark:text-indigo-200">
                                        <span className="font-semibold inline-flex items-center gap-1">
                                            <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
                                            Meeting Prep:
                                        </span>{" "}
                                        {event.prep_notes}
                                    </div>
                                )}
                            </div>

                            {/* Meeting Link / Action */}
                            {event.meeting_link && (
                                <div className="shrink-0 self-center">
                                    <a
                                        href={event.meeting_link}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-50 px-3.5 py-2 text-xs font-semibold text-indigo-700 transition hover:bg-indigo-100 active:scale-95 dark:bg-indigo-950/50 dark:text-indigo-300 dark:hover:bg-indigo-900/60"
                                    >
                                        <Video className="h-3.5 w-3.5" />
                                        <span>Join</span>
                                        <ExternalLink className="h-3 w-3 opacity-60" />
                                    </a>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
