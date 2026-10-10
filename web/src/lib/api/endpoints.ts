// Base URL is the same-origin /api/v1 proxy; see lib/api-client.ts.
// The hardcoded value here pointed at port 8000 while the backend runs on
// 8001, so every call through this module was hitting nothing.

export const ENDPOINTS = {
    AUTH: {
        LOGIN: "/auth/login",
        SIGNUP: "/auth/signup",
        VERIFY_MFA: "/auth/verify-mfa",
        ME: "/auth/me",
    },
    HEALTH: "/health",
    PROJECTS: {
        LIST: "/workgraph/projects",
        CREATE: "/workgraph/projects",
        TASKS: "/workgraph/tasks",
        TASK: (id: string) => `/workgraph/tasks/${id}`,
    },
    CALENDAR: {
        EVENTS: "/calendar/events",
        EVENT: (id: string) => `/calendar/events/${id}`,
    },
    MEETINGS: {
        CREATE: "/meetings",
        FOLLOW_UPS: "/meetings/follow-ups",
    },
    COMMITMENTS: {
        LIST: "/commitments",
        SCAN: "/commitments/scan",
        SWEEP: "/commitments/sweep",
    },
    AUTOMATIONS: {
        LIST: "/automations",
        CREATE: "/automations",
        FROM_TEXT: "/automations/from-text",
        UPDATE: (id: string) => `/automations/${id}`,
        RUN: (id: string) => `/automations/${id}/run`,
        DIGEST_RUN_NOW: "/automations/digest/run-now",
        DIGEST_LATEST: "/automations/digest/latest",
        DIGEST_ENABLE: "/automations/digest/enable",
        DIGEST_DISABLE: "/automations/digest/disable",
    },
    DOCUMENTS: {
        LIST: "/documents",
        UPLOAD: "/documents/upload",
    },
    KNOWLEDGE: {
        SEARCH: "/knowledge/search",
    },
    CHAT: {
        QUERY: "/chat/query",
        WS: "ws://127.0.0.1:8000/api/v1/chat/ws",
    },
    APPROVALS: {
        // The backend lists pending approvals at /approvals/pending;
        // POST /approvals creates one.
        LIST: "/approvals/pending",
        CREATE: "/approvals",
        APPROVE: (id: string) => `/approvals/${id}/approve`,
        REJECT: (id: string) => `/approvals/${id}/reject`,
    },
    WORKSPACES: {
        ME: "/workspaces/me",
    },
    ADMIN: {
        METRICS: "/admin/metrics",
    },
};
