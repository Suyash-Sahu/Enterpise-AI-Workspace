// Mock dataset for the /research/evaluation screenshot route.
// Every value here is illustrative — see the on-page badge in page.tsx.
// Replace with real experiment API data by swapping these exports.

export interface ResearchMetric {
    label: string;
    value: string;
    note?: string;
}

export interface DagPerformance {
    shape: string;
    sequentialMs: number;
    amofMs: number;
}

export interface RoutingDecision {
    task: string;
    sensitivity: "PUBLIC" | "INTERNAL" | "RESTRICTED" | "CONFIDENTIAL";
    placement: "LOCAL" | "CLOUD";
    reason: string;
}

export interface VerificationResult {
    label: string;
    corruptedOutputs: number;
    rejected: number;
    accepted: number;
    downstreamPoisoned: number;
}

export interface FailureResult {
    strategy: string;
    salvagePct: number;
    blockedDependents: number;
    invalidDownstream: number;
}

export interface ApprovalRecord {
    approvalId: string;
    timestamp: string;
    action: string;
    decision: "PENDING" | "APPROVED" | "REJECTED";
    actor: string;
}

export interface WorkflowResult {
    task: string;
    owner: string;
    dueDate: string;
    verified: boolean;
}

export const overviewMetrics: ResearchMetric[] = [
    { label: "Evaluation Runs", value: "970" },
    { label: "DAG Shapes", value: "5" },
    { label: "Verification", value: "72 / 72" },
    { label: "Failure Containment", value: "100%" },
    { label: "Privacy Violations", value: "0" },
    { label: "Routing Decisions", value: "20" },
];

export const dagPerformance: DagPerformance[] = [
    { shape: "Chain-5", sequentialMs: 608, amofMs: 604 },
    { shape: "Fan-out", sequentialMs: 612, amofMs: 387 },
    { shape: "Wide", sequentialMs: 595, amofMs: 268 },
    { shape: "Diamond", sequentialMs: 485, amofMs: 375 },
    { shape: "Two-Chains", sequentialMs: 592, amofMs: 266 },
];

export const failureResults: FailureResult[] = [
    { strategy: "AMOF-X", salvagePct: 100, blockedDependents: 3, invalidDownstream: 0 },
    { strategy: "Fail-Fast Baseline", salvagePct: 71, blockedDependents: 3, invalidDownstream: 0 },
    { strategy: "Ignore-Dependencies Baseline", salvagePct: 100, blockedDependents: 0, invalidDownstream: 81 },
];

export const verificationResult: VerificationResult[] = [
    { label: "AMOF-X", corruptedOutputs: 72, rejected: 72, accepted: 0, downstreamPoisoned: 0 },
    { label: "Final-Only Verification", corruptedOutputs: 72, rejected: 0, accepted: 72, downstreamPoisoned: 57 },
];

export const routingDecisions: RoutingDecision[] = [
    { task: "Task 01", sensitivity: "PUBLIC", placement: "CLOUD", reason: "Quality requirement" },
    { task: "Task 02", sensitivity: "INTERNAL", placement: "LOCAL", reason: "Cost minimization" },
    { task: "Task 03", sensitivity: "RESTRICTED", placement: "LOCAL", reason: "Privacy constraint (hard)" },
    { task: "Task 04", sensitivity: "PUBLIC", placement: "LOCAL", reason: "Latency budget" },
    { task: "Task 05", sensitivity: "CONFIDENTIAL", placement: "LOCAL", reason: "Privacy constraint (hard)" },
];

export const routingSplit = { local: 13, cloud: 7 };

export const approvalRecords: ApprovalRecord[] = [
    {
        approvalId: "appr_9f21ac",
        timestamp: "2026-09-27 09:14:02",
        action: "Create project tasks",
        decision: "PENDING",
        actor: "user_demo",
    },
];

export const workflowResults: WorkflowResult[] = [
    { task: "Draft evaluation summary", owner: "user_demo", dueDate: "2026-09-28", verified: true },
    { task: "Share benchmark matrix with team", owner: "user_demo", dueDate: "2026-09-29", verified: true },
    { task: "Schedule follow-up sync", owner: "user_demo", dueDate: "2026-09-30", verified: true },
];

export const humanEffort = {
    manualSeconds: 180,
    amofSeconds: 95,
};
