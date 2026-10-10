export interface AMOFNotificationAgent {
    id: string;
    name: string;
    role: string;
    mode: "Local" | "Cloud" | "Hybrid" | "IO";
    badgeColor: string;
    description: string;
}

export const AMOF_AGENTS: AMOFNotificationAgent[] = [
    {
        id: "supervisor",
        name: "Supervisor Agent",
        role: "Task Decomposition & Task Graph Builder",
        mode: "Cloud",
        badgeColor: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
        description: "Decomposes complex requests, assigns subtasks to specialized agents, and orchestrates final execution graph.",
    },
    {
        id: "document",
        name: "Document Agent",
        role: "RAG + Multi-Modal Drive Ingestion",
        mode: "Hybrid",
        badgeColor: "bg-sky-500/10 text-sky-400 border-sky-500/20",
        description: "Searches, embeds, and analyzes Google Drive PDFs, DOCX files, and internal document vaults.",
    },
    {
        id: "database",
        name: "Database Agent",
        role: "Text-to-SQL & Query Execution",
        mode: "Local",
        badgeColor: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
        description: "Translates natural language questions into safe SQL and executes read-only queries against PostgreSQL.",
    },
    {
        id: "meeting",
        name: "Meeting Agent",
        role: "Transcript Summaries & Meet Links",
        mode: "Local",
        badgeColor: "bg-purple-500/10 text-purple-400 border-purple-500/20",
        description: "Summarizes meeting notes, extracts action items, and generates Google Meet video links.",
    },
    {
        id: "writing",
        name: "Writing Agent",
        role: "Drafting & Gmail Compose Synthesis",
        mode: "Cloud",
        badgeColor: "bg-rose-500/10 text-rose-400 border-rose-500/20",
        description: "Synthesizes multi-source outputs into executive emails, PRDs, and project updates.",
    },
    {
        id: "verification",
        name: "Verification Agent",
        role: "Arbitration & Safety Sign-off",
        mode: "Cloud",
        badgeColor: "bg-amber-500/10 text-amber-400 border-amber-500/20",
        description: "Cross-checks agent outputs for hallucination, verifies source citations, and computes confidence scores.",
    },
    {
        id: "connector",
        name: "Connector Agent",
        role: "Gmail & Google Drive OAuth I/O",
        mode: "IO",
        badgeColor: "bg-red-500/10 text-red-400 border-red-500/20",
        description: "Centralized OAuth adapter handling Gmail read/send and Google Drive API synchronization.",
    },
    {
        id: "router",
        name: "AI Execution Manager",
        role: "Privacy, Cost & Latency Router",
        mode: "Hybrid",
        badgeColor: "bg-primary/10 text-primary border-primary/20",
        description: "Intercepts LLM prompts and decides dynamic routing between local desktop Ollama runtime and cloud gateways.",
    },
];
