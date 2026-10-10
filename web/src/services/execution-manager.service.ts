import { apiClient, ApiResponse } from "@/lib/api-client";

export type ExecutionStatus =
    | "CREATED"
    | "VALIDATING"
    | "QUEUED"
    | "RUNNING"
    | "COMPLETED"
    | "FAILED"
    | "TIMEOUT"
    | "CANCELLED";

export interface ExecutionResponseData {
    execution_id: string;
    status: ExecutionStatus;
    task_type: string;
    result?: Record<string, any> | null;
    provider?: string | null;
    model?: string | null;
    execution_time: number;
    retry_count: number;
    idempotency_key?: string | null;
    request_id?: string | null;
    error_type?: string | null;
    error_message?: string | null;
}

export interface ExecutionStatusData {
    execution_id: string;
    status: ExecutionStatus;
    task_type: string;
    execution_mode: string;
    created_at: string;
    started_at?: string | null;
    completed_at?: string | null;
    execution_time: number;
    retry_count: number;
    error_message?: string | null;
}

export interface ExecutionHistoryData {
    total: number;
    items: ExecutionResponseData[];
}

export interface ExecutionHealthData {
    status: string;
    execution_manager_enabled: boolean;
    supported_tasks: string[];
    default_timeout_seconds: number;
    max_timeout_seconds: number;
    max_retries: number;
    history_limit: number;
}

export const executionManagerService = {
    async executeTask(params: {
        task_type: string;
        input: Record<string, any>;
        execution_mode?: string;
        idempotency_key?: string;
        request_id?: string;
        timeout?: number;
    }): Promise<ExecutionResponseData> {
        const response = await apiClient.post<ApiResponse<ExecutionResponseData>>(
            "/execution-manager/execute",
            params
        );
        return response.data.data;
    },

    async getStatus(executionId: string): Promise<ExecutionStatusData> {
        const response = await apiClient.get<ApiResponse<ExecutionStatusData>>(
            `/execution-manager/status/${executionId}`
        );
        return response.data.data;
    },

    async getHistory(limit: number = 50): Promise<ExecutionHistoryData> {
        const response = await apiClient.get<ApiResponse<ExecutionHistoryData>>(
            `/execution-manager/history?limit=${limit}`
        );
        return response.data.data;
    },

    async cancelExecution(executionId: string): Promise<ExecutionStatusData> {
        const response = await apiClient.post<ApiResponse<ExecutionStatusData>>(
            `/execution-manager/cancel/${executionId}`
        );
        return response.data.data;
    },

    async getHealth(): Promise<ExecutionHealthData> {
        const response = await apiClient.get<ApiResponse<ExecutionHealthData>>(
            "/execution-manager/health"
        );
        return response.data.data;
    },
};
