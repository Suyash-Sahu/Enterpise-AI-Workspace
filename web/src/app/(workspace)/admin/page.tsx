"use client";

import PageHeader from "@/components/shared/PageHeader";
import { useAdminTelemetry } from "@/hooks/useAdmin";
import { isApiErrorStatus } from "@/lib/api-client";
import { Activity, AlertTriangle, CheckCircle2, GitBranch, Route, ShieldAlert, Workflow, XCircle } from "lucide-react";

/**
 * Admin telemetry (Phase 20).
 *
 * Every number here is a live count aggregated by the backend from the
 * Execution / RoutingDecisionRecord / WorkflowPlan tables — there are no
 * illustrative or placeholder values on this page. If the request fails,
 * the page says so rather than rendering zeros, which would read as "no
 * activity" when it actually means "no data".
 *
 * Access is enforced server-side by require_role("admin"); this page only
 * renders the 403 it gets back.
 */
export default function AdminPage() {
    const { data, isLoading, error } = useAdminTelemetry();

    const forbidden = isApiErrorStatus(error, 403);

    const cards = data
        ? [
              { label: "Executions", value: data.total_executions, icon: Activity },
              { label: "Completed", value: data.completed_executions, icon: CheckCircle2 },
              { label: "Failed", value: data.failed_executions, icon: XCircle },
              { label: "Routing decisions", value: data.total_routing_decisions, icon: Route },
              { label: "Replanning events", value: data.total_replanning_events, icon: GitBranch },
              { label: "Workflow plans", value: data.total_workflow_plans, icon: Workflow },
          ]
        : [];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Admin telemetry"
                description="Live platform counts aggregated from the execution, routing, and workflow tables."
                breadcrumbs={[{ label: "Workspace" }, { label: "Admin" }]}
            />

            {forbidden && (
                <div className="flex items-start gap-3 rounded-2xl border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
                    <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                    <div>
                        <p className="font-medium">Admin role required</p>
                        <p className="text-destructive/80">
                            This page is restricted to accounts with the admin role. The restriction is
                            enforced by the API, not by this page.
                        </p>
                    </div>
                </div>
            )}

            {error && !forbidden && (
                <div className="flex items-start gap-3 rounded-2xl border border-warning/20 bg-warning/10 p-4 text-sm text-warning">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                    <div>
                        <p className="font-medium">Telemetry unavailable</p>
                        <p className="text-warning/80">{(error as Error).message}</p>
                    </div>
                </div>
            )}

            {isLoading && (
                <div className="rounded-2xl border border-border bg-surface p-6 text-xs text-muted-foreground animate-pulse">
                    Loading telemetry from backend API...
                </div>
            )}

            {data && (
                <>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        {cards.map(({ label, value, icon: Icon }) => (
                            <div key={label} className="rounded-2xl border border-border bg-surface p-5">
                                <div className="flex items-center gap-2 text-xs font-mono uppercase text-muted-foreground">
                                    <Icon className="h-3.5 w-3.5" aria-hidden />
                                    {label}
                                </div>
                                <p className="mt-3 text-3xl font-semibold tabular-nums text-foreground">
                                    {value.toLocaleString()}
                                </p>
                            </div>
                        ))}
                    </div>

                    <p className="text-xs text-muted-foreground">
                        Source: <span className="font-mono">{data.telemetry_source}</span> — counts are read
                        directly from the database at request time.
                    </p>
                </>
            )}
        </div>
    );
}
