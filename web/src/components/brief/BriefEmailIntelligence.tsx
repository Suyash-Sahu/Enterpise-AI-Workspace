"use client";

import { useState } from "react";
import { Mail, Clock, ExternalLink, Reply, ShieldAlert, Sparkles, AlertCircle, ChevronRight, Inbox } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmailDigestItem, DigestPayload } from "@/types/automation";

interface BriefEmailIntelligenceProps {
    digest?: DigestPayload;
}

export default function BriefEmailIntelligence({ digest }: BriefEmailIntelligenceProps) {
    const [activeFilter, setActiveFilter] = useState<"all" | "urgent" | "needs_reply" | "fyi" | "important" | "unread">("all");
    const [activeDateGroup, setActiveDateGroup] = useState<"all" | "today" | "yesterday" | "older">("all");
    const [selectedEmail, setSelectedEmail] = useState<EmailDigestItem | null>(null);

    const emailSection = digest?.unread_email;
    const isAvailable = emailSection?.available !== false;
    const failureReason = emailSection?.reason;

    // Collect all items from emails or legacy unread_email
    const items: EmailDigestItem[] = digest?.emails?.items || emailSection?.items || [];
    const counts = digest?.emails?.counts || {
        today: digest?.emails?.today?.length ?? 0,
        yesterday: digest?.emails?.yesterday?.length ?? 0,
        older: digest?.emails?.older?.length ?? 0,
        important: emailSection?.important ?? 0,
        urgent: emailSection?.urgent ?? 0,
        needs_reply: emailSection?.needs_reply ?? 0,
        fyi: emailSection?.fyi ?? 0,
        spam: emailSection?.spam ?? 0,
    };

    const hasMore = digest?.emails?.has_more || emailSection?.has_more || false;
    const totalUnread = digest?.emails?.total_unread || emailSection?.total_unread || items.length;

    // Filter items
    const filteredItems = items.filter((item) => {
        // Date group filter
        if (activeDateGroup !== "all" && item.date_category !== activeDateGroup) {
            return false;
        }

        // Category filter
        if (activeFilter === "all") return true;
        if (activeFilter === "urgent") return item.classification === "urgent" || item.priority === "urgent";
        if (activeFilter === "needs_reply") return item.classification === "needs_reply";
        if (activeFilter === "fyi") return item.classification === "fyi";
        if (activeFilter === "important") return item.is_important || item.classification === "urgent";
        if (activeFilter === "unread") return item.is_unread !== false;
        return true;
    });

    const formatTimestamp = (rawDate?: string) => {
        if (!rawDate) return "";
        try {
            const dt = new Date(rawDate);
            if (isNaN(dt.getTime())) return rawDate;
            const now = new Date();
            const isToday = dt.toDateString() === now.toDateString();
            if (isToday) {
                return dt.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
            }
            return dt.toLocaleDateString([], { month: "short", day: "numeric" });
        } catch {
            return rawDate;
        }
    };

    if (!isAvailable) {
        return (
            <Card className="p-6 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-destructive mb-3">
                    <ShieldAlert className="h-6 w-6" />
                </div>
                <h3 className="text-sm font-semibold text-foreground">Gmail Connection Issue</h3>
                <p className="mt-1 text-xs text-muted-foreground max-w-md mx-auto">
                    {failureReason || "Could not retrieve unread emails. Please check your Google account connection in Integrations."}
                </p>
                <Button size="sm" variant="outline" className="mt-4" onClick={() => window.open("/integrations", "_self")}>
                    Manage Integrations
                </Button>
            </Card>
        );
    }

    return (
        <div className="space-y-4">
            {/* Filter and Tab Bar */}
            <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between">
                {/* Category Filters */}
                <div className="flex flex-wrap items-center gap-1.5">
                    {[
                        { id: "all", label: "All Mail", count: items.length },
                        { id: "urgent", label: "Urgent", count: counts.urgent },
                        { id: "needs_reply", label: "Needs Reply", count: counts.needs_reply },
                        { id: "important", label: "Important", count: counts.important },
                        { id: "fyi", label: "FYI", count: counts.fyi },
                    ].map((f) => (
                        <button
                            key={f.id}
                            type="button"
                            onClick={() => setActiveFilter(f.id as any)}
                            className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                                activeFilter === f.id
                                    ? "bg-primary text-primary-foreground shadow-xs"
                                    : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground"
                            }`}
                        >
                            <span>{f.label}</span>
                            {f.count > 0 && (
                                <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${activeFilter === f.id ? "bg-primary-foreground/20 text-primary-foreground" : "bg-muted-foreground/20 text-muted-foreground"}`}>
                                    {f.count}
                                </span>
                            )}
                        </button>
                    ))}
                </div>

                {/* Date Group Selection */}
                <div className="flex items-center gap-1 rounded-lg border border-border/60 bg-muted/30 p-0.5 text-xs">
                    {(["all", "today", "yesterday", "older"] as const).map((group) => (
                        <button
                            key={group}
                            type="button"
                            onClick={() => setActiveDateGroup(group)}
                            className={`rounded-md px-2.5 py-1 text-[11px] font-medium capitalize transition-colors ${
                                activeDateGroup === group
                                    ? "bg-background text-foreground shadow-xs"
                                    : "text-muted-foreground hover:text-foreground"
                            }`}
                        >
                            {group === "all" ? "All Dates" : group}
                        </button>
                    ))}
                </div>
            </div>

            {/* Email Cards List */}
            {filteredItems.length === 0 ? (
                <Card className="flex flex-col items-center justify-center p-8 text-center bg-card/60">
                    <Inbox className="h-8 w-8 text-muted-foreground/60 mb-2" />
                    <p className="text-xs font-semibold text-foreground">No emails match the selected filters</p>
                    <p className="text-[11px] text-muted-foreground mt-0.5">Try selecting a different category or date range.</p>
                </Card>
            ) : (
                <div className="space-y-2.5">
                    {filteredItems.map((email) => {
                        const isUrgent = email.classification === "urgent" || email.priority === "urgent";
                        const isNeedsReply = email.classification === "needs_reply";

                        return (
                            <Card
                                key={email.id}
                                className={`p-4 transition-all hover:border-primary/40 hover:shadow-sm ${
                                    isUrgent ? "border-amber-500/30 bg-amber-500/5" : "bg-card"
                                }`}
                            >
                                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                                    <div className="space-y-1 min-w-0 flex-1">
                                        {/* Sender and Status Tags */}
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className="text-xs font-bold text-foreground truncate max-w-[200px]">
                                                {email.sender}
                                            </span>
                                            {email.sender_email && email.sender_email !== email.sender && (
                                                <span className="text-[11px] text-muted-foreground truncate hidden sm:inline">
                                                    &lt;{email.sender_email}&gt;
                                                </span>
                                            )}

                                            <div className="flex items-center gap-1.5 ml-auto sm:ml-0">
                                                {isUrgent && (
                                                    <Badge variant="destructive" className="text-[10px] uppercase font-semibold">
                                                        Urgent
                                                    </Badge>
                                                )}
                                                {isNeedsReply && (
                                                    <Badge variant="warning" className="text-[10px] font-semibold">
                                                        Needs Reply
                                                    </Badge>
                                                )}
                                                {email.classification === "fyi" && (
                                                    <Badge variant="secondary" className="text-[10px]">
                                                        FYI
                                                    </Badge>
                                                )}
                                                {email.date_category && (
                                                    <Badge variant="outline" className="text-[10px] capitalize text-muted-foreground">
                                                        {email.date_category}
                                                    </Badge>
                                                )}
                                            </div>
                                        </div>

                                        {/* Subject */}
                                        <h4 className="text-xs font-semibold text-foreground truncate">
                                            {email.subject}
                                        </h4>

                                        {/* Snippet / Preview */}
                                        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                                            {email.snippet || "No preview snippet available"}
                                        </p>

                                        {/* AI explanation or suggested action */}
                                        {email.classification_reason && (
                                            <div className="flex items-center gap-1.5 pt-1 text-[11px] text-primary/90 font-medium">
                                                <Sparkles className="h-3 w-3 shrink-0" />
                                                <span>{email.classification_reason}</span>
                                            </div>
                                        )}
                                    </div>

                                    {/* Action Buttons & Timestamp */}
                                    <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-start gap-2 shrink-0 pt-2 sm:pt-0">
                                        <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                                            <Clock className="h-3 w-3" />
                                            <span>{formatTimestamp(email.received_at)}</span>
                                        </div>

                                        <div className="flex items-center gap-1.5 mt-auto">
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                className="h-7 px-2.5 text-xs gap-1"
                                                onClick={() => {
                                                    const gmailUrl = `https://mail.google.com/mail/u/0/#inbox/${email.thread_id || email.id}`;
                                                    window.open(gmailUrl, "_blank", "noopener,noreferrer");
                                                }}
                                            >
                                                <ExternalLink className="h-3 w-3" />
                                                <span>Open</span>
                                            </Button>

                                            {isNeedsReply && (
                                                <Button
                                                    size="sm"
                                                    variant="secondary"
                                                    className="h-7 px-2.5 text-xs gap-1"
                                                    onClick={() => {
                                                        const replyUrl = `https://mail.google.com/mail/u/0/#inbox/${email.thread_id || email.id}`;
                                                        window.open(replyUrl, "_blank", "noopener,noreferrer");
                                                    }}
                                                >
                                                    <Reply className="h-3 w-3" />
                                                    <span>Reply</span>
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </Card>
                        );
                    })}

                    {hasMore && (
                        <div className="p-3 text-center border border-dashed rounded-lg bg-muted/20">
                            <p className="text-xs text-muted-foreground">
                                Showing {filteredItems.length} of {totalUnread} unread emails in inbox.
                            </p>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="mt-1 text-xs text-primary"
                                onClick={() => window.open("https://mail.google.com", "_blank")}
                            >
                                Open Full Gmail Inbox <ChevronRight className="h-3 w-3 ml-1" />
                            </Button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
