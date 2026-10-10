"use client";

import { ReactNode, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    BarChart3,
    Bell,
    Bot,
    Cpu,
    Database,
    FileText,
    HardDrive,
    LayoutDashboard,
    LogOut,
    Mail,
    Menu,
    MessageSquare,
    PanelLeft,
    PanelLeftClose,
    Search,
    Settings,
    Sparkles,
    SquareKanban,
    Video,
    Sunrise,
    Handshake,
    Zap,
    type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import ThemeToggle from "@/components/ui/ThemeToggle";
import Logo from "@/components/shared/Logo";
import CommandPalette from "@/components/shared/CommandPalette";
import NotificationDropdown from "@/components/notifications/NotificationDropdown";
import { NAV_GROUPS, type NavStatus } from "@/constants/navigation";
import { useNotificationStore } from "@/stores/notification.store";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
    LayoutDashboard,
    FileText,
    HardDrive,
    Mail,
    SquareKanban,
    Video,
    MessageSquare,
    Sparkles,
    Database,
    Cpu,
    Bot,
    BarChart3,
    Settings,
    Sunrise,
    Handshake,
    Zap,
};

const STATUS_LABEL: Record<NavStatus, string> = {
    live: "Live",
    soon: "Soon",
    beta: "Beta",
};

const STATUS_VARIANT: Record<NavStatus, "success" | "warning" | "secondary"> = {
    live: "success",
    soon: "warning",
    beta: "secondary",
};

function SidebarNav({
    collapsed,
    onNavigate,
}: {
    collapsed?: boolean;
    onNavigate?: () => void;
}) {
    const pathname = usePathname();

    return (
        <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
            {NAV_GROUPS.map((group) => (
                <div key={group.label}>
                    {!collapsed && (
                        <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                            {group.label}
                        </p>
                    )}
                    <ul className="space-y-0.5">
                        {group.items.map((item) => {
                            const Icon = ICONS[item.iconName] ?? LayoutDashboard;
                            const active =
                                pathname === item.href ||
                                pathname.startsWith(`${item.href}/`);

                            return (
                                <li key={item.href}>
                                    <Link
                                        href={item.href}
                                        onClick={onNavigate}
                                        title={collapsed ? item.name : undefined}
                                        aria-current={active ? "page" : undefined}
                                        className={cn(
                                            "group relative flex items-center gap-3 rounded-sm px-3 py-2 text-sm transition-colors",
                                            active
                                                ? "bg-accent font-medium text-foreground"
                                                : "text-muted-foreground hover:bg-accent hover:text-foreground",
                                            collapsed && "justify-center px-0"
                                        )}
                                    >
                                        {active && (
                                            <span
                                                aria-hidden
                                                className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary"
                                            />
                                        )}
                                        <Icon className="h-4 w-4 shrink-0" aria-hidden />
                                        {!collapsed && (
                                            <span className="flex-1 truncate">{item.name}</span>
                                        )}
                                        {!collapsed && item.status && (
                                            <Badge
                                                variant={STATUS_VARIANT[item.status]}
                                                className="shrink-0"
                                            >
                                                {STATUS_LABEL[item.status]}
                                            </Badge>
                                        )}
                                    </Link>
                                </li>
                            );
                        })}
                    </ul>
                </div>
            ))}
        </nav>
    );
}

function SidebarContents({
    collapsed = false,
    onNavigate,
}: {
    collapsed?: boolean;
    onNavigate?: () => void;
}) {
    const { user, logout } = useAuth();
    const initial = (user?.fullName ?? user?.email ?? "U").charAt(0).toUpperCase();

    return (
        <div className="flex h-full flex-col bg-surface">
            <div
                className={cn(
                    "flex h-16 items-center border-b border-border px-4",
                    collapsed && "justify-center px-0"
                )}
            >
                <Link
                    href="/dashboard"
                    onClick={onNavigate}
                    className="flex min-w-0 items-center rounded-sm"
                >
                    <Logo iconOnly={collapsed} />
                </Link>
            </div>

            <SidebarNav collapsed={collapsed} onNavigate={onNavigate} />

            <div className="border-t border-border p-3">
                <div
                    className={cn(
                        "flex items-center gap-2.5",
                        collapsed && "justify-center"
                    )}
                >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                        {initial}
                    </span>
                    {!collapsed && (
                        <>
                            <div className="min-w-0 flex-1">
                                <p className="truncate text-xs font-medium text-foreground">
                                    {user?.fullName ?? "Signed in"}
                                </p>
                                <p className="truncate text-[11px] text-muted-foreground">
                                    {user?.email ?? ""}
                                </p>
                            </div>
                            <Button
                                variant="ghost"
                                size="icon-sm"
                                aria-label="Sign out"
                                onClick={logout}
                            >
                                <LogOut aria-hidden />
                            </Button>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

export default function AppShellLayout({ children }: { children: ReactNode }) {
    const { unreadCount } = useNotificationStore();
    const [collapsed, setCollapsed] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);
    const [notifOpen, setNotifOpen] = useState(false);

    return (
        <div className="flex min-h-screen bg-background text-foreground">
            <CommandPalette />

            {/* Docked sidebar — lg and up */}
            <aside
                className={cn(
                    "sticky top-0 z-30 hidden h-screen shrink-0 border-r border-border lg:block",
                    collapsed ? "w-16" : "w-64"
                )}
            >
                <SidebarContents collapsed={collapsed} />
            </aside>

            {/* Drawer — below lg */}
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
                <SheetContent side="left" className="w-72 p-0 sm:max-w-72">
                    <SheetTitle className="sr-only">Navigation</SheetTitle>
                    <SidebarContents onNavigate={() => setMobileOpen(false)} />
                </SheetContent>
            </Sheet>

            <div className="flex min-w-0 flex-1 flex-col">
                <header className="sticky top-0 z-20 flex h-16 items-center gap-2 border-b border-border bg-surface/80 px-4 backdrop-blur-md">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="lg:hidden"
                        aria-label="Open navigation"
                        onClick={() => setMobileOpen(true)}
                    >
                        <Menu aria-hidden />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="hidden lg:inline-flex"
                        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                        aria-pressed={collapsed}
                        onClick={() => setCollapsed((v) => !v)}
                    >
                        {collapsed ? <PanelLeft aria-hidden /> : <PanelLeftClose aria-hidden />}
                    </Button>

                    <button
                        type="button"
                        onClick={() =>
                            window.dispatchEvent(new CustomEvent("commandpalette:toggle"))
                        }
                        className="flex h-9 max-w-md flex-1 items-center gap-2 rounded-sm border border-input bg-background px-3 text-sm text-muted-foreground transition-colors hover:border-ring/50 hover:text-foreground"
                    >
                        <Search className="h-4 w-4 shrink-0" aria-hidden />
                        <span className="truncate">Search or run a command</span>
                        <kbd className="ml-auto hidden items-center gap-0.5 rounded-sm border border-border px-1.5 text-[11px] font-medium sm:inline-flex">
                            <span className="text-xs">⌘</span>K
                        </kbd>
                    </button>

                    <div className="ml-auto flex items-center gap-1.5">
                        <ThemeToggle />
                        <div className="relative">
                            <Button
                                variant="outline"
                                size="icon"
                                aria-label={
                                    unreadCount > 0
                                        ? `Notifications, ${unreadCount} unread`
                                        : "Notifications"
                                }
                                onClick={() => setNotifOpen((v) => !v)}
                            >
                                <Bell aria-hidden />
                                {unreadCount > 0 && (
                                    <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-foreground">
                                        {unreadCount > 9 ? "9+" : unreadCount}
                                    </span>
                                )}
                            </Button>
                            <NotificationDropdown
                                isOpen={notifOpen}
                                onClose={() => setNotifOpen(false)}
                            />
                        </div>
                    </div>
                </header>

                <main className="flex-1 overflow-x-hidden">
                    <div className="mx-auto w-full max-w-[1400px] p-4 sm:p-6 lg:p-8">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
}
