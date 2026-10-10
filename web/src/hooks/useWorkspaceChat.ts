import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { aiChatService, ChatSession, ChatMessageItem } from "@/services/ai-chat.service";

export function useChatSessions() {
    return useQuery<ChatSession[]>({
        queryKey: ["chat-sessions"],
        queryFn: () => aiChatService.getSessions(),
    });
}

/** Disabled until a session exists — there is no shared default to fall back on. */
export function useChatSessionHistory(sessionId?: string) {
    return useQuery<ChatMessageItem[]>({
        queryKey: ["chat-session-history", sessionId],
        queryFn: () => aiChatService.getSessionHistory(sessionId as string),
        enabled: Boolean(sessionId),
    });
}

export function useCreateChatSession() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (title?: string) => aiChatService.createSession(title),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
        },
    });
}

export function useSendChatMessage() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ message, sessionId, fileId }: { message: string; sessionId?: string; fileId?: string }) =>
            aiChatService.sendMessage(message, sessionId, fileId),
        onSuccess: (data) => {
            // The backend opens a session when none was supplied and returns
            // its id, so the sender does not need to know it in advance.
            queryClient.invalidateQueries({ queryKey: ["chat-session-history", data.session_id] });
            queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
        },
    });
}
