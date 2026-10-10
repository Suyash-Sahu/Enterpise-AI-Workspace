"use client";

import { toast } from "sonner";
import { Loader2, Mail, Calendar, ListTodo, Clock, Handshake, Lightbulb, RefreshCw } from "lucide-react";

import PageHeader from "@/components/shared/PageHeader";
import DataState from "@/components/shared/DataState";
import EmptyState from "@/components/shared/EmptyState";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useLatestDigest, useRunDigestNow } from "@/hooks/useAutomations";

interface DigestSection {
    available?: boolean;
    count?: number;
    items?: Record<string, unknown>[];
    reason?: string;
    conflicts?: { event_a: string; event_b: string }[];
}

interface DigestPayload {
    generated_at?: string;
    unread_email?: DigestSection;
    today_events?: DigestSection;
    overdue_tasks?: DigestSection;
    upcoming_deadlines?: DigestSection;
    at_risk_commitments?: DigestSection;
    suggested_actions?: string[];
}

export default function MorningBriefPage() {
    const { data, isLoading, isError, error, refetch } = useLatestDigest();
    const runNow = useRunDigestNow();

    const digest = (data?.digest as DigestPayload | undefined) ?? undefined;

    return (
        <div className="space-y-6">
            <PageHeader
                title="Morning Brief"
                description="Unread mail, today's schedule, overdue tasks, upcoming deadlines, and at-risk commitments -- one view."
                actions={
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => refetch()}>
                            <RefreshCw aria-hidden />
                            Refresh
                        </Button>
                        <Button
                            size="sm"
                            disabled={runNow.isPending}
                            onClick={() =>
                                runNow.mutate(undefined, {
                                    onSuccess: () => toast.success("Morning brief generated"),
                                    onError: () => toast.error("Could not generate the brief"),
                                })
                            }
                        >
                            {runNow.isPending ? <Loader2 className="animate-spin" /> : null}
                            Generate now
                        </Button>
                    </div>
                }
            />

            <DataState
                isLoading={isLoading}
                isError={isError && (error as { status?: number })?.status !== 404}
                error={error}
                isEmpty={!data}
                onRetry={() => refetch()}
                resource="your morning brief"
                empty={
                    <EmptyState
                        icon={<Lightbulb />}
                        title="No brief yet"
                        description="Click 'Generate now' to build your first Morning Brief."
                    />
                }
            >
                {digest && (
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        <BriefCard
                            icon={<Mail className="h-4 w-4" />}
                            title="Unread email"
                            section={digest.unread_email}
                            renderItem={(item) => String(item.subject ?? "No subject")}
                        />
                        <BriefCard
                            icon={<Calendar className="h-4 w-4" />}
                            title="Today's events"
                            section={digest.today_events}
                            renderItem={(item) => String(item.summary ?? "(no title)")}
                            extra={
                                digest.today_events?.conflicts?.length ? (
                                    <p className="text-xs text-destructive">
                                        {digest.today_events.conflicts.length} conflict(s)
                                    </p>
                                ) : null
                            }
                        />
                        <BriefCard
                            icon={<ListTodo className="h-4 w-4" />}
                            title="Overdue tasks"
                            section={digest.overdue_tasks}
                            renderItem={(item) => String(item.title ?? "")}
                        />
                        <BriefCard
                            icon={<Clock className="h-4 w-4" />}
                            title="Upcoming deadlines"
                            section={digest.upcoming_deadlines}
                            renderItem={(item) => String(item.title ?? "")}
                        />
                        <BriefCard
                            icon={<Handshake className="h-4 w-4" />}
                            title="At-risk commitments"
                            section={digest.at_risk_commitments}
                            renderItem={(item) => String(item.description ?? "")}
                        />
                        <Card className="p-5">
                            <div className="mb-3 flex items-center gap-2 text-xs font-bold text-foreground">
                                <Lightbulb className="h-4 w-4 text-primary" />
                                <span>Suggested actions</span>
                            </div>
                            {digest.suggested_actions?.length ? (
                                <ul className="space-y-1.5 text-xs text-muted-foreground">
                                    {digest.suggested_actions.map((a, i) => (
                                        <li key={i}>&bull; {a}</li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="text-xs text-muted-foreground">Nothing needs attention right now.</p>
                            )}
                        </Card>
                    </div>
                )}
            </DataState>
        </div>
    );
}

function BriefCard({
    icon,
    title,
    section,
    renderItem,
    extra,
}: {
    icon: React.ReactNode;
    title: string;
    section?: DigestSection;
    renderItem: (item: Record<string, unknown>) => string;
    extra?: React.ReactNode;
}) {
    return (
        <Card className="p-5">
            <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-bold text-foreground">
                    {icon}
                    <span>{title}</span>
                </div>
                <span className="text-xs text-muted-foreground">{section?.available ? section.count ?? 0 : "—"}</span>
            </div>
            {!section?.available ? (
                <p className="text-xs text-muted-foreground">Unavailable{section?.reason ? `: ${section.reason}` : ""}</p>
            ) : section.items?.length ? (
                <ul className="space-y-1.5 text-xs text-muted-foreground">
                    {section.items.slice(0, 5).map((item, i) => (
                        <li key={i} className="truncate">{renderItem(item)}</li>
                    ))}
                </ul>
            ) : (
                <p className="text-xs text-muted-foreground">Nothing here.</p>
            )}
            {extra}
        </Card>
    );
}
