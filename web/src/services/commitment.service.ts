import { apiClient } from "@/lib/api/client";
import { ENDPOINTS } from "@/lib/api/endpoints";
import {
    CommitmentDTO,
    CommitmentCreateInput,
    CommitmentUpdateInput,
    CommitmentVerificationInput,
    CommitmentRunDTO,
    CommitmentStatsDTO,
    CommitmentAnalyticsDTO,
    CommitmentEventDTO,
    FollowUpDraftDTO,
    CommitmentScanResultDTO,
    CommitmentSweepResultDTO,
} from "@/types/commitment";

export interface ListCommitmentsParams {
    status?: string;
    direction?: string;
    source_type?: string;
    priority?: string;
    search?: string;
    limit?: number;
    offset?: number;
}

export class CommitmentService {
    static async list(params?: ListCommitmentsParams): Promise<CommitmentDTO[]> {
        const queryParams: Record<string, string> = {};
        if (params?.status && params.status !== "all") queryParams.status_filter = params.status;
        if (params?.direction && params.direction !== "all") queryParams.direction = params.direction;
        if (params?.source_type && params.source_type !== "all") queryParams.source_type = params.source_type;
        if (params?.priority && params.priority !== "all") queryParams.priority = params.priority;
        if (params?.search) queryParams.search = params.search;
        if (params?.limit) queryParams.limit = String(params.limit);
        if (params?.offset) queryParams.offset = String(params.offset);

        return apiClient<CommitmentDTO[]>(ENDPOINTS.COMMITMENTS.LIST, {
            method: "GET",
            params: Object.keys(queryParams).length > 0 ? queryParams : undefined,
        });
    }

    static async get(id: string): Promise<CommitmentDTO> {
        return apiClient<CommitmentDTO>(ENDPOINTS.COMMITMENTS.GET(id), {
            method: "GET",
        });
    }

    static async create(data: CommitmentCreateInput): Promise<CommitmentDTO> {
        return apiClient<CommitmentDTO>(ENDPOINTS.COMMITMENTS.CREATE, {
            method: "POST",
            body: data,
        });
    }

    static async update(id: string, data: CommitmentUpdateInput): Promise<CommitmentDTO> {
        return apiClient<CommitmentDTO>(ENDPOINTS.COMMITMENTS.UPDATE(id), {
            method: "PATCH",
            body: data,
        });
    }

    static async complete(id: string): Promise<CommitmentDTO> {
        return apiClient<CommitmentDTO>(ENDPOINTS.COMMITMENTS.COMPLETE(id), {
            method: "POST",
        });
    }

    static async dismiss(id: string): Promise<CommitmentDTO> {
        return apiClient<CommitmentDTO>(ENDPOINTS.COMMITMENTS.DISMISS(id), {
            method: "POST",
        });
    }

    static async reopen(id: string): Promise<CommitmentDTO> {
        return apiClient<CommitmentDTO>(ENDPOINTS.COMMITMENTS.REOPEN(id), {
            method: "POST",
        });
    }

    static async verify(id: string, data?: CommitmentVerificationInput): Promise<CommitmentDTO> {
        return apiClient<CommitmentDTO>(ENDPOINTS.COMMITMENTS.VERIFY(id), {
            method: "POST",
            body: data || {},
        });
    }

    static async generateFollowUp(id: string): Promise<FollowUpDraftDTO> {
        return apiClient<FollowUpDraftDTO>(ENDPOINTS.COMMITMENTS.FOLLOW_UP(id), {
            method: "POST",
        });
    }

    static async proposeTask(id: string): Promise<{ proposal_id: string; status: string; message: string }> {
        return apiClient<{ proposal_id: string; status: string; message: string }>(
            ENDPOINTS.COMMITMENTS.PROPOSE_TASK(id),
            {
                method: "POST",
            }
        );
    }

    static async getEvents(id: string): Promise<CommitmentEventDTO[]> {
        return apiClient<CommitmentEventDTO[]>(ENDPOINTS.COMMITMENTS.EVENTS(id), {
            method: "GET",
        });
    }

    static async getStats(): Promise<CommitmentStatsDTO> {
        return apiClient<CommitmentStatsDTO>(ENDPOINTS.COMMITMENTS.STATS, {
            method: "GET",
        });
    }

    static async getAnalytics(): Promise<CommitmentAnalyticsDTO> {
        return apiClient<CommitmentAnalyticsDTO>(ENDPOINTS.COMMITMENTS.ANALYTICS, {
            method: "GET",
        });
    }

    static async startRun(run_type: "scan" | "sweep" = "scan", max_emails: number = 10): Promise<CommitmentRunDTO> {
        return apiClient<CommitmentRunDTO>(ENDPOINTS.COMMITMENTS.RUNS, {
            method: "POST",
            body: { run_type, max_emails },
        });
    }

    static async getActiveRun(): Promise<CommitmentRunDTO | null> {
        return apiClient<CommitmentRunDTO | null>(ENDPOINTS.COMMITMENTS.ACTIVE_RUN, {
            method: "GET",
        });
    }

    static async getRun(runId: string): Promise<CommitmentRunDTO> {
        return apiClient<CommitmentRunDTO>(ENDPOINTS.COMMITMENTS.RUN(runId), {
            method: "GET",
        });
    }

    static async cancelRun(runId: string): Promise<CommitmentRunDTO> {
        return apiClient<CommitmentRunDTO>(ENDPOINTS.COMMITMENTS.CANCEL_RUN(runId), {
            method: "POST",
        });
    }

    static async listRuns(limit: number = 20): Promise<CommitmentRunDTO[]> {
        return apiClient<CommitmentRunDTO[]>(ENDPOINTS.COMMITMENTS.RUNS, {
            method: "GET",
            params: { limit: String(limit) },
        });
    }

    // Legacy methods
    static async scan(): Promise<CommitmentScanResultDTO> {
        return apiClient<CommitmentScanResultDTO>(ENDPOINTS.COMMITMENTS.SCAN, {
            method: "POST",
        });
    }

    static async sweep(): Promise<CommitmentSweepResultDTO> {
        return apiClient<CommitmentSweepResultDTO>(ENDPOINTS.COMMITMENTS.SWEEP, {
            method: "POST",
        });
    }
}
