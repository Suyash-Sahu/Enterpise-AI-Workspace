"use client";

import { useState } from "react";
import { toast } from "sonner";
import PageHeader from "@/components/shared/PageHeader";
import SearchInput from "@/components/shared/SearchInput";
import ComposeEmailModal from "@/components/communication/ComposeEmailModal";
import { SEED_EMAILS, CentralEmail } from "@/data/central-store";
import { Mail, Send, Sparkles, Star, Trash2, Reply, CheckCircle2, CornerUpLeft, Inbox, SendHorizontal, FileEdit, LayoutTemplate } from "lucide-react";

export default function CommunicationPage() {
    const [search, setSearch] = useState("");
    const [emails, setEmails] = useState<CentralEmail[]>(SEED_EMAILS);
    const [selectedEmailId, setSelectedEmailId] = useState<string | null>(SEED_EMAILS[0].id);
    const [activeFolder, setActiveFolder] = useState<"inbox" | "starred" | "sent" | "drafts" | "templates" | "trash">("inbox");
    const [isComposeOpen, setIsComposeOpen] = useState(false);
    const [replyText, setReplyText] = useState("");

    const handleSentEmail = (newEmail: { to: string; subject: string; body: string }) => {
        const sent: CentralEmail = {
            id: `email-${Date.now()}`,
            sender: { name: "Rahul Sharma", email: "rahul@enterprise.ai" },
            subject: newEmail.subject,
            snippet: newEmail.body.slice(0, 60),
            body: newEmail.body,
            timestamp: "Just now",
            priority: "Normal",
            read: true,
            labels: ["Sent"],
        };
        setEmails([sent, ...emails]);
    };

    const filtered = emails.filter((e) => e.subject.toLowerCase().includes(search.toLowerCase()) || e.sender.name.toLowerCase().includes(search.toLowerCase()));
    const selectedEmail = emails.find((e) => e.id === selectedEmailId) || emails[0];

    const applySmartReply = (reply: string) => {
        setReplyText(reply);
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Communication Hub (Gmail Sync)"
                description="AI-first enterprise email inbox with automatic summaries & smart reply."
                breadcrumbs={[{ label: "Workspace" }, { label: "Communication" }]}
                actions={
                    <button
                        onClick={() => setIsComposeOpen(true)}
                        className="flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md transition-all"
                    >
                        <Send className="h-4 w-4" />
                        <span>Compose Email</span>
                    </button>
                }
            />

            {/* Folder Tabs */}
            <div className="flex items-center gap-1.5 overflow-x-auto border-b border-border pb-3">
                {[
                    { id: "inbox", label: "Inbox", icon: Inbox },
                    { id: "starred", label: "Starred", icon: Star },
                    { id: "sent", label: "Sent", icon: SendHorizontal },
                    { id: "drafts", label: "Drafts", icon: FileEdit },
                    { id: "templates", label: "Templates", icon: LayoutTemplate },
                    { id: "trash", label: "Trash", icon: Trash2 },
                ].map((folder) => {
                    const Icon = folder.icon;
                    const isSelected = activeFolder === folder.id;
                    return (
                        <button
                            key={folder.id}
                            onClick={() => setActiveFolder(folder.id as any)}
                            className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all ${
                                isSelected
                                    ? "bg-primary text-primary-foreground shadow-md font-bold"
                                    : "border border-border bg-surface text-muted-foreground hover:bg-muted/50"
                            }`}
                        >
                            <Icon className="h-3.5 w-3.5" />
                            <span>{folder.label}</span>
                        </button>
                    );
                })}
            </div>

            {/* Main Inbox & Thread Split View */}
            <div className="-mx-4 sm:-mx-6 lg:-mx-8 border-t border-border flex h-[calc(100vh-14rem)] overflow-hidden">
                {/* Left Inbox List */}
                <div className="w-80 border-r border-border bg-surface/50 p-3 space-y-3 flex flex-col">
                    <SearchInput value={search} onChange={setSearch} placeholder="Search..." />

                    <div className="flex-1 overflow-y-auto space-y-1">
                        {filtered.map((email) => {
                            const isSelected = email.id === selectedEmailId;
                            return (
                                <button
                                    key={email.id}
                                    onClick={() => setSelectedEmailId(email.id)}
                                    className={`flex w-full flex-col gap-1 rounded-xl p-3 text-left transition-all ${
                                        isSelected
                                            ? "bg-primary/10 border border-primary/30 text-foreground"
                                            : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                                    }`}
                                >
                                    <div className="flex items-center justify-between text-xs">
                                        <span className={`font-bold truncate ${isSelected ? "text-primary" : "text-foreground"}`}>
                                            {email.sender.name}
                                        </span>
                                        <span className="font-mono text-[10px] text-muted-foreground">{email.timestamp}</span>
                                    </div>
                                    <h4 className="text-xs font-semibold text-foreground truncate">{email.subject}</h4>
                                    <p className="text-xs text-muted-foreground line-clamp-1">{email.snippet}</p>
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Right Email Preview & Smart Reply */}
                <div className="flex-1 p-6 overflow-y-auto space-y-6 bg-background">
                    {selectedEmail ? (
                        <div className="space-y-6 max-w-3xl">
                            {/* Email Subject Header */}
                            <div className="flex items-start justify-between border-b border-border pb-4">
                                <div className="space-y-1">
                                    <h2 className="text-lg font-bold text-foreground">{selectedEmail.subject}</h2>
                                    <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
                                        <span>From: <strong className="text-foreground">{selectedEmail.sender.name}</strong> ({selectedEmail.sender.email})</span>
                                        <span>•</span>
                                        <span>{selectedEmail.timestamp}</span>
                                    </div>
                                </div>
                                <span className="rounded-full bg-destructive/10 px-3 py-1 font-mono text-xs font-bold text-destructive border border-destructive/20">
                                    {selectedEmail.priority}
                                </span>
                            </div>

                            {/* AI Summary Callout */}
                            <div className="rounded-2xl border border-primary/20 bg-primary/10 p-4 space-y-1.5">
                                <div className="flex items-center gap-2 text-primary font-bold text-xs">
                                    <Sparkles className="h-4 w-4" />
                                    <span>AMOF Executive Summary</span>
                                </div>
                                <p className="text-xs text-muted-foreground leading-relaxed">
                                    Sarah Jenkins approved the security sign-off for Phase 3 authentication. Requests wrapping AppShellLayout around all workspace routes today.
                                </p>
                            </div>

                            {/* Email Body */}
                            <div className="rounded-2xl border border-border bg-surface p-5 text-xs text-foreground leading-relaxed whitespace-pre-wrap">
                                {selectedEmail.body}
                            </div>

                            {/* One-Click Smart Replies */}
                            <div className="space-y-2 pt-2">
                                <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                                    <Sparkles className="h-3.5 w-3.5 text-primary" />
                                    <span>One-Click Smart Replies</span>
                                </span>
                                <div className="flex flex-wrap gap-2">
                                    {[
                                        "Thanks Sarah! I will complete AppShellLayout wrapping right away.",
                                        "Sounds great. The authentication tests are 100% passing.",
                                        "Can we schedule a 10-minute sync over Google Meet to confirm?",
                                    ].map((reply, i) => (
                                        <button
                                            key={i}
                                            onClick={() => applySmartReply(reply)}
                                            className="rounded-xl border border-border bg-surface px-3 py-2 text-xs font-semibold text-foreground hover:border-primary/50 hover:bg-primary/10 hover:text-primary transition-all text-left"
                                        >
                                            "{reply}"
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Reply Input Box */}
                            <div className="rounded-2xl border border-border bg-surface p-4 space-y-3">
                                <div className="flex items-center gap-2 text-xs font-bold text-foreground">
                                    <CornerUpLeft className="h-4 w-4 text-primary" />
                                    <span>Reply to {selectedEmail.sender.name}</span>
                                </div>
                                <textarea
                                    rows={3}
                                    placeholder="Write your response..."
                                    value={replyText}
                                    onChange={(e) => setReplyText(e.target.value)}
                                    className="w-full rounded-xl border border-border bg-background p-3 text-xs text-foreground focus:border-primary focus:outline-none"
                                />
                                <div className="flex items-center justify-between">
                                    <button className="flex items-center gap-1.5 text-xs font-bold text-primary hover:underline">
                                        <Sparkles className="h-3.5 w-3.5" />
                                        <span>AI Tone & Rewrite</span>
                                    </button>
                                    <button
                                        onClick={() => {
                                            toast.success("Reply sent");
                                            setReplyText("");
                                        }}
                                        className="flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md transition-all"
                                    >
                                        <span>Send Reply</span>
                                        <Send className="h-3.5 w-3.5" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <p className="text-xs text-muted-foreground">Select an email to view thread.</p>
                    )}
                </div>
            </div>

            {/* Compose Modal */}
            <ComposeEmailModal isOpen={isComposeOpen} onClose={() => setIsComposeOpen(false)} onSent={handleSentEmail} />
        </div>
    );
}
