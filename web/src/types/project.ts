export interface ProjectDTO {
    id: string;
    owner_id: string;
    name: string;
    description?: string | null;
    status: string;
    created_at: string;
    updated_at: string;
}

export type WorkStatus =
    | "backlog"
    | "open"
    | "todo"
    | "in_progress"
    | "in_review"
    | "blocked"
    | "done"
    | "cancelled";

export type WorkType = "TASK" | "BUG" | "FEATURE";

/** Board / dashboard columns; mirrors STATUS_BUCKETS in workgraph_service.py. */
export type StatusBucket = "open" | "in_progress" | "blocked" | "done";

export function bucketOf(status: WorkStatus): StatusBucket | null {
    switch (status) {
        case "backlog":
        case "open":
        case "todo":
            return "open";
        case "in_progress":
        case "in_review":
            return "in_progress";
        case "blocked":
            return "blocked";
        case "done":
            return "done";
        default:
            return null; // cancelled: not on the board
    }
}

export type WorkPriority =
    | "low"
    | "medium"
    | "high"
    | "urgent";

export interface TaskDTO {
    id: string;
    owner_id: string;
    project_id?: string | null;

    title: string;
    description?: string | null;

    assignee?: string | null;

    priority: WorkPriority;
    status: WorkStatus;
    type: WorkType;

    due_date?: string | null;

    created_by: "human" | "ai";
    created_by_actor?: string | null;
    source_type: string;
    source_ref?: string | null;
    ai_confidence?: number | null;

    depends_on: string[];

    created_at: string;
    updated_at: string;
}

export interface CreateProjectInput {
    name: string;
    description?: string;
}

export interface UpdateProjectInput {
    name?: string;
    description?: string;
    status?: string;
}

export interface CreateWorkItemInput {
    title: string;
    description?: string;
    project_id?: string;
    assignee?: string;
    priority?: WorkPriority;
    status?: WorkStatus;
    type?: WorkType;
    due_date?: string;
    depends_on?: string[];
}

export interface UpdateWorkItemInput {
    title?: string;
    description?: string;
    assignee?: string;
    priority?: WorkPriority;
    status?: WorkStatus;
    type?: WorkType;
    due_date?: string;
}

export type DependencyKind = "BLOCKS" | "BLOCKED_BY" | "RELATES_TO";

export interface TaskDependencyDTO {
    task_id: string;
    depends_on_task_id: string;
    kind?: string;
}

export interface TaskLinksDTO {
    blocked_by: string[];
    blocks: string[];
    relates_to: string[];
}

export interface ActivityDTO {
    id: number;
    task_id: string;
    actor: string;
    event_type: string;
    payload?: Record<string, unknown> | null;
    created_at: string;
}

export type StatusCounts = Record<StatusBucket, number>;

export interface DashboardDTO {
    counts: StatusCounts;
    due_today: TaskDTO[];
    overdue: TaskDTO[];
    recently_updated: TaskDTO[];
}

export interface ProjectStatsDTO {
    project_id: string;
    total: number;
    counts: StatusCounts;
    overdue: number;
}

// ---------------------------------------------------------------------------
// AMOF Work AI layer (proposals, inbox, kill switch, autonomy)
// ---------------------------------------------------------------------------

export type ProposalStatus =
    | "PENDING"
    | "APPROVED"
    | "EXECUTED"
    | "FAILED"
    | "REJECTED"
    | "EXPIRED"
    | "CANCELLED";

export type ProposalKind =
    | "create_item"
    | "update_item"
    | "link_items"
    | "duplicate_warning"
    | "risk_alert"
    | "sprint_plan";

export interface ProposalDTO {
    id: string;
    project_id?: string | null;
    kind: ProposalKind;
    agent: string;
    payload: Record<string, unknown>;
    source: string;
    source_ref?: string | null;
    status: ProposalStatus;
    confidence?: number | null;
    explanation?: string | null;
    privacy_tier?: string | null;
    autonomy_level: string;
    approval_id?: number | null;
    result?: Record<string, unknown> | null;
    error?: string | null;
    created_at?: string | null;
    decided_at?: string | null;
    decided_by?: string | null;
}

export type AutonomyLevel = "L0" | "L1" | "L2" | "L3";
export type MutatingKind = "create_item" | "update_item" | "link_items";

export interface AiSettingsDTO {
    switches: { user: boolean; projects: Record<string, boolean> };
    grants: { project_id: string; action_kind: MutatingKind; level: AutonomyLevel }[];
}


export interface CommandResultDTO {
    mode: "read" | "proposal" | "clarify" | "unsupported";
    answer: string;
    data: {
        items?: Pick<TaskDTO, "id" | "title" | "status" | "priority">[];
        candidates?: Pick<TaskDTO, "id" | "title" | "status" | "priority">[];
        blockers?: Pick<TaskDTO, "id" | "title" | "status" | "priority">[];
    } & Record<string, unknown>;
    proposals: ProposalDTO[];
}

export interface FocusItemDTO {
    task_id: string;
    title: string;
    priority: string;
    status: string;
    due_date?: string | null;
    score: number;
    reasons: string[];
}

export interface FocusPlanDTO {
    items: FocusItemDTO[];
    waiting: { task_id: string; title: string; waiting_on: string[] }[];
    summary: string;
}

export interface RiskDTO {
    type: "overdue" | "blocked_chain" | "unassigned_urgent" | "stale";
    severity: "high" | "medium" | "low";
    task_id: string;
    title: string;
    detail: string;
}

export interface RiskReportDTO {
    risks: RiskDTO[];
    counts: Record<string, number>;
}


// ---------------------------------------------------------------------------
// Automations + comments
// ---------------------------------------------------------------------------

export interface AutomationDTO {
    id: string;
    project_id?: string | null;
    name: string;
    source_text?: string | null;
    trigger: { type: string; to?: string | null };
    conditions: { priority?: string[]; status?: string[]; type?: string[]; unassigned?: boolean };
    actions: { type: string; value?: string | null }[];
    status: "draft" | "active" | "paused";
    previewed: boolean;
    activated_at?: string | null;
    created_at?: string | null;
}

export interface AutomationRunDTO {
    id: number;
    automation_id: string;
    status: string;
    matched_count: number;
    proposals_created: number;
    executed_count: number;
    detail?: Record<string, unknown> | null;
    error?: string | null;
    started_at?: string | null;
}

export interface AutomationPreviewDTO {
    total_matched: number;
    max_items_per_run: number;
    would_exceed_limit: boolean;
    kill_switch_on: boolean;
    warnings: string[];
    sample: {
        task_id: string;
        title: string;
        status: string;
        priority: string;
        drafts: { kind: string; explanation: string; autonomy_level: string; would_auto_execute: boolean }[];
    }[];
}

export interface AutomationBuildDTO {
    needs_clarification: boolean;
    clarification?: string | null;
    automation?: AutomationDTO | null;
    definition?: Record<string, unknown> | null;
    preview?: AutomationPreviewDTO | null;
    warnings: string[];
}

export interface CommentDTO {
    id: string;
    task_id: string;
    author: string;
    body: string;
    edited: boolean;
    created_at: string;
    updated_at: string;
}
