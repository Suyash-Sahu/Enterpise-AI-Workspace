export interface AMOFStepTrace {
    step: string;
    status: "Completed" | "In Progress" | "Pending";
}

export interface ChatQueryResponseDTO {
    response: string;
    routing: {
        location: "Local" | "Cloud" | "Hybrid";
        model: string;
        reasoning: string;
    };
    step_trace: AMOFStepTrace[];
    sources: string[];
    tools_used: string[];
}