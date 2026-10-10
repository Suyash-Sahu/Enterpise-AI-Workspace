export interface FAQItem {
    id: string;
    question: string;
    answer: string;
    category: "general" | "security" | "models" | "integrations";
}

export const FAQS: FAQItem[] = [
    {
        id: "amof-explain",
        category: "general",
        question: "What is AMOF (Adaptive Multi-Agent Orchestration Framework)?",
        answer: "AMOF is our proprietary orchestration engine that breaks down natural language user requests into subtask DAGs, dispatches each subtask to specialized AI agents (Document, Database, Email, etc.), evaluates privacy/cost parameters, and synthesizes a single verified response.",
    },
    {
        id: "local-mode",
        category: "security",
        question: "How does Local Execution Mode ensure zero data leakage?",
        answer: "In Local Mode, the desktop workspace runs open-source LLMs (such as Ollama Qwen2.5-32B or Llama 3) entirely within your machine's hardware environment. Zero prompts or file data are uploaded to third-party cloud servers.",
    },
    {
        id: "gmail-drive",
        category: "integrations",
        question: "Does Enterprise AI Workspace store my Gmail or Drive credentials?",
        answer: "No. The platform utilizes a centralized Connector Manager with user-authenticated OAuth 2.0 authorization tokens. Credentials are isolated on your client machine and never stored on central servers.",
    },
    {
        id: "human-approval",
        category: "security",
        question: "What is the Human-in-the-Loop Approval Gate?",
        answer: "For any action that produces external side-effects—such as sending an email via Gmail, executing a database write, or creating a Jira ticket—the workspace pauses execution and displays an approval UI where you can review, edit, or reject the action.",
    },
    {
        id: "custom-models",
        category: "models",
        question: "Can we connect custom cloud LLM endpoints or self-hosted models?",
        answer: "Yes! You can configure custom OpenAI-compatible API endpoints, Azure OpenAI instances, vLLM servers, or local Ollama instances directly in your workspace settings.",
    },
    {
        id: "text-to-sql",
        category: "integrations",
        question: "How does Text-to-SQL prevent accidental database deletion?",
        answer: "The Database Agent operates in strict read-only execution sandboxes. It automatically validates generated SQL statements to prevent any DDL/DML mutations (`DROP`, `DELETE`, `UPDATE`) unless explicit admin write mode is enabled with human approval.",
    },
];
