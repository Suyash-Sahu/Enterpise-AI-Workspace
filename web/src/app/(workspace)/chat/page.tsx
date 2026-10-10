"use client";

import { useState } from "react";
import { useChatSessions, useChatSessionHistory, useCreateChatSession, useSendChatMessage } from "@/hooks/useWorkspaceChat";
import { Bot, Sparkles, Send, Plus, Trash2, Cpu, FileText, ExternalLink, Loader2, User } from "lucide-react";

export default function ChatPage() {
    // No session until one is created or selected. There used to be a
    // hardcoded "sess_default" that was the same conversation for every user
    // on the server.
    const [activeSessionId, setActiveSessionId] = useState<string | undefined>(undefined);
    const [promptText, setPromptText] = useState("");

    const { data: sessions } = useChatSessions();
    const { data: messages, isLoading: isHistoryLoading } = useChatSessionHistory(activeSessionId);
    const createSessionMutation = useCreateChatSession();
    const sendMessageMutation = useSendChatMessage();

    const handleCreateSession = () => {
        createSessionMutation.mutate("New Conversation", {
            onSuccess: (newSess) => {
                if (newSess?.id) {
                    setActiveSessionId(newSess.id);
                }
            },
        });
    };

    const handleSendPrompt = (e: React.FormEvent) => {
        e.preventDefault();
        if (!promptText.trim() || sendMessageMutation.isPending) return;

        const currentPrompt = promptText;
        setPromptText("");

        sendMessageMutation.mutate(
            {
                message: currentPrompt,
                sessionId: activeSessionId,
            },
            {
                // The first message opens a session server-side; adopt it so
                // the rest of the conversation lands in the same place.
                onSuccess: (created) => {
                    if (!activeSessionId && created?.session_id) {
                        setActiveSessionId(created.session_id);
                    }
                },
            }
        );
    };

    return (
        <div className="-m-4 sm:-m-6 lg:-m-8 flex h-[calc(100vh-4rem)] overflow-hidden bg-background">
            {/* Left Chat Sessions Drawer */}
            <aside className="hidden md:flex w-64 flex-col border-r border-border bg-surface">
                <div className="flex h-14 items-center justify-between border-b border-border px-4">
                    <div className="flex items-center gap-2 font-bold text-xs text-foreground">
                        <Bot className="h-4.5 w-4.5 text-primary" />
                        <span>Chat Sessions</span>
                    </div>
                    <button
                        onClick={handleCreateSession}
                        className="rounded-lg border border-border p-1 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                        title="New Chat Session"
                    >
                        <Plus className="h-4 w-4" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-3 space-y-1">
                    {(sessions ?? []).map((sess) => {
                        const isActive = sess.id === activeSessionId;
                        return (
                            <button
                                key={sess.id}
                                onClick={() => setActiveSessionId(sess.id)}
                                className={`w-full flex items-center justify-between rounded-xl px-3 py-2.5 text-xs font-semibold transition-all ${
                                    isActive
                                        ? "bg-primary text-primary-foreground shadow-md font-bold"
                                        : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                                }`}
                            >
                                <span className="truncate">{sess.title}</span>
                                <span className="font-mono text-[10px] opacity-70">
                                    {sess.message_count !== undefined ? `${sess.message_count} msgs` : ""}
                                </span>
                            </button>
                        );
                    })}
                </div>
            </aside>

            {/* Main Supervisor Chat Interface */}
            <div className="flex flex-1 flex-col min-w-0">
                {/* Top Supervisor Header */}
                <div className="flex h-14 items-center justify-between border-b border-border bg-surface/80 px-4 sm:px-6 backdrop-blur-md">
                    <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-tr from-primary to-primary text-primary-foreground shadow-md">
                            <Sparkles className="h-4 w-4" />
                        </div>
                        <div>
                            <h2 className="text-xs font-semibold text-foreground">AMOF Supervisor Agent</h2>
                            <span className="block font-mono text-xs text-primary">Multi-Agent Intent Router (Ollama / OpenRouter)</span>
                        </div>
                    </div>

                    {sendMessageMutation.isPending && (
                        <div className="flex items-center gap-2 font-mono text-xs font-bold text-primary animate-pulse">
                            <Loader2 className="h-4 w-4 animate-spin text-primary" />
                            <span>Routing intent to sub-agents...</span>
                        </div>
                    )}
                </div>

                {/* Messages Stream Area */}
                <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
                    {isHistoryLoading ? (
                        <div className="text-center text-xs text-muted-foreground animate-pulse p-12">
                            Loading conversation history...
                        </div>
                    ) : (messages || []).length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full space-y-4 text-center p-8">
                            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary border border-primary/20">
                                <Sparkles className="h-8 w-8" />
                            </div>
                            <div className="max-w-md space-y-1">
                                <h3 className="text-sm font-bold text-foreground">Enterprise AI Workspace Assistant</h3>
                                <p className="text-xs text-muted-foreground">
                                    Ask questions, summarize Google Drive documents, query Gmail inbox, or generate email drafts. Your prompt will be classified automatically by the Supervisor Agent.
                                </p>
                            </div>
                        </div>
                    ) : (
                        (messages || []).map((msg) => {
                            const isUser = msg.role === "user";
                            return (
                                <div key={msg.id} className={`flex gap-3 max-w-3xl ${isUser ? "ml-auto flex-row-reverse" : "mr-auto"}`}>
                                    <div
                                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl font-bold text-xs shadow-sm ${
                                            isUser
                                                ? "bg-primary text-primary-foreground"
                                                : "bg-surface border border-border text-primary"
                                        }`}
                                    >
                                        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                                    </div>

                                    <div className="space-y-2">
                                        {/* Agent Routing & Provider Badges */}
                                        {!isUser && msg.agent && (
                                            <div className="flex items-center gap-2 font-mono text-xs font-bold">
                                                <span className="rounded-full bg-primary/20 px-2.5 py-0.5 text-primary border border-primary/30">
                                                    {msg.agent}
                                                </span>
                                                <span className="rounded-full bg-primary/20 px-2 py-0.5 text-primary">
                                                    {msg.provider || "Ollama"}
                                                </span>
                                                <span className="text-muted-foreground">{msg.timestamp?.slice(11, 16)}</span>
                                            </div>
                                        )}

                                        {/* Bubble Container */}
                                        <div
                                            className={`rounded-2xl p-4 text-xs leading-relaxed border shadow-sm ${
                                                isUser
                                                    ? "bg-primary text-primary-foreground border-primary/30"
                                                    : "bg-surface border-border text-foreground font-mono"
                                            }`}
                                        >
                                            <p className="whitespace-pre-wrap">{msg.message || msg.content}</p>

                                            {/* Citation Sources Render */}
                                            {msg.sources && msg.sources.length > 0 && (
                                                <div className="mt-3 pt-2 border-t border-border space-y-1.5">
                                                    <span className="font-mono text-xs font-bold text-primary uppercase">RAG Sources & Citations</span>
                                                    {msg.sources.map((src, idx) => (
                                                        <div key={idx} className="rounded-lg bg-background p-2 border border-border text-xs text-muted-foreground space-y-0.5">
                                                            <div className="flex items-center justify-between font-bold text-foreground">
                                                                <span>{src.title}</span>
                                                                {src.page && <span>Page {src.page}</span>}
                                                            </div>
                                                            <p className="italic text-xs line-clamp-2">{src.snippet}</p>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            );
                        })
                    )}

                    {/* Typing Indicator */}
                    {sendMessageMutation.isPending && (
                        <div className="flex gap-3 max-w-2xl mr-auto">
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-surface border border-border text-primary">
                                <Bot className="h-4 w-4" />
                            </div>
                            <div className="flex items-center gap-2 rounded-md border border-border bg-surface p-4 text-xs text-muted-foreground">
                                <span className="flex gap-1" aria-hidden>
                                    <span className="h-1.5 w-1.5 rounded-full bg-primary/70" />
                                    <span className="h-1.5 w-1.5 rounded-full bg-primary/50" />
                                    <span className="h-1.5 w-1.5 rounded-full bg-primary/30" />
                                </span>
                                <span className="ml-1 font-medium text-foreground">Supervisor agent reasoning…</span>
                            </div>
                        </div>
                    )}
                </div>

                {/* Prompt Input Form */}
                <div className="p-4 border-t border-border bg-surface/50">
                    <form onSubmit={handleSendPrompt} className="relative flex items-center">
                        <input
                            type="text"
                            value={promptText}
                            onChange={(e) => setPromptText(e.target.value)}
                            disabled={sendMessageMutation.isPending}
                            placeholder="Ask your question here (type / for commands)"
                            className="w-full rounded-2xl border border-border bg-background py-3.5 pl-4 pr-12 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
                        />
                        <button
                            type="submit"
                            disabled={!promptText.trim() || sendMessageMutation.isPending}
                            className="absolute right-2.5 flex h-8 w-8 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-md hover:scale-105 transition-all disabled:opacity-40"
                        >
                            <Send className="h-4 w-4" />
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}
