"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import PageHeader from "@/components/shared/PageHeader";
import SearchInput from "@/components/shared/SearchInput";
import { StatusBadge } from "@/components/shared/BadgeVariants";
import { googleService } from "@/services/google.service";
import {
    Puzzle,
    Globe,
    Code2,
    MessageCircle,
    Database,
    Cpu,
    CheckCircle2,
    Shield,
    Key,
    Webhook,
    Activity,
    AlertTriangle,
    Loader2,
} from "lucide-react";

/**
 * The Google card on this page used to be an entry in a hardcoded array whose
 * "Connect Account" button flipped a local useState flag. It never called the
 * connector, so there was no way to connect a Google account from anywhere in
 * the app — while the card claimed "Connected" regardless. It is now driven by
 * the backend's real connection status and starts the real OAuth flow.
 */

/** Reasons the OAuth callback can redirect back with. */
const CALLBACK_ERRORS: Record<string, string> = {
    missing_parameters: "Google did not return an authorization code. Try again.",
    invalid_state:
        "This connection link has expired or was already used. Start the connection again.",
    token_exchange_failed:
        "Google rejected the authorization code. Check that the redirect URI registered in Google Cloud matches this server, then try again.",
    userinfo_failed:
        "Connected, but Google would not return the account address. Try again.",
};

/**
 * Integrations that are not implemented. They are listed because the roadmap
 * is useful, but they are labelled as unavailable rather than shown with a
 * Connected badge and a button that only toggles a local flag.
 */
const PLANNED_CONNECTORS = [
    {
        id: "github",
        name: "GitHub Enterprise",
        category: "Development",
        icon: Code2,
        color: "text-primary",
        desc: "Repository commits, PR reviews, and issue tracking.",
    },
    {
        id: "slack",
        name: "Slack Workspace",
        category: "Communication",
        icon: MessageCircle,
        color: "text-success",
        desc: "Channel messages, alerts, and AI notification digest.",
    },
    {
        id: "jira",
        name: "Jira Software",
        category: "Project Management",
        icon: Puzzle,
        color: "text-info",
        desc: "Bi-directional issue sync and sprint velocity metrics.",
    },
    {
        id: "snowflake",
        name: "Snowflake Data Cloud",
        category: "Databases",
        icon: Database,
        color: "text-primary",
        desc: "Enterprise warehouse SQL queries and AMOF Database Agent.",
    },
    {
        id: "openai",
        name: "OpenAI API",
        category: "AI Models",
        icon: Cpu,
        color: "text-success",
        desc: "LLM synthesis and multi-agent prompt orchestration.",
    },
];

export default function IntegrationsPage() {
    // useSearchParams needs a Suspense boundary to keep this page
    // prerenderable.
    return (
        <Suspense fallback={null}>
            <IntegrationsPageContent />
        </Suspense>
    );
}

function IntegrationsPageContent() {
    const [search, setSearch] = useState("");
    const [activeTab, setActiveTab] = useState<
        "marketplace" | "connected" | "logs" | "apikeys" | "webhooks"
    >("marketplace");
    const [connecting, setConnecting] = useState(false);
    const [connectError, setConnectError] = useState<string | null>(null);

    const queryClient = useQueryClient();
    const searchParams = useSearchParams();

    // Derived during render rather than pushed into state from an effect,
    // which would cost a second render pass on every page load.
    const callbackNotice = useMemo<{
        kind: "success" | "error";
        message: string;
    } | null>(() => {
        const connected = searchParams.get("connected");

        if (!connected) return null;

        if (connected === "true") {
            return { kind: "success", message: "Google account connected." };
        }

        const reason = searchParams.get("error") ?? "";
        return {
            kind: "error",
            message:
                CALLBACK_ERRORS[reason] ??
                "Could not connect the Google account. Try again.",
        };
    }, [searchParams]);

    const {
        data: googleStatus,
        isLoading: statusLoading,
        isError: statusFailed,
        error: statusError,
    } = useQuery({
        queryKey: ["google-status"],
        queryFn: () => googleService.getGoogleStatus(),
    });

    // Act on the callback result: refresh the cached status, then strip the
    // query string so a reload does not replay the banner. history.replaceState
    // is used rather than router.replace so the banner stays on screen.
    useEffect(() => {
        if (!callbackNotice) return;

        if (callbackNotice.kind === "success") {
            queryClient.invalidateQueries({ queryKey: ["google-status"] });
            queryClient.invalidateQueries({ queryKey: ["workspace-dashboard"] });
        }

        window.history.replaceState({}, "", window.location.pathname);
    }, [callbackNotice, queryClient]);

    const startConnect = async () => {
        setConnectError(null);
        setConnecting(true);
        try {
            // Navigates to Google on success, so this promise normally does
            // not resolve back into this component.
            await googleService.startGoogleConnect();
        } catch (err) {
            // The backend's own reason, not a guess about which of several
            // things went wrong.
            setConnectError(
                err instanceof Error && err.message
                    ? err.message
                    : "Could not start the Google connection."
            );
            setConnecting(false);
        }
    };

    const isConnected = googleStatus?.connected === true;

    // Three states, not two. Failing to reach the status endpoint is not the
    // same as being told the account is disconnected, and rendering the second
    // for the first states a fact the page never learned.
    const statusLabel = statusFailed
        ? "Error"
        : isConnected
          ? "Connected"
          : "Disconnected";

    const planned = PLANNED_CONNECTORS.filter((c) =>
        c.name.toLowerCase().includes(search.toLowerCase())
    );
    const googleMatches = "google workspace".includes(search.toLowerCase());

    return (
        <div className="space-y-6">
            <PageHeader
                title="Integration Center & Connectors"
                description="Manage connected enterprise accounts, OAuth permissions, API keys, and webhooks."
                breadcrumbs={[{ label: "Workspace" }, { label: "Integrations" }]}
            />

            {callbackNotice && (
                <div
                    className={`flex items-start gap-2.5 rounded-xl border p-3.5 text-xs ${
                        callbackNotice.kind === "success"
                            ? "border-success/30 bg-success/10 text-success dark:text-success"
                            : "border-destructive/30 bg-destructive/10 text-destructive dark:text-destructive"
                    }`}
                >
                    {callbackNotice.kind === "success" ? (
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                    ) : (
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    )}
                    <span className="font-medium leading-relaxed">
                        {callbackNotice.message}
                    </span>
                </div>
            )}

            {/* View Tabs */}
            <div className="flex items-center gap-1.5 overflow-x-auto border-b border-border pb-3">
                {[
                    { id: "marketplace", label: "App Marketplace", icon: Puzzle },
                    {
                        id: "connected",
                        label: `Connected Apps (${isConnected ? 1 : 0})`,
                        icon: CheckCircle2,
                    },
                    { id: "logs", label: "Access Logs", icon: Activity },
                    { id: "apikeys", label: "API Keys", icon: Key },
                    { id: "webhooks", label: "Webhooks", icon: Webhook },
                ].map((t) => {
                    const Icon = t.icon;
                    const isSelected = activeTab === t.id;
                    return (
                        <button
                            key={t.id}
                            onClick={() => setActiveTab(t.id as typeof activeTab)}
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

            {/* Marketplace Tab */}
            {activeTab === "marketplace" && (
                <div className="space-y-4">
                    <SearchInput
                        value={search}
                        onChange={setSearch}
                        placeholder="Search integrations..."
                        className="max-w-md"
                    />

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        {/* The one real connector. */}
                        {googleMatches && (
                            <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4">
                                <div className="flex items-start justify-between">
                                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-muted border border-border text-destructive">
                                        <Globe className="h-6 w-6" />
                                    </div>
                                    {statusLoading ? (
                                        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                                    ) : (
                                        <StatusBadge status={statusLabel} />
                                    )}
                                </div>

                                <div className="space-y-1">
                                    <h4 className="text-sm font-bold text-foreground">
                                        Google Workspace
                                    </h4>
                                    <span className="font-mono text-xs text-muted-foreground">
                                        Productivity &amp; Communication
                                    </span>
                                    <p className="text-xs text-muted-foreground leading-relaxed pt-1">
                                        {statusFailed
                                            ? "Could not check whether an account is connected."
                                            : isConnected
                                              ? "Gmail and Drive access is active for this workspace account."
                                              : "Not connected yet. Connect an account to read Gmail and Drive."}
                                    </p>
                                    {statusFailed && (
                                        <p className="pt-1 text-xs leading-relaxed text-destructive">
                                            {statusError instanceof Error
                                                ? statusError.message
                                                : "The workspace API could not be reached."}
                                        </p>
                                    )}
                                    {isConnected && googleStatus?.email && (
                                        <p className="pt-1 font-mono text-xs text-foreground">
                                            {googleStatus.email}
                                        </p>
                                    )}
                                </div>

                                {connectError && (
                                    <p className="text-xs leading-relaxed text-destructive">
                                        {connectError}
                                    </p>
                                )}

                                <div className="pt-2 border-t border-border flex items-center justify-between gap-2">
                                    <span className="font-mono text-xs text-muted-foreground">
                                        OAuth 2.0 + PKCE
                                    </span>
                                    <button
                                        onClick={startConnect}
                                        disabled={connecting}
                                        className="flex items-center gap-1.5 rounded-xl bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground shadow-sm transition-all disabled:opacity-60 disabled:hover:scale-100"
                                    >
                                        {connecting && <Loader2 className="h-3 w-3 animate-spin" />}
                                        {isConnected ? "Reconnect" : "Connect Account"}
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Not built yet — labelled as such rather than faked. */}
                        {planned.map((conn) => {
                            const Icon = conn.icon;
                            return (
                                <div
                                    key={conn.id}
                                    className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4 opacity-70"
                                >
                                    <div className="flex items-start justify-between">
                                        <div
                                            className={`flex h-11 w-11 items-center justify-center rounded-xl bg-muted border border-border ${conn.color}`}
                                        >
                                            <Icon className="h-6 w-6" />
                                        </div>
                                        <span className="rounded-lg border border-border bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground">
                                            Not available
                                        </span>
                                    </div>

                                    <div className="space-y-1">
                                        <h4 className="text-sm font-bold text-foreground">
                                            {conn.name}
                                        </h4>
                                        <span className="font-mono text-xs text-muted-foreground">
                                            {conn.category}
                                        </span>
                                        <p className="text-xs text-muted-foreground leading-relaxed pt-1">
                                            {conn.desc}
                                        </p>
                                    </div>

                                    <div className="pt-2 border-t border-border">
                                        <span className="font-mono text-xs text-muted-foreground">
                                            No connector implemented
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Connected Tab */}
            {activeTab === "connected" && (
                <div className="rounded-2xl border border-border bg-surface p-6 max-w-xl space-y-3">
                    <h3 className="text-sm font-bold text-foreground">Connected Accounts</h3>
                    {statusLoading ? (
                        <p className="text-xs text-muted-foreground">Checking…</p>
                    ) : statusFailed ? (
                        <p className="text-xs leading-relaxed text-destructive">
                            {statusError instanceof Error
                                ? statusError.message
                                : "Could not check connected accounts."}
                        </p>
                    ) : isConnected ? (
                        <div className="flex items-center gap-2.5">
                            <Shield className="h-4 w-4 text-success" />
                            <div>
                                <p className="text-xs font-semibold text-foreground">
                                    Google Workspace
                                </p>
                                <p className="font-mono text-xs text-muted-foreground">
                                    {googleStatus?.email ?? "connected"}
                                </p>
                            </div>
                        </div>
                    ) : (
                        <p className="text-xs text-muted-foreground">
                            No accounts connected yet. Connect Google Workspace from the App
                            Marketplace tab.
                        </p>
                    )}
                </div>
            )}

            {/* API Keys Tab */}
            {activeTab === "apikeys" && (
                <div className="rounded-2xl border border-border bg-surface p-6 max-w-xl space-y-2">
                    <h3 className="text-sm font-bold text-foreground">
                        API Keys &amp; Secret Manager
                    </h3>
                    {/* This tab used to display a hardcoded string styled as a live
                        production key. There is no key-issuing endpoint behind it. */}
                    <p className="text-xs text-muted-foreground leading-relaxed">
                        Workspace API key issuing is not implemented. The backend
                        authenticates callers with short-lived access tokens issued at
                        sign-in, not with long-lived API keys.
                    </p>
                </div>
            )}

            {/* Access Logs / Webhooks */}
            {(activeTab === "logs" || activeTab === "webhooks") && (
                <div className="rounded-2xl border border-border bg-surface p-6 max-w-xl">
                    <p className="text-xs text-muted-foreground leading-relaxed">
                        {activeTab === "logs"
                            ? "Per-connector access logs are not implemented. Backend audit events are recorded server-side."
                            : "Outbound webhooks are not implemented."}
                    </p>
                </div>
            )}
        </div>
    );
}
