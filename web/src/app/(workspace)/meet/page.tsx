"use client";

import { useState } from "react";
import { toast } from "sonner";
import PageHeader from "@/components/shared/PageHeader";
import { useCreateMeeting, useMeetingFollowUps } from "@/hooks/useMeetings";
import { MeetingDTO } from "@/types/meeting";
import {
    FileText,
    Sparkles,
    CheckCircle2,
    AlertTriangle,
    HelpCircle,
    ListChecks,
    Loader2,
    Bell,
} from "lucide-react";

// No live Google Meet transcript-export API exists for third-party apps --
// extraction works from an uploaded/exported/pasted transcript, never a live
// Meet pull. Confirmed external constraint (see PHASE_07.md), not a gap.
export default function MeetPage() {
    const [transcript, setTranscript] = useState("");
    const [result, setResult] = useState<MeetingDTO | null>(null);
    const createMeeting = useCreateMeeting();
    const followUps = useMeetingFollowUps();

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!transcript.trim()) return;

        createMeeting.mutate(
            { transcript_text: transcript, transcript_source: "manual_paste" },
            {
                onSuccess: (meeting) => {
                    setResult(meeting);
                    toast.success("Transcript processed");
                },
                onError: () => toast.error("Could not extract this transcript"),
            }
        );
    };

    return (
        <div className="space-y-6 max-w-4xl mx-auto">
            <PageHeader
                title="Meeting Transcripts"
                description="Paste a meeting transcript to get an AI summary, decisions, risks, and action items."
                breadcrumbs={[{ label: "Workspace" }, { label: "Meet" }]}
            />

            {!!followUps.data?.length && (
                <div className="rounded-2xl border border-warning/30 bg-warning/5 p-5 shadow-sm space-y-2">
                    <div className="flex items-center gap-2 text-xs font-bold text-foreground">
                        <Bell className="h-4 w-4 text-warning" />
                        <span>Follow-ups ({followUps.data.length})</span>
                    </div>
                    <ul className="space-y-2">
                        {followUps.data.map((task) => (
                            <li key={task.id} className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2 text-xs">
                                <span className="text-foreground">{task.title}</span>
                                {task.due_date && (
                                    <span className="font-mono text-muted-foreground">
                                        {new Date(task.due_date).toLocaleDateString()}
                                    </span>
                                )}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-3 rounded-2xl border border-border bg-surface p-5 shadow-sm">
                <label className="block text-xs font-bold text-foreground">Transcript</label>
                <textarea
                    value={transcript}
                    onChange={(e) => setTranscript(e.target.value)}
                    rows={10}
                    placeholder="Paste a pasted/exported meeting transcript here..."
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                    required
                />
                <div className="flex justify-end">
                    <button
                        type="submit"
                        disabled={createMeeting.isPending}
                        className="flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md transition-all disabled:opacity-60"
                    >
                        {createMeeting.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Sparkles className="h-4 w-4" />
                        )}
                        <span>Extract Summary & Action Items</span>
                    </button>
                </div>
            </form>

            {result && (
                <div className="space-y-4">
                    {result.summary && (
                        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-2">
                            <div className="flex items-center gap-2 text-xs font-bold text-foreground">
                                <FileText className="h-4 w-4 text-primary" />
                                <span>Summary</span>
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed">{result.summary}</p>
                        </div>
                    )}

                    {result.decisions.length > 0 && (
                        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-2">
                            <div className="flex items-center gap-2 text-xs font-bold text-foreground">
                                <CheckCircle2 className="h-4 w-4 text-success" />
                                <span>Decisions</span>
                            </div>
                            <ul className="list-disc pl-5 space-y-1 text-xs text-muted-foreground">
                                {result.decisions.map((d, i) => (
                                    <li key={i}>{d}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {result.risks.length > 0 && (
                        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-2">
                            <div className="flex items-center gap-2 text-xs font-bold text-foreground">
                                <AlertTriangle className="h-4 w-4 text-warning" />
                                <span>Risks</span>
                            </div>
                            <ul className="list-disc pl-5 space-y-1 text-xs text-muted-foreground">
                                {result.risks.map((r, i) => (
                                    <li key={i}>{r}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {result.unresolved_questions.length > 0 && (
                        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-2">
                            <div className="flex items-center gap-2 text-xs font-bold text-foreground">
                                <HelpCircle className="h-4 w-4 text-info" />
                                <span>Unresolved Questions</span>
                            </div>
                            <ul className="list-disc pl-5 space-y-1 text-xs text-muted-foreground">
                                {result.unresolved_questions.map((q, i) => (
                                    <li key={i}>{q}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {result.action_items.length > 0 && (
                        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-2">
                            <div className="flex items-center gap-2 text-xs font-bold text-foreground">
                                <ListChecks className="h-4 w-4 text-primary" />
                                <span>Action Items</span>
                            </div>
                            <ul className="space-y-2">
                                {result.action_items.map((item) => (
                                    <li key={item.id} className="flex items-center justify-between rounded-xl bg-muted/50 px-3 py-2 text-xs">
                                        <span className="text-foreground">{item.description}</span>
                                        {item.owner && <span className="font-mono text-muted-foreground">{item.owner}</span>}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
