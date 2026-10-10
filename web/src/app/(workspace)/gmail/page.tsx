"use client";

import { useState } from "react";
import PageHeader from "@/components/shared/PageHeader";
import SearchInput from "@/components/shared/SearchInput";
import ConnectorErrorState from "@/components/shared/ConnectorErrorState";
import { describeConnectorError } from "@/lib/connector-state";
import { useGmailMessages, useUnreadGmail, useGmailLabels, useGmailProfile, useSendEmail, useSaveDraft, useRequestSendApproval } from "@/hooks/useGmail";
import { useGenerateAIWriter } from "@/hooks/useAIWriter";
import { Mail, Send, Save, Sparkles, Inbox, Tag, User, Search, RefreshCw, Plus, CheckCircle2, X } from "lucide-react";

export default function GmailPage() {
    const [search, setSearch] = useState("");
    const [selectedEmail, setSelectedEmail] = useState<any | null>(null);
    const [activeTab, setActiveTab] = useState<"inbox" | "unread">("inbox");
    const [isComposeOpen, setIsComposeOpen] = useState(false);

    // Compose form state
    const [to, setTo] = useState("");
    const [subject, setSubject] = useState("");
    const [body, setBody] = useState("");
    const [aiSummary, setAiSummary] = useState<string | null>(null);
    const [sendError, setSendError] = useState<string | null>(null);
    const [sendNotice, setSendNotice] = useState<string | null>(null);

    const { data: messages, isLoading, isError, error, refetch } = useGmailMessages();
    const { data: unreadMessages } = useUnreadGmail();
    const { data: labels } = useGmailLabels();
    const { data: profile, isError: isProfileError, error: profileError } = useGmailProfile();

    // The profile query's failure was discarded entirely, which is what let a
    // placeholder address stand in for a mailbox nobody had connected.
    const profileState = isProfileError
        ? describeConnectorError(profileError, "Gmail account")
        : null;

    const requestSendApproval = useRequestSendApproval();
    const sendEmailMutation = useSendEmail();
    const saveDraftMutation = useSaveDraft();
    const aiWriterMutation = useGenerateAIWriter();

    const emailList = activeTab === "unread" ? (unreadMessages || []) : (messages || []);
    const filteredEmails = emailList.filter(
        (e) => (e.subject || "").toLowerCase().includes(search.toLowerCase()) || (e.from || "").toLowerCase().includes(search.toLowerCase())
    );
    const activeEmail = selectedEmail || filteredEmails[0];

    // Sending is gated on human approval: this creates a pending approval
    // record rather than sending immediately. The mail goes out once the
    // request is approved on the Approvals screen.
    const handleSend = (e: React.FormEvent) => {
        e.preventDefault();
        setSendError(null);
        requestSendApproval.mutate(
            { to, subject, body },
            {
                onSuccess: () => {
                    setIsComposeOpen(false);
                    setTo("");
                    setSubject("");
                    setBody("");
                    setSendNotice(
                        "Approval requested. The email will be sent once you approve it on the Approvals screen."
                    );
                },
                onError: (err: Error) => {
                    setSendError(err.message || "Could not request approval to send.");
                },
            }
        );
    };

    const handleSaveDraft = () => {
        setSendError(null);
        saveDraftMutation.mutate(
            { to, subject, body },
            {
                onSuccess: () => setSendNotice("Draft saved to Gmail."),
                onError: (err: Error) =>
                    setSendError(err.message || "Could not save the draft."),
            }
        );
    };

    const handleAISummarizeEmail = (emailContent: string) => {
        setAiSummary("Generating email summary...");
        aiWriterMutation.mutate(
            { type: "email", instruction: `Summarize this email concisely: ${emailContent}` },
            {
                onSuccess: (res) => setAiSummary(res),
                onError: (err) => setAiSummary(`Error: ${err.message}`),
            }
        );
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Gmail Workspace Inbox"
                description="Manage messages, draft & send emails, search labels, and perform AI email summaries."
                breadcrumbs={[{ label: "Workspace" }, { label: "Gmail" }]}
                actions={
                    <button
                        onClick={() => setIsComposeOpen(true)}
                        className="flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md transition-all"
                    >
                        <Plus className="h-4 w-4" />
                        <span>Compose Email</span>
                    </button>
                }
            />

            {/* Profile Info Banner */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 rounded-2xl border border-border bg-surface p-4">
                <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-destructive/10 text-destructive font-bold text-sm border border-destructive/20">
                        <Mail className="h-5 w-5" />
                    </div>
                    <div>
                        {/* This used to fall back to "alex.dev@enterprise.ai"
                            labelled "Connected Google OAuth Account", so a
                            workspace with no Google grant displayed a mailbox
                            address that belongs to nobody — directly above the
                            error state saying no account was connected. */}
                        <div className="text-xs font-bold text-foreground">
                            {profile?.emailAddress ?? (isProfileError ? "Not connected" : "…")}
                        </div>
                        <span className="text-xs font-mono text-muted-foreground">
                            {profile?.emailAddress
                                ? "Connected Google OAuth Account"
                                : isProfileError
                                  ? profileState?.body
                                  : "Reading your Google account"}
                        </span>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <SearchInput value={search} onChange={setSearch} placeholder="Search..." className="max-w-xs" />
                </div>
            </div>

            {/* Main Email Layout */}
            {isLoading ? (
                <div className="rounded-2xl border border-border bg-surface p-8 text-center text-xs text-muted-foreground animate-pulse">
                    Synchronizing with Gmail REST API...
                </div>
            ) : isError ? (
                <ConnectorErrorState
                    error={error}
                    resource="Gmail messages"
                    onRetry={() => refetch()}
                />
            ) : (
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                    {/* Inbox Message List */}
                    <div className="lg:col-span-2 space-y-3">
                        <div className="flex items-center justify-between border-b border-border pb-3">
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setActiveTab("inbox")}
                                    className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                                        activeTab === "inbox" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
                                    }`}
                                >
                                    All Inbox ({messages?.length || 0})
                                </button>
                                <button
                                    onClick={() => setActiveTab("unread")}
                                    className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                                        activeTab === "unread" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
                                    }`}
                                >
                                    Unread ({unreadMessages?.length || 0})
                                </button>
                            </div>
                        </div>

                        <div className="space-y-2">
                            {filteredEmails.map((msg) => {
                                const isSelected = activeEmail?.id === msg.id;
                                return (
                                    <div
                                        key={msg.id}
                                        onClick={() => {
                                            setSelectedEmail(msg);
                                            setAiSummary(null);
                                        }}
                                        className={`cursor-pointer rounded-2xl border p-4 shadow-sm transition-all space-y-1.5 ${
                                            isSelected
                                                ? "border-primary bg-primary/10 shadow-md"
                                                : "border-border bg-surface hover:border-primary/40"
                                        }`}
                                    >
                                        <div className="flex items-center justify-between">
                                            <span className="text-xs font-bold text-foreground truncate">{msg.from || "Gmail Contact"}</span>
                                            <span className="font-mono text-xs text-muted-foreground">{msg.date || "Today"}</span>
                                        </div>
                                        <h4 className="text-xs font-semibold text-primary truncate">{msg.subject || "No Subject"}</h4>
                                        <p className="text-xs text-muted-foreground line-clamp-2">{msg.snippet || msg.body}</p>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Email Reader & AI Summary Panel */}
                    <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4">
                        <div className="flex items-center gap-2 border-b border-border pb-3">
                            <Sparkles className="h-5 w-5 text-destructive" />
                            <h3 className="text-sm font-bold text-foreground">Email Preview & AI Summary</h3>
                        </div>

                        {activeEmail ? (
                            <div className="space-y-4 text-xs">
                                <div>
                                    <span className="font-mono text-xs text-muted-foreground">From: {activeEmail.from || "Contact"}</span>
                                    <h4 className="text-sm font-bold text-foreground mt-0.5">{activeEmail.subject || "No Subject"}</h4>
                                </div>

                                <div className="rounded-xl border border-border bg-background p-3 font-mono text-xs text-muted-foreground leading-relaxed max-h-48 overflow-y-auto">
                                    {activeEmail.snippet || activeEmail.body || "No email body text."}
                                </div>

                                <button
                                    onClick={() => handleAISummarizeEmail(activeEmail.snippet || activeEmail.subject)}
                                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-2 text-xs font-semibold text-primary-foreground shadow-md transition-all"
                                >
                                    <Sparkles className="h-4 w-4" />
                                    <span>Summarize Email with AI</span>
                                </button>

                                {aiSummary && (
                                    <div className="rounded-xl border border-primary/30 bg-primary/10 p-3 space-y-1">
                                        <div className="flex items-center gap-1.5 text-primary font-bold text-xs">
                                            <Sparkles className="h-4 w-4" />
                                            <span>AI Email Overview</span>
                                        </div>
                                        <p className="text-xs text-muted-foreground leading-relaxed">{aiSummary}</p>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <p className="text-xs text-muted-foreground">Select an email to view full content and generate AI summaries.</p>
                        )}
                    </div>
                </div>
            )}

            {/* Compose Email Modal */}
            {sendNotice && (
                <div
                    role="status"
                    className="mx-5 mb-4 flex items-start justify-between gap-3 rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-xs text-success"
                >
                    <span>{sendNotice}</span>
                    <button
                        type="button"
                        onClick={() => setSendNotice(null)}
                        className="font-semibold underline underline-offset-2"
                    >
                        Dismiss
                    </button>
                </div>
            )}

            {isComposeOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in">
                    <div className="w-full max-w-lg rounded-2xl border border-border bg-surface shadow-md overflow-hidden">
                        <div className="flex items-center justify-between border-b border-border p-4">
                            <div className="flex items-center gap-2">
                                <Mail className="h-5 w-5 text-primary" />
                                <h3 className="text-sm font-bold text-foreground">Compose Email (Gmail API)</h3>
                            </div>
                            <button onClick={() => setIsComposeOpen(false)} className="rounded-lg p-1 text-muted-foreground hover:bg-muted">
                                <X className="h-4 w-4" />
                            </button>
                        </div>

                        <form onSubmit={handleSend} className="p-5 space-y-4">
                            {sendError && (
                                <div
                                    role="alert"
                                    className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive"
                                >
                                    {sendError}
                                </div>
                            )}
                            <div>
                                <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">To</label>
                                <input
                                    type="email"
                                    required
                                    value={to}
                                    onChange={(e) => setTo(e.target.value)}
                                    placeholder="Recipient email"
                                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Subject</label>
                                <input
                                    type="text"
                                    required
                                    value={subject}
                                    onChange={(e) => setSubject(e.target.value)}
                                    placeholder="Subject..."
                                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Body</label>
                                <textarea
                                    required
                                    rows={5}
                                    value={body}
                                    onChange={(e) => setBody(e.target.value)}
                                    placeholder="Email body..."
                                    className="w-full rounded-xl border border-border bg-background p-3 text-xs text-foreground focus:border-primary focus:outline-none"
                                />
                            </div>

                            <div className="flex items-center justify-between pt-2">
                                <button
                                    type="button"
                                    onClick={handleSaveDraft}
                                    className="flex items-center gap-1.5 rounded-xl border border-border bg-background px-3.5 py-2 text-xs font-semibold text-foreground hover:bg-muted"
                                >
                                    <Save className="h-3.5 w-3.5" />
                                    <span>Save Draft</span>
                                </button>

                                <button
                                    type="submit"
                                    disabled={requestSendApproval.isPending}
                                    className="flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md disabled:opacity-60"
                                >
                                    <Send className="h-3.5 w-3.5" />
                                    <span>
                                        {requestSendApproval.isPending
                                            ? "Requesting approval..."
                                            : "Request approval to send"}
                                    </span>
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
