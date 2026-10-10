"use client";

import { useState } from "react";
import PageHeader from "@/components/shared/PageHeader";
import { useNotificationStore } from "@/stores/notification.store";
import { PriorityBadge } from "@/components/shared/BadgeVariants";
import { Bell, CheckCheck, FolderKanban, Calendar, Mail, Sparkles, Activity, AtSign, Settings2, Sliders } from "lucide-react";

export default function NotificationsPage() {
    const { notifications, unreadCount, markAsRead, markAllAsRead } = useNotificationStore();
    const [tab, setTab] = useState<"all" | "unread" | "mentions" | "ai" | "system" | "activity" | "preferences">("all");

    // Notification channel preferences state
    const [emailAlerts, setEmailAlerts] = useState(true);
    const [slackAlerts, setSlackAlerts] = useState(false);
    const [desktopAlerts, setDesktopAlerts] = useState(true);

    const filtered = notifications.filter((n) => {
        if (tab === "unread") return !n.read;
        if (tab === "mentions") return n.title.toLowerCase().includes("mention") || n.description.toLowerCase().includes("assigned");
        if (tab === "ai") return n.module === "AMOF AI Router";
        if (tab === "system") return n.module === "Security";
        return true;
    });

    return (
        <div className="space-y-6">
            <PageHeader
                title="Notifications & Activity Center"
                description="Unified notification stream and real-time activity log from all modules."
                breadcrumbs={[{ label: "Workspace" }, { label: "Notifications" }]}
                actions={
                    <button
                        onClick={markAllAsRead}
                        className="flex items-center gap-1.5 rounded-xl border border-border bg-surface px-4 py-2 text-xs font-semibold text-foreground hover:bg-muted/50 transition-colors"
                    >
                        <CheckCheck className="h-4 w-4 text-success" />
                        <span>Mark All as Read</span>
                    </button>
                }
            />

            {/* Tab Controls */}
            <div className="flex items-center gap-1.5 overflow-x-auto border-b border-border pb-3">
                {[
                    { id: "all", label: `All (${notifications.length})`, icon: Bell },
                    { id: "unread", label: `Unread (${unreadCount})`, icon: CheckCheck },
                    { id: "mentions", label: "Mentions", icon: AtSign },
                    { id: "ai", label: "AI Alerts", icon: Sparkles },
                    { id: "activity", label: "Activity Log", icon: Activity },
                    { id: "preferences", label: "Preferences", icon: Sliders },
                ].map((t) => {
                    const Icon = t.icon;
                    const isSelected = tab === t.id;
                    return (
                        <button
                            key={t.id}
                            onClick={() => setTab(t.id as any)}
                            className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all ${
                                isSelected
                                    ? "bg-primary text-primary-foreground shadow-md font-bold"
                                    : "border border-border bg-surface text-muted-foreground hover:bg-muted/50"
                            }`}
                        >
                            <Icon className="h-3.5 w-3.5" />
                            <span>{t.label}</span>
                        </button>
                    );
                })}
            </div>

            {/* Stream Views */}
            {tab !== "activity" && tab !== "preferences" && (
                <div className="space-y-3 max-w-3xl">
                    {filtered.length > 0 ? (
                        filtered.map((notif) => (
                            <div
                                key={notif.id}
                                onClick={() => markAsRead(notif.id)}
                                className={`flex items-start justify-between rounded-2xl border p-4 transition-all cursor-pointer ${
                                    notif.read
                                        ? "border-border bg-surface/60 opacity-80"
                                        : "border-primary/40 bg-surface shadow-sm hover:border-primary"
                                }`}
                            >
                                <div className="flex items-start gap-3">
                                    <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20">
                                        <Bell className="h-4 w-4" />
                                    </div>
                                    <div className="space-y-1">
                                        <div className="flex items-center gap-2">
                                            <h4 className="text-xs font-bold text-foreground">{notif.title}</h4>
                                            <span className="font-mono text-[10px] text-muted-foreground">({notif.module})</span>
                                        </div>
                                        <p className="text-xs text-muted-foreground leading-relaxed">{notif.description}</p>
                                        <span className="font-mono text-xs text-muted-foreground">{notif.createdAt}</span>
                                    </div>
                                </div>
                                <PriorityBadge priority={notif.priority} />
                            </div>
                        ))
                    ) : (
                        <div className="rounded-2xl border border-dashed border-border p-12 text-center text-xs text-muted-foreground">
                            🎉 You're all caught up in this category!
                        </div>
                    )}
                </div>
            )}

            {/* Activity History View */}
            {tab === "activity" && (
                <div className="rounded-2xl border border-border bg-surface p-6 max-w-3xl space-y-4">
                    <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                        <Activity className="h-4 w-4 text-primary" />
                        <span>Real-Time Workspace Activity Timeline</span>
                    </h3>
                    <div className="space-y-3 text-xs text-muted-foreground font-mono">
                        <p>• 10:14 AM — Rahul Sharma merged PR #42 (Hybrid RAG RRF tuning)</p>
                        <p>• 09:30 AM — AMOF AI generated schedule risk recommendation</p>
                        <p>• 08:00 AM — Sarah Jenkins sent authentication review sign-off email</p>
                    </div>
                </div>
            )}

            {/* Notification Preferences View */}
            {tab === "preferences" && (
                <div className="rounded-2xl border border-border bg-surface p-6 max-w-xl space-y-4">
                    <h3 className="text-sm font-bold text-foreground">Notification Channel Preferences</h3>
                    <div className="space-y-3 text-xs">
                        <div className="flex items-center justify-between p-3 rounded-xl border border-border bg-background">
                            <span>Email Digest Notifications</span>
                            <input type="checkbox" checked={emailAlerts} onChange={(e) => setEmailAlerts(e.target.checked)} className="h-4 w-4" />
                        </div>
                        <div className="flex items-center justify-between p-3 rounded-xl border border-border bg-background">
                            <span>Desktop Push Notifications</span>
                            <input type="checkbox" checked={desktopAlerts} onChange={(e) => setDesktopAlerts(e.target.checked)} className="h-4 w-4" />
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
