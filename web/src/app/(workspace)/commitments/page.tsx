"use client";

import React, { useState } from "react";
import { toast } from "sonner";
import {
    useCommitments,
    useCommitmentStats,
    useActiveCommitmentRun,
    useStartCommitmentRun,
    useCancelCommitmentRun,
    useCreateCommitment,
    useUpdateCommitment,
    useCompleteCommitment,
    useDismissCommitment,
    useReopenCommitment,
} from "@/hooks/useCommitments";
import { CommitmentDTO, FollowUpDraftDTO } from "@/types/commitment";
import { CommitmentService } from "@/services/commitment.service";

import { CommitmentHeader } from "@/components/commitments/CommitmentHeader";
import { DiscoveryCenter } from "@/components/commitments/DiscoveryCenter";
import { CommitmentRunMonitor } from "@/components/commitments/CommitmentRunMonitor";
import { CommitmentStats } from "@/components/commitments/CommitmentStats";
import { CommitmentFilters } from "@/components/commitments/CommitmentFilters";
import { CommitmentTable } from "@/components/commitments/CommitmentTable";
import { CommitmentDetailDrawer } from "@/components/commitments/CommitmentDetailDrawer";
import { CommitmentFormDialog } from "@/components/commitments/CommitmentFormDialog";
import { FollowUpCenterDialog } from "@/components/commitments/FollowUpCenterDialog";
import { CommitmentAnalyticsModal } from "@/components/commitments/CommitmentAnalyticsModal";

export default function CommitmentsPage() {
    // Filter & Search State
    const [search, setSearch] = useState("");
    const [status, setStatus] = useState("all");
    const [direction, setDirection] = useState("all");
    const [sourceType, setSourceType] = useState("all");
    const [priority, setPriority] = useState("all");
    const [viewMode, setViewMode] = useState<"table" | "followup" | "analytics" | "history">("table");

    // Interactive Dialogs & Drawers
    const [selectedCommitment, setSelectedCommitment] = useState<CommitmentDTO | null>(null);
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [editingCommitment, setEditingCommitment] = useState<CommitmentDTO | null>(null);
    const [isAnalyticsOpen, setIsAnalyticsOpen] = useState(false);
    const [dismissedRunId, setDismissedRunId] = useState<string | null>(null);

    // Follow-up state
    const [followUpDraft, setFollowUpDraft] = useState<FollowUpDraftDTO | null>(null);
    const [isDraftLoading, setIsDraftLoading] = useState(false);
    const [isFollowUpOpen, setIsFollowUpOpen] = useState(false);

    // Backend queries & mutations
    const {
        data: commitments = [],
        isLoading: isCommitmentsLoading,
        refetch: refetchCommitments,
    } = useCommitments({
        status: status === "all" ? undefined : status,
        direction: direction === "all" ? undefined : direction,
        source_type: sourceType === "all" ? undefined : sourceType,
        priority: priority === "all" ? undefined : priority,
        search: search.trim() || undefined,
    });

    const { data: stats, refetch: refetchStats } = useCommitmentStats();
    const { data: activeRun, refetch: refetchActiveRun } = useActiveCommitmentRun();

    const startRun = useStartCommitmentRun();
    const cancelRun = useCancelCommitmentRun();
    const createCommitment = useCreateCommitment();
    const updateCommitment = useUpdateCommitment();
    const completeCommitment = useCompleteCommitment();
    const dismissCommitment = useDismissCommitment();
    const reopenCommitment = useReopenCommitment();

    // Handlers
    const handleRefreshAll = () => {
        refetchCommitments();
        refetchStats();
        refetchActiveRun();
        toast.success("Commitments updated");
    };

    const handleStartScan = () => {
        setDismissedRunId(null);
        startRun.mutate(
            { run_type: "scan", max_emails: 15 },
            {
                onSuccess: () => toast.success("Started background scan across Gmail and meetings"),
                onError: (err: any) => toast.error(err?.message || "Failed to start scan"),
            }
        );
    };

    const handleStartSweep = () => {
        setDismissedRunId(null);
        startRun.mutate(
            { run_type: "sweep", max_emails: 15 },
            {
                onSuccess: () => toast.success("Started AI Sweep: detecting promises and drafting proposals"),
                onError: (err: any) => toast.error(err?.message || "Failed to start AI Sweep"),
            }
        );
    };

    const handleCancelRun = () => {
        if (!activeRun) return;
        cancelRun.mutate(activeRun.id, {
            onSuccess: () => toast.info("Cancellation requested"),
            onError: () => toast.error("Failed to cancel run"),
        });
    };

    const handleDraftFollowUp = async (commitmentId: string) => {
        setIsDraftLoading(true);
        setIsFollowUpOpen(true);
        try {
            const draft = await CommitmentService.generateFollowUp(commitmentId);
            setFollowUpDraft(draft);
        } catch (err: any) {
            toast.error(err?.message || "Failed to generate follow-up draft");
            setIsFollowUpOpen(false);
        } finally {
            setIsDraftLoading(false);
        }
    };

    const handleProposeTask = async (commitmentId: string) => {
        try {
            const res = await CommitmentService.proposeTask(commitmentId);
            toast.success(res.message || "Task proposal submitted to AI Inbox for review");
        } catch (err: any) {
            toast.error(err?.message || "Failed to propose task in AI Inbox");
        }
    };

    const handleComplete = (id: string) => {
        completeCommitment.mutate(id, {
            onSuccess: () => {
                toast.success("Commitment marked completed");
                if (selectedCommitment?.id === id) {
                    setSelectedCommitment((prev) => (prev ? { ...prev, status: "completed", effective_status: "completed" } : null));
                }
            },
            onError: () => toast.error("Failed to complete commitment"),
        });
    };

    const handleDismiss = (id: string) => {
        dismissCommitment.mutate(id, {
            onSuccess: () => {
                toast.info("Commitment dismissed");
                if (selectedCommitment?.id === id) {
                    setSelectedCommitment(null);
                }
            },
            onError: () => toast.error("Failed to dismiss commitment"),
        });
    };

    const handleReopen = (id: string) => {
        reopenCommitment.mutate(id, {
            onSuccess: () => {
                toast.success("Commitment reopened");
                if (selectedCommitment?.id === id) {
                    setSelectedCommitment((prev) => (prev ? { ...prev, status: "pending", effective_status: "pending" } : null));
                }
            },
            onError: () => toast.error("Failed to reopen commitment"),
        });
    };

    const visibleRun = activeRun && activeRun.id !== dismissedRunId ? activeRun : null;

    return (
        <div className="space-y-6">
            {/* 1. Header */}
            <CommitmentHeader
                onScan={handleStartScan}
                onSweep={handleStartSweep}
                onCreateManual={() => {
                    setEditingCommitment(null);
                    setIsFormOpen(true);
                }}
                onRefresh={handleRefreshAll}
                onOpenAnalytics={() => setIsAnalyticsOpen(true)}
                activeRun={activeRun ?? null}
                isStartingRun={startRun.isPending}
            />

            {/* 2. Run Execution Monitor (Durable progress & stage breakdown) */}
            {visibleRun && (
                <CommitmentRunMonitor
                    run={visibleRun}
                    onCancel={handleCancelRun}
                    onDismiss={() => setDismissedRunId(visibleRun.id)}
                    isCancelling={cancelRun.isPending}
                />
            )}

            {/* 3. Discovery Connectors */}
            <DiscoveryCenter
                stats={stats}
                onTriggerScan={handleStartScan}
                isScanning={startRun.isPending || (activeRun?.status === "running")}
            />

            {/* 4. Statistics Cards */}
            <CommitmentStats
                stats={stats}
                activeFilter={status}
                onSelectFilter={(newStatus) => setStatus(newStatus)}
            />

            {/* 5. Filters & Search */}
            <CommitmentFilters
                search={search}
                onSearchChange={setSearch}
                direction={direction}
                onDirectionChange={setDirection}
                status={status}
                onStatusChange={setStatus}
                sourceType={sourceType}
                onSourceTypeChange={setSourceType}
                priority={priority}
                onPriorityChange={setPriority}
                viewMode={viewMode}
                onViewModeChange={(mode) => {
                    if (mode === "analytics") {
                        setIsAnalyticsOpen(true);
                    } else {
                        setViewMode(mode);
                    }
                }}
            />

            {/* 6. Main Commitments Table */}
            {isCommitmentsLoading ? (
                <div className="flex h-48 items-center justify-center rounded-xl border border-border bg-card/50">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                        Loading commitments...
                    </div>
                </div>
            ) : (
                <CommitmentTable
                    commitments={commitments}
                    onSelectCommitment={(c) => setSelectedCommitment(c)}
                    onComplete={handleComplete}
                    onDismiss={handleDismiss}
                    onReopen={handleReopen}
                    onProposeTask={handleProposeTask}
                    onDraftFollowUp={handleDraftFollowUp}
                />
            )}

            {/* 7. Commitment Detail Drawer */}
            <CommitmentDetailDrawer
                commitment={selectedCommitment}
                open={Boolean(selectedCommitment)}
                onClose={() => setSelectedCommitment(null)}
                onEdit={(c) => {
                    setEditingCommitment(c);
                    setIsFormOpen(true);
                }}
                onComplete={handleComplete}
                onDismiss={handleDismiss}
                onReopen={handleReopen}
                onProposeTask={handleProposeTask}
                onDraftFollowUp={handleDraftFollowUp}
            />

            {/* 8. Manual Commitment Create / Edit Dialog */}
            <CommitmentFormDialog
                open={isFormOpen}
                onClose={() => {
                    setIsFormOpen(false);
                    setEditingCommitment(null);
                }}
                editingCommitment={editingCommitment}
                isSubmitting={createCommitment.isPending || updateCommitment.isPending}
                onSubmitCreate={(input) => {
                    createCommitment.mutate(input, {
                        onSuccess: () => {
                            toast.success("Commitment created");
                            setIsFormOpen(false);
                        },
                        onError: () => toast.error("Failed to create commitment"),
                    });
                }}
                onSubmitUpdate={(id, input) => {
                    updateCommitment.mutate(
                        { id, data: input },
                        {
                            onSuccess: () => {
                                toast.success("Commitment updated");
                                setIsFormOpen(false);
                                setEditingCommitment(null);
                            },
                            onError: () => toast.error("Failed to update commitment"),
                        }
                    );
                }}
            />

            {/* 9. Follow-Up Center Assistant Dialog */}
            <FollowUpCenterDialog
                open={isFollowUpOpen}
                onClose={() => setIsFollowUpOpen(false)}
                draft={followUpDraft}
                isLoading={isDraftLoading}
            />

            {/* 10. Analytics & Insights Modal */}
            <CommitmentAnalyticsModal
                open={isAnalyticsOpen}
                onClose={() => setIsAnalyticsOpen(false)}
            />
        </div>
    );
}
