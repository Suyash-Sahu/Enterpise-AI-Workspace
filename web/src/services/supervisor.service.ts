import { apiClient, ApiResponse } from "@/lib/api-client";

export interface IntentResultData {
    capability: "rag_search" | "rag_answer" | "database_query" | "text_generation" | "document_summary";
    confidence: number;
    reason: string;
}

export interface PlanStepData {
    step_id: string;
    capability: string;
    purpose: "capability" | "intent_classification" | "synthesis";
    depends_on: string[];
    input_template: Record<string, any>;
    status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "TIMEOUT" | "CANCELLED";
    execution_id?: string;
    result?: Record<string, any>;
    execution_time: number;
}

export interface SupervisorPlanData {
    plan_id: string;
    request_id: string;
    steps: PlanStepData[];
    max_steps: number;
}

export interface SupervisorResultData {
    request_id: string;
    trace_id: string;
    status: "COMPLETED" | "FAILED" | "TIMEOUT" | "CLARIFICATION_REQUIRED" | "REJECTED";
    intent: IntentResultData;
    answer: string;
    sources: Record<string, any>[];
    execution_ids: string[];
    steps: PlanStepData[];
    execution_time: number;
}

export interface SupervisorHealthData {
    status: string;
    supervisor_enabled: boolean;
    p5_available: boolean;
    supported_capabilities: string[];
    max_steps: number;
    max_timeout_seconds: number;
}

export class SupervisorService {
    async getHealth(): Promise<SupervisorHealthData> {
        const res = await apiClient.get<ApiResponse<SupervisorHealthData>>("/supervisor/health");
        return res.data.data;
    }

    async executeSupervisor(params: {
        question: string;
        execution_mode?: string;
        timeout?: number;
        conversation_id?: string;
    }): Promise<SupervisorResultData> {
        const res = await apiClient.post<ApiResponse<SupervisorResultData>>("/supervisor/execute", params);
        return res.data.data;
    }

    async classifyIntent(params: {
        question: string;
        execution_mode?: string;
    }): Promise<IntentResultData> {
        const res = await apiClient.post<ApiResponse<IntentResultData>>("/supervisor/classify", params);
        return res.data.data;
    }

    async createPlan(params: {
        question: string;
        execution_mode?: string;
    }): Promise<SupervisorPlanData> {
        const res = await apiClient.post<ApiResponse<SupervisorPlanData>>("/supervisor/plan", params);
        return res.data.data;
    }
}

export const supervisorService = new SupervisorService();
