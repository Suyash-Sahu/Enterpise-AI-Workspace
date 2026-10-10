import {
    MessageSquare,
    BrainCircuit,
    Cpu,
    ShieldCheck,
    CheckCircle2,
    Layers,
} from "lucide-react";

export interface StepItem {
    id: number;
    title: string;
    badge: string;
    description: string;
    details: string[];
    icon: typeof MessageSquare;
    color: string;
    lightBg: string;
    borderColor: string;
}

export const STEPS: StepItem[] = [
    {
        id: 1,
        title: "User Request",
        badge: "Step 01",
        description: "Submit natural language instructions across any enterprise tool—Gmail, Drive, Slack, DBs, Jira, or local files.",
        details: [
            "Unified natural language interface",
            "Multi-source context ingestion",
            "Privacy-first credential isolation"
        ],
        icon: MessageSquare,
        color: "text-blue-500",
        lightBg: "bg-blue-500/10",
        borderColor: "border-blue-500/30",
    },
    {
        id: 2,
        title: "AMOF Adaptive Planning",
        badge: "Step 02",
        description: "AMOF analyzes request complexity, breaks it into subtasks, and constructs a dynamic dependency DAG.",
        details: [
            "Intent & entity extraction",
            "Subtask DAG decomposition",
            "Dynamic priority assignment"
        ],
        icon: BrainCircuit,
        color: "text-violet-500",
        lightBg: "bg-violet-500/10",
        borderColor: "border-violet-500/30",
    },
    {
        id: 3,
        title: "Multi-Agent Execution",
        badge: "Step 03",
        description: "Specialized agents (Document, Database, Email, Writing) execute subtasks in parallel via Connector Manager.",
        details: [
            "Parallel agent delegation",
            "Vector RAG & Text-to-SQL",
            "Centralized OAuth connectors"
        ],
        icon: Cpu,
        color: "text-indigo-500",
        lightBg: "bg-indigo-500/10",
        borderColor: "border-indigo-500/30",
    },
    {
        id: 4,
        title: "Local vs Cloud Routing",
        badge: "Step 04",
        description: "AI Execution Manager routes subtasks to Local Ollama/Qwen (for sensitive data) or Cloud LLMs for heavy reasoning.",
        details: [
            "Privacy-preserving token filter",
            "On-device local execution",
            "Cost & latency optimizer"
        ],
        icon: Layers,
        color: "text-emerald-500",
        lightBg: "bg-emerald-500/10",
        borderColor: "border-emerald-500/30",
    },
    {
        id: 5,
        title: "Verification & Human Approval",
        badge: "Step 05",
        description: "Verification Engine audits output consistency; sensitive actions (email send, DB write) trigger human approval.",
        details: [
            "Fact-check arbitration",
            "Human-in-the-loop gating",
            "Immutable audit logging"
        ],
        icon: ShieldCheck,
        color: "text-amber-500",
        lightBg: "bg-amber-500/10",
        borderColor: "border-amber-500/30",
    },
    {
        id: 6,
        title: "Verified Response",
        badge: "Step 06",
        description: "Synthesized single response returned with source citations, execution timeline, and confidence scores.",
        details: [
            "Interactive source citations",
            "Full execution tracing timeline",
            "Semantic memory caching"
        ],
        icon: CheckCircle2,
        color: "text-cyan-500",
        lightBg: "bg-cyan-500/10",
        borderColor: "border-cyan-500/30",
    },
];