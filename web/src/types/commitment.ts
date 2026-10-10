export type CommitmentStatus = "pending" | "completed" | "at_risk";

export interface CommitmentDTO {
    id: string;
    owner_id: string;
    description: string;
    responsible_party?: string;
    due_date?: string;
    source_type: "gmail" | "meeting";
    source_ref: string;
    status: CommitmentStatus;
    linked_task_id?: string;
    created_at: string;
    updated_at: string;
}

export interface CommitmentScanResultDTO {
    scanned_gmail: number;
    scanned_meeting_items: number;
    created: number;
    updated: number;
    commitments: CommitmentDTO[];
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
