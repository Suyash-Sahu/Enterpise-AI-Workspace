"use client";

import Link from "next/link";
import {
    AlertTriangle,
    ArrowUpRight,
    CheckCircle2,
    Cpu,
    FileText,
    Mail,
    Plug,
    RefreshCw,
    UserCheck,
    XCircle,
} from "lucide-react";

import { useDashboard } from "@/hooks/useDashboard";
import { useHealth } from "@/hooks/useHealth";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import PageHeader from "@/components/shared/PageHeader";
import ConnectorErrorState from "@/components/shared/ConnectorErrorState";

export default function DashboardPage() {
    const {
        data: dashboard,
        isLoading,
        isError,
        error,
        refetch,
    } = useDashboard();
    const { data: health } = useHealth();

    if (isLoading) {
        return (
            <div className="space-y-6" aria-busy="true">
                <div className="h-9 w-48 animate-pulse rounded-sm bg-muted" />
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {[0, 1, 2, 3].map((i) => (
                        <div
                            key={i}
                            className="h-28 animate-pulse rounded-md border border-border bg-card"
                        />
                    ))}
                </div>
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                    <div className="h-64 animate-pulse rounded-md border border-border bg-card" />
                    <div className="h-64 animate-pulse rounded-md border border-border bg-card lg:col-span-2" />
                </div>
            </div>
        );
    }

    // On failure, show the error instead of placeholder values (a broken
    // request used to look like a working but empty workspace).
    if (isError) {
        return (
            <ConnectorErrorState
                error={error}
                resource="your workspace"
                onRetry={() => refetch()}
            />
        );
    }

    const user = dashboard?.user;
    const drive = dashboard?.drive;
    const gmail = dashboard?.gmail;
    const ai = dashboard?.ai;
    const workspace = dashboard?.workspace;
    const capabilities = dashboard?.capabilities ?? {};

    const isGoogleConnected = workspace?.connected === true;
    const unavailable = workspace?.unavailable ?? [];

    const healthRows = [
        { name: "Backend REST core", status: health?.backend },
        { name: "Database storage", status: health?.database },
        { name: "Google OAuth API", status: health?.google },
        { name: "Local Ollama LLM", status: health?.ollama },
        { name: "Cloud OpenRouter AI", status: health?.openrouter },
    ];

    return (
        <div className="space-y-6">
            <PageHeader
                title={`Welcome back${user?.name ? `, ${user.name}` : ""}`}
                description={
                    user?.email
                        ? `Signed in as ${user.email}${user.provider ? ` · ${user.provider}` : ""}`
                        : "Your workspace at a glance"
                }
                actions={
                    <Button variant="outline" size="sm" onClick={() => refetch()}>
                        <RefreshCw aria-hidden />
                        Refresh
                    </Button>
                }
            />

            {!isGoogleConnected && (
                <Card className="flex flex-col gap-3 border-primary/30 bg-primary/5 p-5 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-start gap-3">
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-primary/20 bg-primary/10 text-primary">
                            <Plug className="h-4 w-4" aria-hidden />
                        </span>
                        <div>
                            <h3 className="text-sm font-semibold text-foreground">
                                Connect your Google account
                            </h3>
                            <p className="mt-0.5 text-sm text-muted-foreground">
                                Gmail and Drive data appear here once you connect.
                            </p>
                        </div>
                    </div>
                    <Button size="sm" asChild>
                        <Link href="/integrations">Connect Google</Link>
                    </Button>
                </Card>
            )}

            {unavailable.length > 0 && (
                <div
                    role="alert"
                    className="flex items-start gap-2.5 rounded-md border border-warning/30 bg-warning/10 p-3 text-sm text-warning"
                >
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                    <span className="leading-relaxed">
                        Could not load {unavailable.join(" and ")} this time. The figures
                        below are incomplete rather than zero.
                    </span>
                </div>
            )}

            {/* Metrics */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard
                    label="Google account"
                    icon={<UserCheck className="h-5 w-5" />}
                    value={user?.email ?? "—"}
                    foot={
                        isGoogleConnected ? (
                            <span className="inline-flex items-center gap-1.5 text-xs text-success">
                                <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                                OAuth 2.0 synchronized
                            </span>
                        ) : (
                            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                                <XCircle className="h-3.5 w-3.5" aria-hidden />
                                Not connected
                            </span>
                        )
                    }
                />
                <StatCard
                    label="Google Drive"
                    icon={<FileText className="h-5 w-5" />}
                    value={isGoogleConnected ? `${drive?.count ?? 0} files` : "—"}
                    foot={
                        <span className="truncate text-xs text-muted-foreground">
                            {isGoogleConnected
                                ? `Recent: ${drive?.recent?.[0]?.name ?? "No files found"}`
                                : "Connect Google to see your Drive"}
                        </span>
                    }
                />
                <StatCard
                    label="Gmail"
                    icon={<Mail className="h-5 w-5" />}
                    value={isGoogleConnected ? `${gmail?.unread ?? 0} unread` : "—"}
                    foot={
                        <span className="truncate text-xs text-muted-foreground">
                            {isGoogleConnected
                                ? `${gmail?.count ?? 0} messages in mailbox`
                                : "Connect Google to see your mail"}
                        </span>
                    }
                />
                <StatCard
                    label="AI router"
                    icon={<Cpu className="h-5 w-5" />}
                    value={ai?.local_model || "Ollama"}
                    foot={
                        <span className="truncate text-xs text-muted-foreground">
                            Cloud: {ai?.cloud_model || "OpenRouter"}
                        </span>
                    }
                />
            </div>

            {/* Health + capabilities */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                <Card className="p-6">
                    <h3 className="text-sm font-semibold text-foreground">System health</h3>
                    <div className="mt-4 space-y-2">
                        {healthRows.map((item) => {
                            const online =
                                item.status === "online" || item.status === "connected";
                            return (
                                <div
                                    key={item.name}
                                    className="flex items-center justify-between rounded-sm border border-border bg-muted/40 px-3 py-2"
                                >
                                    <span className="text-sm text-foreground">{item.name}</span>
                                    <span
                                        className={`inline-flex items-center gap-1.5 text-xs font-medium capitalize ${
                                            online ? "text-success" : "text-destructive"
                                        }`}
                                    >
                                        {online ? (
                                            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                                        ) : (
                                            <XCircle className="h-3.5 w-3.5" aria-hidden />
                                        )}
                                        {item.status || "offline"}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </Card>

                <Card className="p-6 lg:col-span-2">
                    <h3 className="text-sm font-semibold text-foreground">
                        Workspace capabilities
                    </h3>
                    <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                        {Object.entries(capabilities).map(([key, enabled]) => (
                            <div
                                key={key}
                                className={`flex flex-col gap-2 rounded-sm border p-3 ${
                                    enabled
                                        ? "border-success/30 bg-success/5"
                                        : "border-border bg-muted/40 opacity-70"
                                }`}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <span className="truncate text-xs font-medium capitalize text-foreground">
                                        {key.replace(/_/g, " ")}
                                    </span>
                                    <Badge variant={enabled ? "success" : "secondary"}>
                                        {enabled ? "Active" : "Off"}
                                    </Badge>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    {enabled ? "Enabled and synchronized." : "Disabled in settings."}
                                </p>
                            </div>
                        ))}
                    </div>
                </Card>
            </div>

            {/* Recent lists */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <OverviewList
                    title="Recent Drive files"
                    href="/drive"
                    linkLabel="Open Drive"
                    items={(drive?.recent ?? []).map((f, i) => ({
                        key: String(i),
                        primary: f.name || `Drive file ${i + 1}`,
                        meta: "Synced",
                    }))}
                    emptyText="No recent Drive files."
                />
                <OverviewList
                    title="Latest Gmail"
                    href="/gmail"
                    linkLabel="Open Gmail"
                    items={(gmail?.latest ?? []).map((m, i) => ({
                        key: String(i),
                        primary: m.subject || "No subject",
                        secondary: m.snippet || m.from,
                        meta: "Gmail",
                    }))}
                    emptyText="No recent Gmail messages."
                />
            </div>
        </div>
    );
}

function StatCard({
    label,
    icon,
    value,
    foot,
}: {
    label: string;
    icon: React.ReactNode;
    value: string;
    foot: React.ReactNode;
}) {
    return (
        <Card className="gap-2 p-5">
            <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">{label}</span>
                <span className="flex h-8 w-8 items-center justify-center rounded-md bg-muted text-muted-foreground">
                    {icon}
                </span>
            </div>
            <div className="truncate text-lg font-semibold text-foreground">{value}</div>
            {foot}
        </Card>
    );
}

interface OverviewItem {
    key: string;
    primary: string;
    secondary?: string;
    meta?: string;
}

function OverviewList({
    title,
    href,
    linkLabel,
    items,
    emptyText,
}: {
    title: string;
    href: string;
    linkLabel: string;
    items: OverviewItem[];
    emptyText: string;
}) {
    return (
        <Card className="p-6">
            <div className="flex items-center justify-between border-b border-border pb-3">
                <h3 className="text-sm font-semibold text-foreground">{title}</h3>
                <Link
                    href={href}
                    className="inline-flex items-center gap-1 rounded-sm text-xs font-medium text-primary hover:underline"
                >
                    {linkLabel}
                    <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
                </Link>
            </div>
            <div className="mt-3 space-y-2">
                {items.length > 0 ? (
                    items.map((item) => (
                        <div
                            key={item.key}
                            className="flex items-center justify-between gap-3 rounded-sm border border-border bg-muted/40 px-3 py-2.5"
                        >
                            <div className="min-w-0">
                                <div className="truncate text-sm font-medium text-foreground">
                                    {item.primary}
                                </div>
                                {item.secondary && (
                                    <div className="truncate text-xs text-muted-foreground">
                                        {item.secondary}
                                    </div>
                                )}
                            </div>
                            {item.meta && (
                                <span className="shrink-0 text-xs text-muted-foreground">
                                    {item.meta}
                                </span>
                            )}
                        </div>
                    ))
                ) : (
                    <p className="py-2 text-sm text-muted-foreground">{emptyText}</p>
                )}
            </div>
        </Card>
    );
}
