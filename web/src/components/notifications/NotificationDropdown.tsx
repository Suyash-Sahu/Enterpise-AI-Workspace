"use client";

import { useNotificationStore } from "@/stores/notification.store";
import { Bell, CheckCheck, ExternalLink, X } from "lucide-react";
import Link from "next/link";
import { PriorityBadge } from "@/components/shared/BadgeVariants";

interface Props {
    isOpen: boolean;
    onClose: () => void;
}

export default function NotificationDropdown({ isOpen, onClose }: Props) {
    const { notifications, unreadCount, markAsRead, markAllAsRead } = useNotificationStore();

    if (!isOpen) return null;

    return (
        <div className="absolute right-0 top-12 z-50 w-80 sm:w-96 overflow-hidden rounded-2xl border border-border bg-surface p-4 shadow-md space-y-3 animate-in fade-in">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2">
                    <Bell className="h-4 w-4 text-primary" />
                    <h3 className="text-xs font-bold text-foreground">Notifications</h3>
                    {unreadCount > 0 && (
                        <span className="rounded-full bg-destructive/10 px-2 py-0.5 font-mono text-[10px] font-bold text-destructive border border-destructive/20">
                            {unreadCount} unread
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={markAllAsRead}
                        className="flex items-center gap-1 text-xs font-mono font-bold text-success hover:underline"
                    >
                        <CheckCheck className="h-3 w-3" />
                        <span>Read All</span>
                    </button>
                    <button onClick={onClose} className="rounded-lg p-1 text-muted-foreground hover:bg-muted">
                        <X className="h-3.5 w-3.5" />
                    </button>
                </div>
            </div>

            {/* List */}
            <div className="max-h-80 overflow-y-auto space-y-2">
                {notifications.length > 0 ? (
                    notifications.slice(0, 5).map((n) => (
                        <div
                            key={n.id}
                            onClick={() => markAsRead(n.id)}
                            className={`rounded-xl border p-2.5 text-xs transition-all cursor-pointer ${
                                n.read ? "border-border bg-background/50 opacity-70" : "border-primary/30 bg-primary/5 shadow-sm"
                            }`}
                        >
                            <div className="flex items-start justify-between gap-2">
                                <h4 className="font-bold text-foreground truncate">{n.title}</h4>
                                <PriorityBadge priority={n.priority} />
                            </div>
                            <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">{n.description}</p>
                            <span className="font-mono text-[10px] text-muted-foreground mt-1 block">{n.createdAt}</span>
                        </div>
                    ))
                ) : (
                    <p className="text-center text-xs text-muted-foreground py-4">No notifications.</p>
                )}
            </div>

            {/* Footer */}
            <div className="pt-2 border-t border-border text-center">
                <Link
                    href="/notifications"
                    onClick={onClose}
                    className="flex items-center justify-center gap-1.5 text-xs font-bold text-primary hover:underline"
                >
                    <span>View All Notifications & History</span>
                    <ExternalLink className="h-3 w-3" />
                </Link>
            </div>
        </div>
    );
}
