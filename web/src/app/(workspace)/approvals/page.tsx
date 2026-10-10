"use client";

import PageHeader from "@/components/shared/PageHeader";
import { useApprovals } from "@/hooks/useApprovals";
import ApprovalQueueCard from "@/features/approval/ApprovalQueueCard";
import { ShieldCheck, CheckCircle2, Sparkles, Clock } from "lucide-react";

export default function ApprovalsPage() {
    const { data: approvals, isLoading } = useApprovals();

    return (
        <div className="space-y-6">
            <PageHeader
                title="Human Approval Queue"
                description="Review and authorize AI Agent side-effect operations before execution."
                breadcrumbs={[{ label: "Workspace" }, { label: "Approvals" }]}
                actions={
                    <div className="flex items-center gap-2 rounded-full border border-success/30 bg-success/10 px-3.5 py-1.5 font-mono text-xs font-bold text-success">
                        <ShieldCheck className="h-4 w-4" />
                        <span>Zero-Trust Policy Enforced</span>
                    </div>
                }
            />

            {isLoading ? (
                <div className="rounded-2xl border border-border bg-surface p-6 text-xs text-muted-foreground animate-pulse">
                    Loading pending approval requests from backend...
                </div>
            ) : approvals && approvals.length > 0 ? (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 max-w-4xl">
                    {approvals.map((req) => (
                        <ApprovalQueueCard key={req.id} approval={req} />
                    ))}
                </div>
            ) : (
                <div className="rounded-2xl border border-border bg-surface p-12 text-center space-y-3 max-w-md mx-auto">
                    <CheckCircle2 className="h-10 w-10 text-success mx-auto" />
                    <h3 className="text-sm font-bold text-foreground">Queue is Clear</h3>
                    <p className="text-xs text-muted-foreground">All AI Agent actions have been authorized or reviewed.</p>
                </div>
            )}
        </div>
    );
}
