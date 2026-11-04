export type CommitmentStatus = "pending" | "completed" | "at_risk" | "overdue" | "dismissed";
export type CommitmentDirection = "owed_by_me" | "owed_to_me" | "mutual" | "unknown";
export type CommitmentPriority = "low" | "medium" | "high";
export type VerificationStatus = "unverified" | "verification_pending" | "verified" | "rejected";

export interface CommitmentDTO {
    id: string;
    owner_id: string;
    description: string;
    responsible_party?: string;
    counterparty?: string;
    direction: CommitmentDirection;
    due_date?: string;
    original_due_date_text?: string;
    normalized_due_date?: string;
    timezone?: string;
    confidence?: number;
    evidence?: string;
    priority: CommitmentPriority;
    source_type: "gmail" | "meeting" | "manual";
    source_ref: string;
    source_metadata?: Record<string, any>;
    status: CommitmentStatus;
    effective_status?: CommitmentStatus;
    linked_task_id?: string;
    verification_status: VerificationStatus;
    verification_evidence?: string;
    verification_reasoning?: string;
    review_required: boolean;
    created_at: string;
    updated_at: string;
}

export interface CommitmentCreateInput {
    description: string;
    responsible_party?: string;
    counterparty?: string;
    direction?: CommitmentDirection;
    due_date?: string;
    priority?: CommitmentPriority;
    evidence?: string;
    source_type?: "manual" | "gmail" | "meeting";
    source_ref?: string;
}

export interface CommitmentUpdateInput {
    description?: string;
    responsible_party?: string;
    counterparty?: string;
    direction?: CommitmentDirection;
    due_date?: string;
    priority?: CommitmentPriority;
    status?: CommitmentStatus;
    verification_status?: VerificationStatus;
    verification_evidence?: string;
    verification_reasoning?: string;
    linked_task_id?: string;
}

export interface CommitmentVerificationInput {
    verification_status?: VerificationStatus;
    evidence?: string;
    reasoning?: string;
}

export interface CommitmentRunStageDTO {
    id: string;
    stage_name: string;
    stage_order: number;
    status: "pending" | "running" | "completed" | "failed" | "skipped";
    progress_percent: number;
    processed_count: number;
    total_count: number;
    error_message?: string;
    started_at?: string;
    completed_at?: string;
}

export interface CommitmentRunDTO {
    id: string;
    run_id: string;
    owner_id: string;
    run_type: "scan" | "sweep";
    status: "queued" | "running" | "completed" | "completed_with_warnings" | "failed" | "cancelled";
    current_stage?: string;
    progress_percent: number;
    total_items: number;
    processed_items: number;
    successful_items: number;
    failed_items: number;
    commitments_found: number;
    created_count: number;
    updated_count: number;
    warnings: string[];
    errors: string[];
    result_summary?: Record<string, any>;
    cancel_requested: boolean;
    started_at?: string;
    completed_at?: string;
    created_at: string;
    updated_at: string;
    stages: CommitmentRunStageDTO[];
}

export interface CommitmentStatsDTO {
    total: number;
    pending: number;
    at_risk: number;
    overdue: number;
    completed: number;
    dismissed: number;
    completion_rate: number;
    newly_discovered_this_week: number;
    awaiting_others: number;
    owed_by_me: number;
    owed_to_me: number;
    mutual: number;
    unknown: number;
}

export interface CommitmentEventDTO {
    id: string;
    commitment_id: string;
    owner_id: string;
    event_type: string;
    actor_id?: string;
    details?: Record<string, any>;
    created_at: string;
}

export interface FollowUpDraftDTO {
    commitment_id: string;
    counterparty?: string;
    suggested_follow_up_date?: string;
    reason: string;
    subject: string;
    body: string;
}

export interface ActionableInsightDTO {
    type: "risk" | "warning" | "positive" | "follow_up";
    title: string;
    detail: string;
}

export interface CommitmentAnalyticsDTO {
    stats: CommitmentStatsDTO;
    status_distribution: Record<string, number>;
    direction_distribution: Record<string, number>;
    source_distribution: Record<string, number>;
    priority_distribution: Record<string, number>;
    top_counterparties: Array<{ name: string; count: number }>;
    actionable_insights: ActionableInsightDTO[];
}

export interface CommitmentScanResultDTO {
    scanned_gmail: number;
    scanned_meeting_items: number;
    created: number;
    updated: number;
    commitments: CommitmentDTO[];
    total_messages?: number;
    processed_messages?: number;
    successful_messages?: number;
    no_commitment_messages?: number;
    failed_messages?: number;
    commitments_found?: number;
    status?: string;
    warnings?: string[];
    errors?: string[];
}

export interface SweepStepDTO {
    step: string;
    label: string;
    detail: string;
    count: number;
}

export interface CommitmentSweepResultDTO {
    steps: SweepStepDTO[];
    scan: {
        scanned_gmail: number;
        scanned_meeting_items: number;
        created: number;
        updated: number;
    };
    proposals_created: number;
    duplicate_warnings: number;
    risk_alerts_created: number;
    skipped_already_proposed: number;
}
