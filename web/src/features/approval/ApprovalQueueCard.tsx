"use client";

import { CheckCircle2, XCircle, ShieldAlert, Sparkles } from "lucide-react";
import { ApprovalRequestDTO } from "@/types/approval";
import { useApproveRequest, useRejectRequest } from "@/hooks/useApprovals";
import { toast } from "sonner";

interface Props {
    approval: ApprovalRequestDTO;
}

export default function ApprovalQueueCard({ approval }: Props) {
    const approveMutation = useApproveRequest();
    const rejectMutation = useRejectRequest();

    const handleApprove = () => {
        approveMutation.mutate(approval.id, {
            onSuccess: () => toast.success(`Action '${approval.action_type}' approved and executed!`),
        });
    };

    const handleReject = () => {
        rejectMutation.mutate(approval.id, {
            onSuccess: () => toast.info(`Action '${approval.action_type}' rejected.`),
        });
    };

    return (
        <div className="rounded-2xl border border-warning/30 bg-warning/5 p-5 space-y-4 shadow-sm">
            <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                    <ShieldAlert className="h-5 w-5 text-warning" />
                    <div>
                        <span className="font-mono text-xs font-bold text-warning uppercase">Human Approval Required</span>
                        <h4 className="text-sm font-bold text-foreground">{approval.action_type}</h4>
                    </div>
                </div>
                <span className="rounded-full bg-warning/10 px-2.5 py-0.5 font-mono text-xs font-bold text-warning border border-warning/20">
                    {approval.status}
                </span>
            </div>

            <p className="text-xs text-muted-foreground leading-relaxed bg-background p-3 rounded-xl border border-border">
                {approval.description}
            </p>

            <div className="flex items-center justify-between text-xs font-mono text-muted-foreground border-t border-border pt-2">
                <span>Agent: <strong className="text-primary">{approval.requested_by_agent}</strong></span>
                <span>{approval.timestamp}</span>
            </div>

            <div className="flex items-center gap-2 pt-1">
                <button
                    onClick={handleApprove}
                    disabled={approveMutation.isPending}
                    className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-success px-4 py-2 text-xs font-semibold text-success-foreground shadow-md transition-all disabled:opacity-50"
                >
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Approve & Execute</span>
                </button>
                <button
                    onClick={handleReject}
                    disabled={rejectMutation.isPending}
                    className="flex-1 flex items-center justify-center gap-1.5 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-2 text-xs font-semibold text-destructive hover:bg-destructive/20 transition-all disabled:opacity-50"
                >
                    <XCircle className="h-4 w-4" />
                    <span>Reject</span>
                </button>
            </div>
        </div>
    );
}
