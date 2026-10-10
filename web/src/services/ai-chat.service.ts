import { apiClient, ApiResponse } from "@/lib/api-client";

/**
 * A citation produced by retrieval.
 *
 * Every assistant turn used to arrive with one of these invented by the
 * backend — a hardcoded Drive filename and snippet attached whether or not
 * anything had been retrieved. Sources are now real or absent, so each field
 * is optional: only what retrieval actually reported is present.
 */
export interface ChatSource {
    type?: string;
    title?: string;
    file_id?: string;
    page?: number;
    snippet?: string;
}

export interface ChatMessageItem {
    id: string;
    session_id?: string;
    role: "user" | "assistant" | "system";
    agent?: string;
    /** Null unless the pipeline reported what actually ran. Never inferred. */
    provider?: string | null;
    runtime?: string | null;
    execution_id?: string | null;
    content?: string;
    message?: string;
    sources?: ChatSource[];
    timestamp: string;
}

export interface ChatSession {
    id: string;
    title: string;
    created_at: string;
    updated_at?: string;
    message_count?: number;
}

export const aiChatService = {
    /**
     * Conversations belonging to the signed-in user.
     *
     * Errors propagate. This used to swallow them and return [], which
     * rendered a failed request as "you have no conversations" — the same
     * screen a new user sees, and indistinguishable from real emptiness.
     */
    async getSessions(): Promise<ChatSession[]> {
        const res = await apiClient.get<ApiResponse<{ sessions: ChatSession[] }>>("/chat/sessions");
        return res.data.data?.sessions ?? [];
    },

    async createSession(title?: string): Promise<ChatSession> {
        const res = await apiClient.post<ApiResponse<ChatSession>>("/chat/session", { title: title || "New Conversation" });
        return res.data.data;
    },

    /** Errors propagate: a failed load must not look like an empty history. */
    async getSessionHistory(sessionId: string): Promise<ChatMessageItem[]> {
        const res = await apiClient.get<ApiResponse<{ messages: ChatMessageItem[] }>>(`/chat/session/${sessionId}`);
        return res.data.data?.messages ?? [];
    },

    async deleteSession(sessionId: string): Promise<void> {
        await apiClient.delete(`/chat/session/${sessionId}`);
    },

    /**
     * Send a turn. Omitting sessionId opens a new conversation.
     *
     * This used to default to a shared "sess_default" id, which was the same
     * conversation for every user on the server. There is no such session now.
     */
    async sendMessage(message: string, sessionId?: string, fileId?: string): Promise<ChatMessageItem> {
        const res = await apiClient.post<ApiResponse<ChatMessageItem>>("/chat", {
            message,
            session_id: sessionId,
            file_id: fileId,
        });
        return res.data.data;
    },
};
