"use client";

import { Mail, AlertCircle, ListTodo, Calendar, ArrowUpRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DigestPayload } from "@/types/automation";

interface BriefOverviewProps {
    digest?: DigestPayload;
    activeSection?: string;
    onSectionClick?: (section: string) => void;
    onSelectMetric?: (metric: string) => void;
}

export default function BriefOverview({
    digest,
    activeSection,
    onSectionClick,
    onSelectMetric,
}: BriefOverviewProps) {
    const handleSelect = onSelectMetric || onSectionClick;
    const unread = digest?.unread_email ?? {};
    const emails = digest?.emails ?? {};
    const calendar = digest?.calendar ?? {};
    const todayEvents = digest?.today_events ?? {};
    const tasks = digest?.tasks ?? {};
    const overdueTasks = digest?.overdue_tasks ?? {};

    const totalUnread = digest?.overview?.total_unread ?? unread.total_unread ?? unread.count ?? 0;
    const importantCount = digest?.overview?.important_emails ?? unread.important ?? emails?.counts?.urgent ?? 0;
    const overdueCount = digest?.overview?.overdue_tasks ?? overdueTasks.count ?? tasks?.overdue?.length ?? 0;
    const eventsCount = digest?.overview?.today_events ?? todayEvents.count ?? calendar.total ?? calendar.events?.length ?? 0;

    const cards = [
        {
            id: "emails",
            title: "Unread Emails",
            count: totalUnread,
            subtitle: unread.available === false ? "Gmail disconnected" : `${emails?.counts?.needs_reply ?? unread.needs_reply ?? 0} need reply`,
            icon: Mail,
            color: "text-blue-500",
            bg: "bg-blue-500/10",
            badgeVariant: "secondary" as const,
            badgeText: emails?.has_more || unread.has_more ? "More in inbox" : "Synced",
        },
        {
            id: "important",
            title: "Important Emails",
            count: importantCount,
            subtitle: "Requires attention today",
            icon: AlertCircle,
            color: "text-amber-500",
            bg: "bg-amber-500/10",
            badgeVariant: importantCount > 0 ? ("warning" as const) : ("secondary" as const),
            badgeText: importantCount > 0 ? "High priority" : "Clear",
        },
        {
            id: "tasks",
            title: "Overdue Tasks",
            count: overdueCount,
            subtitle: overdueCount > 0 ? "Deadline passed" : "All tasks up to date",
            icon: ListTodo,
            color: "text-rose-500",
            bg: "bg-rose-500/10",
            badgeVariant: overdueCount > 0 ? ("destructive" as const) : ("success" as const),
            badgeText: overdueCount > 0 ? "Attention" : "On track",
        },
        {
            id: "calendar",
            title: "Today's Schedule",
            count: eventsCount,
            subtitle: todayEvents.conflicts?.length ? `${todayEvents.conflicts.length} conflict(s)` : (todayEvents.available === false ? "Reauth required" : "Confirmed agenda"),
            icon: Calendar,
            color: "text-emerald-500",
            bg: "bg-emerald-500/10",
            badgeVariant: todayEvents.conflicts?.length ? ("destructive" as const) : ("info" as const),
            badgeText: todayEvents.requires_reauth ? "Connect" : `${eventsCount} scheduled`,
        },
    ];

    return (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {cards.map((c) => {
                const Icon = c.icon;
                const isSelected = activeSection === c.id;
                return (
                    <Card
                        key={c.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => handleSelect?.(c.id)}
                        onKeyDown={(e) => e.key === "Enter" && handleSelect?.(c.id)}
                        className={`group relative cursor-pointer p-4 transition-all duration-200 hover:border-primary/50 hover:shadow-md ${
                            isSelected ? "border-primary bg-primary/5 ring-1 ring-primary/30" : "bg-card"
                        }`}
                    >
                        <div className="flex items-start justify-between">
                            <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${c.bg}`}>
                                <Icon className={`h-4 w-4 ${c.color}`} />
                            </div>
                            <Badge variant={c.badgeVariant} className="text-[10px] uppercase tracking-wider">
                                {c.badgeText}
                            </Badge>
                        </div>

                        <div className="mt-3">
                            <div className="text-2xl font-bold tracking-tight text-foreground">{c.count}</div>
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold text-foreground">{c.title}</span>
                                <ArrowUpRight className="h-3 w-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                            </div>
                            <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{c.subtitle}</p>
                        </div>
                    </Card>
                );
            })}
        </div>
    );
}
