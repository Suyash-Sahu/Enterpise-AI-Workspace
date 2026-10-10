export interface CentralUser {
    id: string;
    name: string;
    email: string;
    role: string;
    avatar: string;
    status: "online" | "idle" | "offline";
    department: string;
}

export interface CentralWorkspace {
    id: string;
    name: string;
    slug: string;
    logo?: string;
    owner: string;
    plan: string;
    memberCount: number;
}

export interface CentralProject {
    id: string;
    name: string;
    description: string;
    progress: number;
    status: "In Progress" | "Completed" | "On Hold" | "Planning";
    openTasksCount: number;
    completedTasksCount: number;
    deadline: string;
    sprintName: string;
    members: CentralUser[];
}

export interface CentralTask {
    id: string;
    projectId: string;
    title: string;
    description: string;
    status: "Todo" | "In Progress" | "Review" | "Testing" | "Done";
    priority: "Critical" | "High" | "Medium" | "Low";
    assignee: CentralUser;
    dueDate: string;
    labels: string[];
    commentsCount: number;
}

export interface CentralDocument {
    id: string;
    name: string;
    type: "pdf" | "docx" | "gdoc" | "xlsx" | "csv" | "txt";
    size: string;
    updatedAt: string;
    owner: string;
    collections: string[];
    summary: string;
}

export interface CentralEmail {
    id: string;
    sender: { name: string; email: string };
    subject: string;
    snippet: string;
    timestamp: string;
    priority: "Urgent" | "High" | "Normal";
    read: boolean;
    labels: string[];
    body: string;
}

export interface CentralEvent {
    id: string;
    title: string;
    date: string;
    time: string;
    category: "Meeting" | "Reminder" | "Deadline" | "Sprint" | "Deployment";
    meetLink?: string;
    attendeesCount: number;
}

export interface CentralNotification {
    id: string;
    type: "project" | "calendar" | "communication" | "documents" | "knowledge" | "ai" | "security";
    title: string;
    description: string;
    priority: "critical" | "high" | "medium" | "low";
    read: boolean;
    createdAt: string;
    module: string;
}

export const SEED_USERS: CentralUser[] = [
    { id: "u-1", name: "Rahul Sharma", email: "rahul@enterprise.ai", role: "Owner", avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80", status: "online", department: "Engineering" },
    { id: "u-2", name: "Alex Mercer", email: "alex.dev@enterprise.ai", role: "Developer", avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&auto=format&fit=crop&q=80", status: "online", department: "Architecture" },
    { id: "u-3", name: "Sarah Jenkins", email: "sarah.j@enterprise.ai", role: "Manager", avatar: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&auto=format&fit=crop&q=80", status: "idle", department: "Product" },
    { id: "u-4", name: "Priya Patel", email: "priya@enterprise.ai", role: "Admin", avatar: "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=100&auto=format&fit=crop&q=80", status: "online", department: "Research" },
];

export const SEED_WORKSPACE: CentralWorkspace = {
    id: "ws-101",
    name: "TechNova AI Workspace",
    slug: "technova-ai",
    owner: "Rahul Sharma",
    plan: "Enterprise Edition (AMOF)",
    memberCount: 42,
};

export const SEED_PROJECTS: CentralProject[] = [
    {
        id: "proj-1",
        name: "AMOF Multi-Agent Engine",
        description: "Adaptive Multi-Agent Orchestration Framework core implementation.",
        progress: 78,
        status: "In Progress",
        openTasksCount: 12,
        completedTasksCount: 38,
        deadline: "2026-08-15",
        sprintName: "Sprint 5 — Agent Routing",
        members: [SEED_USERS[0], SEED_USERS[1], SEED_USERS[2]],
    },
    {
        id: "proj-2",
        name: "Hybrid RAG Vector Pipeline",
        description: "BM25 + Qdrant vector database hybrid retrieval architecture.",
        progress: 92,
        status: "In Progress",
        openTasksCount: 4,
        completedTasksCount: 41,
        deadline: "2026-08-01",
        sprintName: "Sprint 8 — Chunk Optimization",
        members: [SEED_USERS[1], SEED_USERS[3]],
    },
    {
        id: "proj-3",
        name: "Google Workspace Integration Hub",
        description: "Bi-directional synchronization for Gmail, Drive, Docs, and Meet.",
        progress: 45,
        status: "In Progress",
        openTasksCount: 19,
        completedTasksCount: 15,
        deadline: "2026-08-28",
        sprintName: "Sprint 2 — OAuth Scopes",
        members: [SEED_USERS[0], SEED_USERS[2], SEED_USERS[3]],
    },
];

export const SEED_TASKS: CentralTask[] = [
    {
        id: "task-101",
        projectId: "proj-1",
        title: "Implement Multi-Factor Authentication (MFA OTP) Guard",
        description: "Integrate 6-digit OTP verification card with auto-focus movement and 60s countdown timer.",
        status: "Done",
        priority: "Critical",
        assignee: SEED_USERS[1],
        dueDate: "2026-07-28",
        labels: ["Frontend", "Security", "Auth"],
        commentsCount: 5,
    },
    {
        id: "task-102",
        projectId: "proj-1",
        title: "AMOF Orchestration Task Router",
        description: "Build prompt analyzer to decompose requests into Document, Database, and Search subtasks.",
        status: "In Progress",
        priority: "High",
        assignee: SEED_USERS[0],
        dueDate: "2026-08-02",
        labels: ["Backend", "AI", "AMOF"],
        commentsCount: 8,
    },
    {
        id: "task-103",
        projectId: "proj-2",
        title: "Hybrid Search Reranker Optimization",
        description: "Tune Reciprocal Rank Fusion (RRF) parameter alpha=0.6 for BM25 and vector score combination.",
        status: "Review",
        priority: "Medium",
        assignee: SEED_USERS[3],
        dueDate: "2026-07-30",
        labels: ["RAG", "Research"],
        commentsCount: 2,
    },
];

export const SEED_DOCUMENTS: CentralDocument[] = [
    {
        id: "doc-1",
        name: "Enterprise_AI_Workspace_PRD.pdf",
        type: "pdf",
        size: "4.2 MB",
        updatedAt: "2 hours ago",
        owner: "Sarah Jenkins",
        collections: ["Product", "Architecture"],
        summary: "Product requirements document detailing AMOF architecture, hybrid RAG pipeline, and 13 enterprise workspace modules.",
    },
    {
        id: "doc-2",
        name: "AMOF_Agent_Topology_Architecture.docx",
        type: "docx",
        size: "1.8 MB",
        updatedAt: "Yesterday",
        owner: "Alex Mercer",
        collections: ["Engineering", "Architecture"],
        summary: "Technical breakdown of Document, Database, Email, Calendar, Meeting, Writing, Search, and Verification agents.",
    },
    {
        id: "doc-3",
        name: "Sprint_5_Review_Meeting_Notes.gdoc",
        type: "gdoc",
        size: "Google Doc",
        updatedAt: "3 days ago",
        owner: "Rahul Sharma",
        collections: ["Product", "Meetings"],
        summary: "Meeting notes covering sprint velocity, authentication sign-off, and upcoming hybrid vector deployment.",
    },
];

export const SEED_EMAILS: CentralEmail[] = [
    {
        id: "email-1",
        sender: { name: "Sarah Jenkins", email: "sarah.j@enterprise.ai" },
        subject: "Sprint 5 Security & Authentication Review Sign-off",
        snippet: "The auth module with MFA and password strength validator has passed technical review. Proceed with Phase 3 completion.",
        timestamp: "10:14 AM",
        priority: "Urgent",
        read: false,
        labels: ["Work", "Urgent", "Auth"],
        body: "Hi Team,\n\nGreat job on completing the authentication subsystem. The password strength meter, Zod validation, and MFA OTP flow look crisp and responsive. Let's make sure the shared AppShellLayout is wrapped around all workspace routes today.\n\nBest,\nSarah",
    },
    {
        id: "email-2",
        sender: { name: "GitHub Notifications", email: "notifications@github.com" },
        subject: "[AMOF Engine] Pull Request #42 Approved: Add Reciprocal Rank Fusion",
        snippet: "Rahul Sharma approved PR #42 (Add Reciprocal Rank Fusion to Hybrid RAG retriever). All checks passed.",
        timestamp: "Yesterday",
        priority: "Normal",
        read: true,
        labels: ["GitHub", "Engineering"],
        body: "Pull Request #42 has been merged into main.",
    },
];

export const SEED_EVENTS: CentralEvent[] = [
    {
        id: "evt-1",
        title: "AMOF Multi-Agent Architecture Sync",
        date: "Today",
        time: "11:00 AM - 12:00 PM",
        category: "Meeting",
        meetLink: "https://meet.google.com/amof-sync-demo",
        attendeesCount: 6,
    },
    {
        id: "evt-2",
        title: "Hybrid Vector DB Deployment Deadline",
        date: "Tomorrow",
        time: "5:00 PM",
        category: "Deployment",
        attendeesCount: 4,
    },
];

export const SEED_NOTIFICATIONS: CentralNotification[] = [
    {
        id: "notif-1",
        type: "project",
        title: "Authentication Task Assigned",
        description: "You were assigned the MFA OTP Verification Card task by Sarah Jenkins.",
        priority: "high",
        read: false,
        createdAt: "2026-07-28T10:15:00Z",
        module: "Projects",
    },
    {
        id: "notif-2",
        type: "ai",
        title: "AI Insight: Sprint 5 Schedule Warning",
        description: "AMOF Multi-Agent Engine is 2 days behind schedule. Consider reassigning 2 tasks.",
        priority: "medium",
        read: false,
        createdAt: "2026-07-28T09:30:00Z",
        module: "AI Assistant",
    },
    {
        id: "notif-3",
        type: "communication",
        title: "New Email from Sarah Jenkins",
        description: "Sprint 5 Security & Authentication Review Sign-off",
        priority: "high",
        read: true,
        createdAt: "2026-07-28T08:00:00Z",
        module: "Communication",
    },
];
