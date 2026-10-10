import { apiClient } from "@/lib/api/client";
import { ENDPOINTS } from "@/lib/api/endpoints";
import { ApiResponse } from "@/types/common";
import { ApprovalRequestDTO } from "@/types/approval";

export interface CreateApprovalInput {
    action_type: string;
    title: string;
    payload: Record<string, unknown>;
    description?: string;
}

export class ApprovalService {
    static async getApprovals(): Promise<ApprovalRequestDTO[]> {
        const res = await apiClient<ApiResponse<ApprovalRequestDTO[]>>(
            ENDPOINTS.APPROVALS.LIST
        );
        return res.data;
    }

    /**
     * Create a pending approval for a side-effecting action.
     *
     * Side effects such as sending mail require an approved record; the backend
     * rejects the action without one.
     */
    static async create(input: CreateApprovalInput): Promise<{ id: number }> {
        return apiClient<{ id: number }>(ENDPOINTS.APPROVALS.CREATE, {
            method: "POST",
            body: input,
        });
    }

    static async approve(id: string): Promise<unknown> {
        const res = await apiClient<ApiResponse<unknown>>(
            ENDPOINTS.APPROVALS.APPROVE(id),
            { method: "POST" }
        );
        return res.data;
    }

    static async reject(id: string): Promise<unknown> {
        const res = await apiClient<ApiResponse<unknown>>(
            ENDPOINTS.APPROVALS.REJECT(id),
            { method: "POST" }
        );
        return res.data;
    }
}
