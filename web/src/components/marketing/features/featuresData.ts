import {
    Bot,
    Layers,
    Search,
    Database,
    Zap,
    Activity,
    Shield,
    Workflow,
    BarChart3,
    Lock,
} from "lucide-react";

export interface FeatureItem {
    id: string;
    category: "agents" | "execution" | "search" | "security";
    title: string;
    subtitle: string;
    description: string;
    icon: typeof Bot;
    badge: string;
    highlights: string[];
    previewText?: string;
}

export const FEATURES: FeatureItem[] = [
    {
        id: "multi-agent",
        category: "agents",
        title: "Autonomous Multi-Agent Swarm",
        subtitle: "Specialized AI Workers Collaborating on Complex Tasks",
        description: "Eight pre-configured agents handle Documents, Databases, Email, Meetings, Code, Writing, and Verification autonomously.",
        icon: Bot,
        badge: "AMOF Core",
        highlights: ["Dynamic DAG planning", "Inter-agent message bus", "Parallel subtask resolution"],
    },
    {
        id: "hybrid-exec",
        category: "execution",
        title: "Adaptive Local & Cloud Execution",
        subtitle: "Privacy-Preserving On-Device Intelligence",
        description: "Run Ollama/Qwen locally for sensitive PII and seamlessly switch to GPT-4o or Claude 3.5 Sonnet for heavy reasoning.",
        icon: Layers,
        badge: "AI Execution Manager",
        highlights: ["Zero-data-leakage local mode", "Smart cost & latency router", "Custom model endpoints"],
    },
    {
        id: "enterprise-search",
        category: "search",
        title: "Universal RAG & Semantic Search",
        subtitle: "Instant Neural Search Across Company Knowledge",
        description: "Vector search across Gmail, Google Drive, Notion, Slack, databases, and local files with exact source citations.",
        icon: Search,
        badge: "Hybrid Vector DB",
        highlights: ["Sub-second retrieval", "Metadata permission filtering", "Source page & paragraph citations"],
    },
    {
        id: "text-to-sql",
        category: "search",
        title: "Natural Language Text-to-SQL",
        subtitle: "Query Enterprise Relational Databases Effortlessly",
        description: "Ask questions in plain English and automatically execute verified SQL queries against Postgres, MySQL, and Snowflake.",
        icon: Database,
        badge: "Database Agent",
        highlights: ["Schema-aware query synthesis", "Read-only safety sandbox", "Instant tabular previews"],
    },
    {
        id: "workflow-automation",
        category: "agents",
        title: "Human-in-the-Loop Approval Gates",
        subtitle: "Full Control Over High-Impact External Actions",
        description: "Require explicit human confirmation before sending emails, updating databases, or creating Jira tickets.",
        icon: Zap,
        badge: "Governance",
        highlights: ["One-click action review", "Draft modification inline", "Policy-based auto-approvals"],
    },
    {
        id: "observability",
        category: "execution",
        title: "Real-Time Observability & Tracing",
        subtitle: "Complete Visibility Into Token Costs & Latency",
        description: "Track model latency, prompt token consumption, confidence arbitration, and agent routing decisions per task.",
        icon: Activity,
        badge: "Analytics",
        highlights: ["Token cost dashboard", "Latency timeline waterfall", "Regression detection alerts"],
    },
    {
        id: "zero-trust",
        category: "security",
        title: "Zero-Trust Credential Isolation",
        subtitle: "Centralized Connector Manager with Scoped OAuth",
        description: "Connect Gmail, Drive, Slack, and Jira without storing raw user credentials. All access uses tokenized OAuth scopes.",
        icon: Lock,
        badge: "Security",
        highlights: ["OAuth2 token encryption", "No credential persistence", "User-scoped permissions"],
    },
    {
        id: "connectors",
        category: "security",
        title: "30+ Native Enterprise Connectors",
        subtitle: "Unify Google Workspace, Microsoft 365 & Developer Tools",
        description: "Seamlessly query across Google Drive, Gmail, Outlook, OneDrive, Slack, Teams, Jira, Linear, and Notion.",
        icon: Workflow,
        badge: "Integrations",
        highlights: ["Bi-directional sync", "Real-time webhook triggers", "Unified API abstraction"],
    },
    {
        id: "semantic-cache",
        category: "execution",
        title: "Semantic Caching & Prompt Memory",
        subtitle: "90% Faster Responses for Frequently Asked Queries",
        description: "Cache high-confidence vector responses locally to eliminate redundant API calls and reduce LLM costs.",
        icon: BarChart3,
        badge: "Performance",
        highlights: ["Vector similarity caching", "Workspace context memory", "Instant cache hits"],
    },
];
