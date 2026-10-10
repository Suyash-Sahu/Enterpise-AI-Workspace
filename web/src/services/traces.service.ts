import { apiClient, ApiResponse } from "@/lib/api-client";

export interface StepTrace {
  step_id: string;
  capability: string;
  depends_on: string[];
  status: string;
  execution_id?: string;
  replanning_of?: string;
  execution_time: number;
  created_at?: string;
}

export interface PlanTrace {
  plan_id: string;
  request_id: string;
  owner_id: string;
  status: string;
  max_steps: number;
  steps: StepTrace[];
  created_at?: string;
}

export interface RoutingDecisionTrace {
  id: string;
  workflow_step_id: string;
  placement: string;
  model: string;
  privacy_label: string;
  classification_confidence: number;
  predicted_quality: number;
  predicted_latency_ms: number;
  predicted_cost_usd: number;
  routing_confidence: number;
  reason?: string;
}

export interface ReplanningEventTrace {
  id: string;
  original_step_id: string;
  new_step_id?: string;
  reason: string;
  confidence_before: number;
  confidence_after?: number;
  created_at?: string;
}

export interface ExecutionTrace {
  execution_id: string;
  task_type: string;
  status: string;
  provider?: string;
  model?: string;
  execution_time: number;
  retry_count: number;
  error_message?: string;
  created_at?: string;
}

export interface ApprovalTrace {
  approval_id: number;
  action_type: string;
  status: string;
  risk_level: string;
  title: string;
  created_at?: string;
}

export interface TraceViewResponse {
  trace_id: string;
  owner_id: string;
  plan?: PlanTrace;
  routing_decisions: RoutingDecisionTrace[];
  replanning_events: ReplanningEventTrace[];
  executions: ExecutionTrace[];
  approvals: ApprovalTrace[];
  total_latency_ms: number;
}

export class TracesService {
  async getTrace(traceId: string): Promise<TraceViewResponse> {
    const res = await apiClient.get<ApiResponse<TraceViewResponse>>(`/observability/traces/${traceId}`);
    return res.data.data;
  }
}

export const tracesService = new TracesService();
