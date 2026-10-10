export interface ApprovalRequestDTO {
    id: string;
    action_type: string;
    description: string;
    payload: Record<string, any>;
    requested_by_agent: string;
    status: "PENDING" | "APPROVED" | "REJECTED";
    timestamp: string;
}
