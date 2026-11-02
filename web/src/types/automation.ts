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

export interface EmailDigestItem {
    id: string;
    thread_id?: string;
    subject: string;
    sender: string;
    sender_email?: string;
    received_at?: string;
    snippet: string;
    labels?: string[];
    classification?: string;
    priority?: string;
    classification_reason?: string;
    date_category?: string;
    is_important?: boolean;
    is_unread?: boolean;
    needs_reply?: boolean;
}

export interface EmailCategoryCounts {
    today: number;
    yesterday: number;
    older: number;
    important: number;
    urgent: number;
    needs_reply: number;
    fyi: number;
    spam: number;
}

export interface CalendarDigestItem {
    id?: string;
    title: string;
    summary?: string;
    start?: string;
    end?: string;
    is_all_day?: boolean;
    location?: string | null;
    meeting_link?: string | null;
    participants?: string[];
    description?: string;
    prep_notes?: string;
}

export interface TaskDigestItem {
    id: string | number;
    title: string;
    description?: string;
    due_date?: string;
    priority?: string;
    status?: string;
    project_id?: string | number;
    project?: string;
    overdue_days?: number;
}

export interface CommitmentDigestItem {
    id: string | number;
    description: string;
    owner?: string;
    responsible_party?: string;
    due_date?: string;
    status?: string;
    source_type?: string;
    source_ref?: string;
    risk_reason?: string;
    priority?: string;
}

export interface SuggestedActionItem {
    id: string;
    title: string;
    description?: string;
    priority?: "urgent" | "high" | "medium" | "low" | string;
    reason?: string;
    action_type?: "reply_email" | "open_email" | "open_task" | "complete_task" | "prepare_meeting" | "resolve_conflict" | "review_commitment" | string;
    related_entity?: {
        type: string;
        id?: string;
    };
    source_reference?: string;
}

export interface AiSummaryPayload {
    text: string;
    priorities?: string[];
    warnings?: string[];
    focus?: string;
    is_ai_generated?: boolean;
}

export interface DigestOverview {
    total_unread: number;
    important_emails: number;
    overdue_tasks: number;
    today_events: number;
}

export interface SourceStatus {
    gmail: "connected" | "disconnected" | "reconnect_required" | string;
    calendar: "connected" | "disconnected" | "reconnect_required" | string;
    tasks: "connected" | "disconnected" | string;
}

export interface DigestPayload {
    date?: string;
    timezone?: string;
    generated_at?: string;
    owner_id?: string;
    overview?: DigestOverview;
    summary?: string | { text?: string; priorities?: string[]; warnings?: string[] };
    ai_summary?: AiSummaryPayload;
    emails?: {
        today?: EmailDigestItem[];
        yesterday?: EmailDigestItem[];
        older?: EmailDigestItem[];
        important?: EmailDigestItem[];
        counts?: EmailCategoryCounts;
        total_unread?: number;
        fetched_count?: number;
        has_more?: boolean;
        next_page_token?: string | null;
        items?: EmailDigestItem[];
    };
    calendar?: {
        events?: CalendarDigestItem[];
        total?: number;
        next_event?: CalendarDigestItem | null;
        conflicts?: { event_a: string; event_b: string }[];
        requires_reauth?: boolean;
    };
    tasks?: {
        overdue?: TaskDigestItem[];
        due_today?: TaskDigestItem[];
        upcoming?: TaskDigestItem[];
    };
    commitments?: {
        at_risk?: CommitmentDigestItem[];
    };
    suggested_actions?: (string | SuggestedActionItem)[];
    source_status?: SourceStatus;
    unread_email?: {
        available?: boolean;
        count?: number;
        total_unread?: number;
        fetched_count?: number;
        items?: EmailDigestItem[];
        reason?: string;
        status?: string;
        important?: number;
        urgent?: number;
        needs_reply?: number;
        fyi?: number;
        spam?: number;
        has_more?: boolean;
    };
    today_events?: {
        available?: boolean;
        count?: number;
        items?: CalendarDigestItem[];
        conflicts?: { event_a: string; event_b: string }[];
        next_event?: CalendarDigestItem | null;
        requires_reauth?: boolean;
        reason?: string;
    };
    overdue_tasks?: {
        available?: boolean;
        count?: number;
        items?: TaskDigestItem[];
        reason?: string;
    };
    upcoming_deadlines?: {
        available?: boolean;
        count?: number;
        items?: TaskDigestItem[];
        due_today?: TaskDigestItem[];
        within_3_days?: TaskDigestItem[];
        within_7_days?: TaskDigestItem[];
        reason?: string;
    };
    at_risk_commitments?: {
        available?: boolean;
        count?: number;
        items?: CommitmentDigestItem[];
        reason?: string;
    };
}


