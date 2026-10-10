"use client";

import { useState } from "react";
import { AlertTriangle, Loader2, LogIn, Plug } from "lucide-react";

import { describeConnectorError } from "@/lib/connector-state";
import { googleService } from "@/services/google.service";
import { Button } from "@/components/ui/button";

/**
 * What the Gmail, Drive and dashboard screens show when a connector call fails.
 *
 * The state mapping lives in describeConnectorError, where every status is
 * asserted directly. "Connect Account" starts the real OAuth flow here rather
 * than linking to another page.
 */
export function ConnectorErrorState({
    error,
    resource,
    onRetry,
}: {
    error: unknown;
    resource: string;
    onRetry?: () => void;
}) {
    const state = describeConnectorError(error, resource);

    const [connecting, setConnecting] = useState(false);
    const [connectError, setConnectError] = useState<string | null>(null);

    const startConnect = async () => {
        setConnectError(null);
        setConnecting(true);
        try {
            // Navigates to Google on success, so this normally does not
            // resolve back into this component.
            await googleService.startGoogleConnect();
        } catch (err) {
            setConnectError(
                err instanceof Error
                    ? err.message
                    : "Could not start the Google connection."
            );
            setConnecting(false);
        }
    };

    const isPrompt = state.kind === "not-connected";
    const Icon = isPrompt ? Plug : state.kind === "signed-out" ? LogIn : AlertTriangle;

    return (
        <div
            role={isPrompt ? undefined : "alert"}
            className="space-y-4 rounded-md border border-border bg-card p-8 text-center"
        >
            <div
                className={`mx-auto flex h-11 w-11 items-center justify-center rounded-md border ${
                    isPrompt
                        ? "border-primary/20 bg-primary/10 text-primary"
                        : "border-destructive/20 bg-destructive/10 text-destructive"
                }`}
            >
                <Icon className="h-5 w-5" aria-hidden />
            </div>

            <div className="space-y-1">
                <h3 className="text-sm font-semibold text-foreground">{state.title}</h3>
                <p className="mx-auto max-w-md text-sm leading-relaxed text-muted-foreground">
                    {state.body}
                </p>
            </div>

            {connectError && (
                <p className="mx-auto max-w-md text-xs leading-relaxed text-destructive">
                    {connectError}
                </p>
            )}

            <div className="flex flex-wrap items-center justify-center gap-2">
                {state.canConnect && (
                    <Button size="sm" onClick={startConnect} disabled={connecting}>
                        {connecting && <Loader2 className="animate-spin" aria-hidden />}
                        {isPrompt ? "Connect account" : "Reconnect Google"}
                    </Button>
                )}

                {state.canRetry && onRetry && (
                    <Button size="sm" variant="outline" onClick={onRetry}>
                        Try again
                    </Button>
                )}
            </div>
        </div>
    );
}

export default ConnectorErrorState;
