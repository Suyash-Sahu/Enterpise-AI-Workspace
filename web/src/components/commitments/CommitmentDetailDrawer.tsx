"use client";

import React, { useState } from "react";
import { CommitmentDTO } from "@/types/commitment";
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
    SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    CommitmentStatusBadge,
    CommitmentDirectionBadge,
    CommitmentPriorityBadge,
    CommitmentVerificationBadge,
} from "./CommitmentStatusBadge";
import { useCommitmentEvents, useVerifyCommitment } from "@/hooks/useCommitments";
import { toast } from "sonner";
import {
    CheckCircle2,
    Clock,
    XCircle,
    RotateCcw,
    Send,
    PlusCircle,
    ShieldCheck,
    Calendar,
    Mail,
    FileText,
    ExternalLink,
    AlertCircle,
    UserCheck,
    History,
    Sparkles,
    Edit3,
} from "lucide-react";

interface CommitmentDetailDrawerProps {
    commitment: CommitmentDTO | null;
    open: boolean;
    onClose: () => void;
    onEdit?: (commitment: CommitmentDTO) => void;
    onComplete: (id: string) => void;
    onDismiss: (id: string) => void;
    onReopen: (id: string) => void;
    onProposeTask: (id: string) => void;
    onDraftFollowUp: (id: string) => void;
}

export function CommitmentDetailDrawer({
    commitment,
    open,
    onClose,
    onEdit,
    onComplete,
    onDismiss,
    onReopen,
    onProposeTask,
    onDraftFollowUp,
}: CommitmentDetailDrawerProps) {
    const [isVerifying, setIsVerifying] = useState(false);
    const { data: events = [] } = useCommitmentEvents(commitment?.id);
    const verifyMutation = useVerifyCommitment();

    if (!commitment) return null;

    const effectiveStatus = commitment.effective_status || commitment.status;
    const isCompleted = effectiveStatus === "completed";
    const isDismissed = effectiveStatus === "dismissed";

    const handleVerify = () => {
        setIsVerifying(true);
        verifyMutation.mutate(
            {
                id: commitment.id,
                data: {
                    verification_status: "verified",
                    evidence: "Manually verified by user with confirmation of deliverable fulfillment.",
                    reasoning: "User verified deliverable outcome.",
                },
            },
            {
                onSuccess: () => {
                    toast.success("Commitment verified and marked completed");
                    setIsVerifying(false);
                },
                onError: (err) => {
                    toast.error("Failed to verify commitment");
                    setIsVerifying(false);
                },
            }
        );
    };

    const formatDate = (isoString?: string) => {
        if (!isoString) return "None";
        try {
            return new Date(isoString).toLocaleString([], {
                month: "short",
                day: "numeric",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit",
            });
        } catch {
            return isoString;
        }
    };

    return (
        <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
            <SheetContent className="w-full sm:max-w-xl overflow-y-auto p-6 space-y-6">
                <SheetHeader className="space-y-2 border-b border-border pb-4">
                    <div className="flex flex-wrap items-center gap-2">
                        <CommitmentStatusBadge status={effectiveStatus} />
                        <CommitmentDirectionBadge direction={commitment.direction} />
                        <CommitmentPriorityBadge priority={commitment.priority} />
                        <CommitmentVerificationBadge status={commitment.verification_status} />
                    </div>
                    <SheetTitle className="text-lg font-semibold text-foreground leading-snug">
                        {commitment.description}
                    </SheetTitle>
                    <SheetDescription className="text-xs text-muted-foreground flex items-center gap-2">
                        <span>Created {formatDate(commitment.created_at)}</span>
                        <span>•</span>
                        <span>Source: {commitment.source_type.toUpperCase()}</span>
                    </SheetDescription>
                </SheetHeader>

                {/* Primary Action Buttons */}
                <div className="flex flex-wrap gap-2">
                    {!isCompleted ? (
                        <Button
                            size="sm"
                            className="bg-emerald-600 hover:bg-emerald-700 text-white"
                            onClick={() => onComplete(commitment.id)}
                        >
                            <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
                            Mark Complete
                        </Button>
                    ) : (
                        <Button
                            size="sm"
                            variant="outline"
                            onClick={() => onReopen(commitment.id)}
                        >
                            <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
                            Reopen
                        </Button>
                    )}

                    <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onDraftFollowUp(commitment.id)}
                    >
                        <Send className="h-3.5 w-3.5 mr-1.5 text-blue-500" />
                        Draft Follow-up
                    </Button>

                    <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onProposeTask(commitment.id)}
                    >
                        <PlusCircle className="h-3.5 w-3.5 mr-1.5 text-purple-500" />
                        Propose Task in AI Inbox
                    </Button>

                    {commitment.verification_status !== "verified" && (
                        <Button
                            size="sm"
                            variant="outline"
                            disabled={isVerifying}
                            onClick={handleVerify}
                        >
                            <ShieldCheck className="h-3.5 w-3.5 mr-1.5 text-indigo-500" />
                            Verify Completion
                        </Button>
                    )}

                    {onEdit && (
                        <Button
                            size="sm"
                            variant="outline"
                            onClick={() => onEdit(commitment)}
                        >
                            <Edit3 className="h-3.5 w-3.5 mr-1.5" />
                            Edit
                        </Button>
                    )}

                    {!isDismissed && (
                        <Button
                            size="sm"
                            variant="ghost"
                            className="text-muted-foreground hover:text-rose-500"
                            onClick={() => onDismiss(commitment.id)}
                        >
                            <XCircle className="h-3.5 w-3.5 mr-1.5" />
                            Dismiss
                        </Button>
                    )}
                </div>

                {/* Ownership & Deadline Grid */}
                <div className="grid grid-cols-2 gap-3 rounded-lg border border-border/80 bg-muted/20 p-4 text-xs">
                    <div>
                        <span className="text-muted-foreground">Responsible Person</span>
                        <p className="mt-1 font-medium text-foreground">
                            {commitment.responsible_party || "Unassigned / You"}
                        </p>
                    </div>

                    <div>
                        <span className="text-muted-foreground">Counterparty</span>
                        <p className="mt-1 font-medium text-foreground">
                            {commitment.counterparty || "Unspecified"}
                        </p>
                    </div>

                    <div>
                        <span className="text-muted-foreground">Target Deadline</span>
                        <p className="mt-1 font-medium text-foreground flex items-center gap-1.5">
                            <Calendar className="h-3.5 w-3.5 text-primary" />
                            {commitment.original_due_date_text || commitment.due_date || "No deadline specified"}
                        </p>
                    </div>

                    <div>
                        <span className="text-muted-foreground">Normalized UTC</span>
                        <p className="mt-1 font-medium text-foreground">
                            {commitment.normalized_due_date
                                ? formatDate(commitment.normalized_due_date)
                                : "Not parsed"}
                        </p>
                    </div>
                </div>

                {/* Evidence & Provenance Section */}
                <div className="space-y-2 rounded-lg border border-border/80 bg-card p-4">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                            <Sparkles className="h-3.5 w-3.5 text-purple-500" />
                            AI Evidence & Provenance
                        </span>
                        {commitment.confidence !== null && (
                            <Badge variant="outline" className="text-[10px]">
                                {Math.round((commitment.confidence || 0) * 100)}% Confidence
                            </Badge>
                        )}
                    </div>
                    <blockquote className="rounded-md border-l-2 border-primary/50 bg-muted/40 p-3 text-xs italic text-foreground">
                        "{commitment.evidence || commitment.description}"
                    </blockquote>
                    <p className="text-[11px] text-muted-foreground">
                        Source Reference: <code className="rounded bg-muted px-1 py-0.5">{commitment.source_ref}</code>
                    </p>
                </div>

                {/* Verification Evidence */}
                {(commitment.verification_evidence || commitment.verification_reasoning) && (
                    <div className="space-y-1.5 rounded-lg border border-emerald-500/30 bg-emerald-50/10 dark:bg-emerald-950/20 p-3 text-xs">
                        <span className="font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                            <UserCheck className="h-3.5 w-3.5" />
                            Verification Findings
                        </span>
                        {commitment.verification_evidence && (
                            <p className="text-muted-foreground">{commitment.verification_evidence}</p>
                        )}
                        {commitment.verification_reasoning && (
                            <p className="text-[11px] text-muted-foreground italic">{commitment.verification_reasoning}</p>
                        )}
                    </div>
                )}

                {/* Audit Activity History */}
                <div className="space-y-3">
                    <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                        <History className="h-3.5 w-3.5 text-muted-foreground" />
                        Audit History & Events ({events.length})
                    </h4>
                    {events.length === 0 ? (
                        <p className="text-xs text-muted-foreground">No lifecycle events recorded yet.</p>
                    ) : (
                        <div className="space-y-2 border-l-2 border-border/70 pl-3">
                            {events.map((ev) => (
                                <div key={ev.id} className="relative text-xs">
                                    <div className="flex items-center justify-between">
                                        <span className="font-medium text-foreground capitalize">
                                            {ev.event_type.replace(/_/g, " ")}
                                        </span>
                                        <span className="text-[10px] text-muted-foreground">
                                            {formatDate(ev.created_at)}
                                        </span>
                                    </div>
                                    {ev.details && Object.keys(ev.details).length > 0 && (
                                        <p className="text-[11px] text-muted-foreground mt-0.5">
                                            {JSON.stringify(ev.details)}
                                        </p>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </SheetContent>
        </Sheet>
    );
}
