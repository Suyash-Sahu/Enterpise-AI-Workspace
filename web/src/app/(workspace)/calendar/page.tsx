"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import PageHeader from "@/components/shared/PageHeader";
import CreateEventModal from "@/components/calendar/CreateEventModal";
import { ConnectorErrorState } from "@/components/shared/ConnectorErrorState";
import { useCalendarEvents, useCreateCalendarEvent } from "@/hooks/useCalendar";
import { CentralEvent } from "@/data/central-store";
import { Plus, Video, Sparkles, Clock, CheckCircle2 } from "lucide-react";

// This week, in RFC3339 -- the real Calendar API's window, not a display label.
function useWeekRange() {
    return useMemo(() => {
        const now = new Date();
        const start = new Date(now);
        start.setHours(0, 0, 0, 0);
        const end = new Date(start);
        end.setDate(end.getDate() + 7);
        return { timeMin: start.toISOString(), timeMax: end.toISOString() };
    }, []);
}

export default function CalendarPage() {
    const [view, setView] = useState<"month" | "week" | "day" | "agenda">("week");
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const { timeMin, timeMax } = useWeekRange();

    const { data: events, isLoading, error, refetch } = useCalendarEvents(timeMin, timeMax);
    const createEvent = useCreateCalendarEvent();

    const handleCreateEvent = (newEvent: { title: string; date: string; time: string; category: CentralEvent["category"]; addMeet: boolean }) => {
        const start = new Date(`${newEvent.date} ${newEvent.time}`);
        if (Number.isNaN(start.getTime())) {
            toast.error("Could not understand that date/time");
            return;
        }
        const end = new Date(start.getTime() + 60 * 60 * 1000);

        createEvent.mutate(
            {
                summary: newEvent.title,
                start: start.toISOString(),
                end: end.toISOString(),
                add_meet: newEvent.addMeet,
            },
            {
                onError: () => toast.error("Could not create the event"),
            }
        );
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Calendar & Schedule"
                description="Manage team events, sprint reviews, and Google Meet video calls."
                breadcrumbs={[{ label: "Workspace" }, { label: "Calendar" }]}
                actions={
                    <button
                        onClick={() => setIsCreateOpen(true)}
                        className="flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md transition-all"
                    >
                        <Plus className="h-4 w-4" />
                        <span>Create Meeting / Event</span>
                    </button>
                }
            />

            {/* View Controls & AI Planning Banner */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-3">
                <div className="flex items-center gap-1.5">
                    {(["month", "week", "day", "agenda"] as const).map((v) => (
                        <button
                            key={v}
                            onClick={() => setView(v)}
                            className={`rounded-xl px-4 py-2 text-xs font-mono font-bold uppercase transition-all ${
                                view === v
                                    ? "bg-primary text-primary-foreground shadow-md"
                                    : "border border-border bg-surface text-muted-foreground hover:bg-muted/50"
                            }`}
                        >
                            {v}
                        </button>
                    ))}
                </div>

                <div className="flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3.5 py-1.5 font-mono text-xs font-bold text-primary">
                    <Sparkles className="h-4 w-4" />
                    <span>AI Conflict Detection Active</span>
                </div>
            </div>

            {/* AI Assistant Planning Card */}
            <div className="rounded-2xl border border-primary/20 bg-gradient-to-r from-primary/10 via-indigo-500/10 to-purple-500/10 p-5 space-y-2">
                <div className="flex items-center gap-2 text-primary font-bold text-xs">
                    <Sparkles className="h-4 w-4" />
                    <span>AMOF Schedule Optimization</span>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                    Conflict detection and focus-time suggestions run against your connected Google Calendar.
                </p>
            </div>

            {/* Events List / Agenda Grid */}
            <div className="space-y-4">
                <h3 className="text-sm font-bold text-foreground">Scheduled Events & Google Meetings</h3>

                {isLoading ? (
                    <div className="rounded-2xl border border-border bg-surface p-6 text-xs text-muted-foreground animate-pulse">
                        Loading events from Google Calendar...
                    </div>
                ) : error ? (
                    <ConnectorErrorState error={error} resource="calendar events" onRetry={() => refetch()} />
                ) : !events || events.length === 0 ? (
                    <div className="rounded-2xl border border-border bg-surface p-6 text-xs text-muted-foreground">
                        No events in the next 7 days.
                    </div>
                ) : (
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        {events.map((evt) => {
                            const startsAt = evt.start?.dateTime ?? evt.start?.date;
                            return (
                                <div key={evt.id} className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-3">
                                    <div className="space-y-1">
                                        <h4 className="text-sm font-bold text-foreground">{evt.summary || "(No title)"}</h4>
                                        {startsAt && (
                                            <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
                                                <Clock className="h-3.5 w-3.5" />
                                                <span>{new Date(startsAt).toLocaleString()}</span>
                                            </div>
                                        )}
                                    </div>

                                    {evt.hangoutLink && (
                                        <div className="flex items-center justify-between pt-2 border-t border-border">
                                            <div className="flex items-center gap-1.5 text-xs text-success font-mono font-bold">
                                                <CheckCircle2 className="h-4 w-4" />
                                                <span>Google Meet Ready</span>
                                            </div>
                                            <a
                                                href={evt.hangoutLink}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="flex items-center gap-1.5 rounded-xl bg-success px-3.5 py-1.5 text-xs font-semibold text-success-foreground shadow-md transition-all"
                                            >
                                                <Video className="h-4 w-4" />
                                                <span>Join Meeting</span>
                                            </a>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Create Event Modal */}
            <CreateEventModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} onCreate={handleCreateEvent} />
        </div>
    );
}
