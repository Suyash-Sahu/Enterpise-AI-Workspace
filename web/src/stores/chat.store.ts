import { create } from "zustand";
import { AI_MODELS } from "@/constants/models";

export interface ChatMessage {
    id: string;
    role: "user" | "assistant" | "system";
    content: string;
    timestamp: string;
    sources?: { title: string; url: string; snippet: string }[];
    tools?: { name: string; status: "Running" | "Completed" | "Failed" }[];
}

export interface Conversation {
    id: string;
    title: string;
    model: string;
    lastMessage: string;
    updatedAt: string;
    messages: ChatMessage[];
}

interface ChatState {
    conversations: Conversation[];
    activeConversationId: string | null;
    selectedModel: string;
    isStreaming: boolean;
    activeTabRightPanel: "sources" | "timeline" | "tools" | "artifacts";
    setSelectedModel: (modelId: string) => void;
    setActiveConversation: (id: string) => void;
    setIsStreaming: (streaming: boolean) => void;
    addMessage: (conversationId: string, message: ChatMessage) => void;
    createNewConversation: (title?: string) => string;
}

const INITIAL_CONVERSATIONS: Conversation[] = [
    {
        id: "conv-1",
        title: "AMOF Multi-Agent Routing Analysis",
        model: "gpt-5.5-turbo",
        lastMessage: "AMOF router successfully assigned Document Agent and Database Agent.",
        updatedAt: "10 minutes ago",
        messages: [
            {
                id: "msg-1",
                role: "user",
                content: "Analyze the architecture PRD and outline the subtask distribution.",
                timestamp: "10:14 AM",
            },
            {
                id: "msg-2",
                role: "assistant",
                content: "### AMOF Subtask Decomposition Summary\n\nBased on `Enterprise_AI_Workspace_PRD.pdf`:\n\n1. **Document Agent**: Extraction of Hybrid RAG requirements.\n2. **Database Agent**: Qdrant vector index payload schema.\n3. **Search Agent**: Reciprocal Rank Fusion tuning.",
                timestamp: "10:15 AM",
                sources: [
                    { title: "Enterprise_AI_Workspace_PRD.pdf", url: "#", snippet: "Section 3.1: AMOF Orchestration Core" },
                ],
                tools: [
                    { name: "Document Agent", status: "Completed" },
                    { name: "Knowledge Hub RAG", status: "Completed" },
                ],
            },
        ],
    },
];

export const useChatStore = create<ChatState>((set) => ({
    conversations: INITIAL_CONVERSATIONS,
    activeConversationId: "conv-1",
    selectedModel: AI_MODELS[0].id,
    isStreaming: false,
    activeTabRightPanel: "sources",
    setSelectedModel: (modelId) => set({ selectedModel: modelId }),
    setActiveConversation: (id) => set({ activeConversationId: id }),
    setIsStreaming: (isStreaming) => set({ isStreaming }),
    addMessage: (conversationId, message) =>
        set((state) => ({
            conversations: state.conversations.map((c) =>
                c.id === conversationId
                    ? {
                          ...c,
                          messages: [...c.messages, message],
                          lastMessage: message.content.slice(0, 60),
                          updatedAt: "Just now",
                      }
                    : c
            ),
        })),
    createNewConversation: (title = "New Conversation") => {
        const newId = `conv-${Date.now()}`;
        const newConv: Conversation = {
            id: newId,
            title,
            model: AI_MODELS[0].id,
            lastMessage: "Conversation initialized...",
            updatedAt: "Just now",
            messages: [],
        };
        set((state) => ({
            conversations: [newConv, ...state.conversations],
            activeConversationId: newId,
        }));
        return newId;
    },
}));
