export interface ActionItemDTO {
    id: string;
    description: string;
    owner?: string;
    due_date?: string;
    workgraph_task_id?: string;
}

export interface MeetingDTO {
    id: string;
    owner_id: string;
    transcript_source: string;
    status: string;
    summary?: string;
    decisions: string[];
    risks: string[];
    unresolved_questions: string[];
    action_items: ActionItemDTO[];
    created_at: string;
}

export interface MeetingCreate {
    transcript_text: string;
    transcript_source?: string;
}
