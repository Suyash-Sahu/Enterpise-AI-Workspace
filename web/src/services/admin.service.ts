import { apiClient } from "@/lib/api-client";

/**
 * Admin endpoints (backend app/api/admin.py).
 *
 * Both routes are gated by require_role("admin") server-side, so a
 * non-admin session gets a 403 here — this client does no gating of its
 * own and must not be mistaken for the access control.
 *
 * These two endpoints return bare JSON, not the {success, data} envelope
 * the rest of the API uses, so there is no `.data.data` unwrapping here.
 */
export interface AdminTelemetry {
    telemetry_source: string;
    total_executions: number;
    completed_executions: number;
    failed_executions: number;
    total_routing_decisions: number;
    total_replanning_events: number;
    total_workflow_plans: number;
}

export interface AdminDashboard {
    message: string;
}

export const adminService = {
    async getTelemetry(): Promise<AdminTelemetry> {
        const res = await apiClient.get<AdminTelemetry>("/admin/telemetry");
        return res.data;
    },

    async getDashboard(): Promise<AdminDashboard> {
        const res = await apiClient.get<AdminDashboard>("/admin/dashboard");
        return res.data;
    },
};
