export interface AutomationStepDTO {
    step_id: string;
    capability: string;
    depends_on: string[];
    input_template: Record<string, unknown>;
}

export interface AutomationDTO {
    id: string;
    owner_id: string;
    name: string;
    trigger_type: "schedule" | "condition" | "event";
    schedule?: string;
    condition?: Record<string, unknown>;
    steps: AutomationStepDTO[];
    enabled: boolean;
    execution_history: Record<string, unknown>[];
    created_at: string;
    updated_at: string;
}

export interface AutomationCreateDTO {
    name: string;
    trigger_type: "schedule" | "condition" | "event";
    schedule?: string | null;
    condition?: Record<string, unknown> | null;
    steps: AutomationStepDTO[];
    enabled: boolean;
}

export interface AutomationDraftDTO {
    needs_clarification: boolean;
    clarification?: string;
    draft?: AutomationCreateDTO;
    source_text: string;
    warnings: string[];
}

export interface AutomationRunResultDTO {
    automation_id: string;
    request_id: string;
    status: string;
    approval_id?: number;
}
