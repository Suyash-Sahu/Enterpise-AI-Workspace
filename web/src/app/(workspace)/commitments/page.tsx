"use client";

import { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { ArrowRight, Bot, CheckCircle2, RefreshCw, ScanSearch, Handshake } from "lucide-react";

import PageHeader from "@/components/shared/PageHeader";
import DataState from "@/components/shared/DataState";
import EmptyState from "@/components/shared/EmptyState";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useCommitments, useCommitmentSweep, useScanCommitments } from "@/hooks/useCommitments";
import { CommitmentDTO, CommitmentStatus, CommitmentSweepResultDTO } from "@/types/commitment";

const STATUS_TABS: { key: CommitmentStatus | "all"; label: string }[] = [
    { key: "all", label: "All" },
    { key: "pending", label: "Pending" },
    { key: "at_risk", label: "At risk" },
    { key: "completed", label: "Completed" },
];

const STATUS_BADGE: Record<CommitmentStatus, "secondary" | "warning" | "success"> = {
    pending: "secondary",
    at_risk: "warning",
    completed: "success",
};

export default function CommitmentsPage() {
    const [tab, setTab] = useState<CommitmentStatus | "all">("all");
    const [sweepResult, setSweepResult] = useState<CommitmentSweepResultDTO | null>(null);
    const { data, isLoading, isError, error, refetch } = useCommitments(tab === "all" ? undefined : tab);
    const scan = useScanCommitments();
    const sweep = useCommitmentSweep();

    return (
        <div className="space-y-6">
            <PageHeader
                title="Commitment Tracker"
                description="Promises detected from Gmail and meeting action items -- pending, completed, and at risk."
                actions={
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => refetch()}>
                            <RefreshCw aria-hidden />
                            Refresh
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={scan.isPending}
                            onClick={() =>
                                scan.mutate(undefined, {
                                    onSuccess: (res) =>
                                        toast.success(
                                            `Scanned ${res.scanned_gmail} email(s) and ${res.scanned_meeting_items} meeting item(s).`
                                        ),
                                    onError: () => toast.error("Commitment scan failed"),
                                })
                            }
                        >
                            <ScanSearch aria-hidden />
                            {scan.isPending ? "Scanning..." : "Scan now"}
                        </Button>
                        <Button
                            size="sm"
                            disabled={sweep.isPending}
                            onClick={() => {
                                setSweepResult(null);
                                sweep.mutate(undefined, {
                                    onSuccess: (res) => setSweepResult(res),
                                    onError: () => toast.error("AI sweep failed"),
                                });
                            }}
                        >
                            <Bot aria-hidden />
                            {sweep.isPending ? "Running AI sweep..." : "Run AI sweep"}
                        </Button>
                    </div>
                }
            />

            <SweepResultPanel result={sweepResult} onDismiss={() => setSweepResult(null)} />

            <div className="flex gap-2 border-b border-border pb-2">
                {STATUS_TABS.map((t) => (
                    <button
                        key={t.key}
                        onClick={() => setTab(t.key)}
                        className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                            tab === t.key
                                ? "bg-primary text-primary-foreground"
                                : "text-muted-foreground hover:bg-muted"
                        }`}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            <DataState
                isLoading={isLoading}
                isError={isError}
                error={error}
                isEmpty={!data?.length}
                onRetry={() => refetch()}
                resource="commitments"
                skeletonVariant="list"
                empty={
                    <EmptyState
                        icon={<Handshake />}
                        title="No commitments tracked yet"
                        description="Run a scan to detect promises from your unread Gmail and meeting action items."
                    />
                }
            >
                <div className="space-y-2">
                    {(data ?? []).map((c) => (
                        <CommitmentRow key={c.id} commitment={c} />
                    ))}
                </div>
            </DataState>
        </div>
    );
}

function SweepResultPanel({
    result,
    onDismiss,
}: {
    result: CommitmentSweepResultDTO | null;
    onDismiss: () => void;
}) {
    if (!result) return null;

    const totalProposals = result.proposals_created + result.duplicate_warnings + result.risk_alerts_created;

    return (
        <Card className="space-y-3 border-primary/30 bg-primary/5 p-5">
            <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Bot className="h-4 w-4" aria-hidden />
                    AI Sweep run
                </h2>
                <Button variant="ghost" size="sm" onClick={onDismiss}>
                    Dismiss
                </Button>
            </div>

            <ol className="space-y-2">
                <AnimatePresence>
                    {result.steps.map((step, idx) => (
                        <motion.li
                            key={step.step}
                            initial={{ opacity: 0, y: 6 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: idx * 0.15 }}
                            className="flex items-start gap-2 text-sm"
                        >
                            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
                            <div>
                                <p className="font-medium text-foreground">{step.label}</p>
                                <p className="text-xs text-muted-foreground">{step.detail}</p>
                            </div>
                        </motion.li>
                    ))}
                </AnimatePresence>
            </ol>

            {totalProposals > 0 ? (
                <Link
                    href="/work/inbox"
                    className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                >
                    Review {totalProposals} proposal{totalProposals === 1 ? "" : "s"} in AI Inbox
                    <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                </Link>
            ) : (
                <p className="text-sm text-muted-foreground">Nothing new to propose right now.</p>
            )}
        </Card>
    );
}

function CommitmentRow({ commitment }: { commitment: CommitmentDTO }) {
    return (
        <Card className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
                <p className="truncate text-sm font-medium text-foreground">{commitment.description}</p>
                <p className="text-xs text-muted-foreground">
                    {commitment.source_type === "gmail" ? "From Gmail" : "From meeting"}
                    {commitment.responsible_party ? ` · ${commitment.responsible_party}` : ""}
                    {commitment.due_date ? ` · due ${commitment.due_date}` : ""}
                </p>
            </div>
            <Badge variant={STATUS_BADGE[commitment.status]}>
                {commitment.status.replace("_", " ")}
            </Badge>
        </Card>
    );
}
