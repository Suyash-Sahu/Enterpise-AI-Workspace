import { apiClient, ApiResponse } from "@/lib/api-client";

export interface EvaluationHealthData {
    status: string;
    module: string;
    dataset_configured: boolean;
    dataset_version: string;
    dataset_hash?: string;
    total_tasks_in_dataset: number;
    total_evaluation_runs: number;
}

export interface MetricSummaryData {
    metric_name: string;
    metric_value: number;
    numerator?: number;
    denominator?: number;
    metadata?: Record<string, any>;
}

export interface BaselineMetricsData {
    baseline_name: string;
    routing_accuracy: number;
    completion_rate: number;
    avg_latency_ms: number;
    p95_latency_ms: number;
    total_cost: number;
    total_tokens: number;
    privacy_leak_rate: number;
}

export interface AblationMetricsData {
    configuration_name: string;
    enabled_components: string[];
    disabled_components: string[];
    routing_accuracy: number;
    completion_rate: number;
    avg_latency_ms: number;
    p95_latency_ms: number;
    total_cost: number;
    total_tokens: number;
    cache_hit_rate: number;
    // Added Phase 14, mirrors AblationConfigMetricsSchema.
    privacy_leak_rate: number;
    verification_pass_rate: number;
}

export interface EvaluationRunData {
    run_id: string;
    status: string;
    dataset_version: string;
    dataset_hash: string;
    started_at?: string;
    completed_at?: string;
    task_count: number;
    completed_count: number;
    failed_count: number;
    git_commit?: string;
    created_at: string;
    configuration_json?: Record<string, any>;
    metrics?: MetricSummaryData[];
    baselines?: BaselineMetricsData[];
    ablations?: AblationMetricsData[];
}

export interface EvaluationResultItemData {
    task_id: string;
    task_text: string;
    category: string;
    complexity: string;
    privacy_level: string;
    expected_capability: string;
    expected_execution_mode: string;
    actual_capability?: string;
    actual_execution_mode?: string;
    actual_model?: string;
    routing_correct?: boolean;
    approval_required: boolean;
    approval_status?: string;
    cache_hit: boolean;
    verification_status?: string;
    latency_ms?: number;
    input_tokens?: number;
    output_tokens?: number;
    total_tokens?: number;
    estimated_cost?: number;
    completion_success: boolean;
    error_type?: string;
    error_message?: string;
}

export class EvaluationService {
    async getHealth(): Promise<EvaluationHealthData> {
        const res = await apiClient.get<ApiResponse<EvaluationHealthData>>("/evaluation/health", {
        });
        return res.data.data;
    }

    async startRun(params: {
        dataset_version?: string;
        run_baselines?: boolean;
        run_ablations?: boolean;
    }): Promise<EvaluationRunData> {
        const res = await apiClient.post<ApiResponse<EvaluationRunData>>(
            "/evaluation/runs",
            {
                dataset_version: params.dataset_version || "amof_eval_v1",
                run_baselines: params.run_baselines ?? true,
                run_ablations: params.run_ablations ?? true,
            },
            {
            }
        );
        return res.data.data;
    }

    async listRuns(): Promise<EvaluationRunData[]> {
        const res = await apiClient.get<ApiResponse<EvaluationRunData[]>>("/evaluation/runs", {
        });
        return res.data.data;
    }

    async getRunDetails(runId: string): Promise<EvaluationRunData> {
        const res = await apiClient.get<ApiResponse<EvaluationRunData>>(`/evaluation/runs/${runId}`, {
        });
        return res.data.data;
    }

    async getRunResults(runId: string): Promise<EvaluationResultItemData[]> {
        const res = await apiClient.get<ApiResponse<EvaluationResultItemData[]>>(`/evaluation/runs/${runId}/results`, {
        });
        return res.data.data;
    }

    async getRunBaselines(runId: string): Promise<BaselineMetricsData[]> {
        const res = await apiClient.get<ApiResponse<BaselineMetricsData[]>>(`/evaluation/runs/${runId}/comparison`, {
        });
        return res.data.data;
    }

    async getRunAblations(runId: string): Promise<AblationMetricsData[]> {
        const res = await apiClient.get<ApiResponse<AblationMetricsData[]>>(`/evaluation/runs/${runId}/ablation`, {
        });
        return res.data.data;
    }

    async downloadCsv(runId: string): Promise<void> {
        const res = await apiClient.get(`/evaluation/runs/${runId}/export/csv`, {
            responseType: "blob",
        });
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `evaluation_results_${runId}.csv`);
        document.body.appendChild(link);
        link.click();
        link.remove();
    }

    async downloadJson(runId: string): Promise<void> {
        const res = await apiClient.get(`/evaluation/runs/${runId}/export/json`, {
            responseType: "blob",
        });
        const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/json" }));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `evaluation_artifact_${runId}.json`);
        document.body.appendChild(link);
        link.click();
        link.remove();
    }
}

export const evaluationService = new EvaluationService();
