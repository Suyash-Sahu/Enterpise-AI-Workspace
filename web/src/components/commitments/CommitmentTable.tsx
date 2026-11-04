"use client";

import React from "react";
import { CommitmentDTO } from "@/types/commitment";
import {
    CommitmentStatusBadge,
    CommitmentDirectionBadge,
    CommitmentPriorityBadge,
    CommitmentVerificationBadge,
} from "./CommitmentStatusBadge";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
    MoreHorizontal,
    CheckCircle2,
    Calendar,
    Mail,
    Send,
    PlusCircle,
    User,
    Clock,
    XCircle,
    RotateCcw,
    ShieldCheck,
} from "lucide-react";

interface CommitmentTableProps {
    commitments: CommitmentDTO[];
    onSelectCommitment: (commitment: CommitmentDTO) => void;
    onComplete: (id: string) => void;
    onDismiss: (id: string) => void;
    onReopen: (id: string) => void;
    onProposeTask: (id: string) => void;
    onDraftFollowUp: (id: string) => void;
}

export function CommitmentTable({
    commitments,
    onSelectCommitment,
    onComplete,
    onDismiss,
    onReopen,
    onProposeTask,
    onDraftFollowUp,
}: CommitmentTableProps) {
    if (commitments.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-12 text-center">
                <div className="rounded-full bg-muted p-3 text-muted-foreground">
                    <CheckCircle2 className="h-6 w-6" />
                </div>
                <h3 className="mt-3 text-sm font-semibold text-foreground">No commitments match the filter</h3>
                <p className="mt-1 text-xs text-muted-foreground max-w-sm">
                    Try adjusting your search criteria, selecting another filter, or running a scan across sources.
                </p>
            </div>
        );
    }

    const formatDeadline = (isoString?: string, rawText?: string) => {
        if (!isoString && !rawText) return "No deadline";
        if (isoString) {
            try {
                const date = new Date(isoString);
                return date.toLocaleDateString([], {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                });
            } catch {
                return rawText || isoString;
            }
        }
        return rawText;
    };

    return (
        <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-xs">
            <table className="w-full text-left text-xs">
                <thead className="border-b border-border bg-muted/40 text-[11px] font-semibold uppercase text-muted-foreground">
                    <tr>
                        <th className="py-3 px-4">Promise / Deliverable</th>
                        <th className="py-3 px-3">Direction</th>
                        <th className="py-3 px-3">Responsible</th>
                        <th className="py-3 px-3">Counterparty</th>
                        <th className="py-3 px-3">Deadline</th>
                        <th className="py-3 px-3">Source</th>
                        <th className="py-3 px-3">Status</th>
                        <th className="py-3 px-3">Priority</th>
                        <th className="py-3 px-3 text-right">Actions</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-border">
                    {commitments.map((c) => {
                        const effStatus = c.effective_status || c.status;
                        const isOverdue = effStatus === "overdue";
                        const isAtRisk = effStatus === "at_risk";
                        const isDone = effStatus === "completed";
                        const isDismissed = effStatus === "dismissed";

                        return (
                            <tr
                                key={c.id}
                                onClick={() => onSelectCommitment(c)}
                                className="group cursor-pointer transition-colors hover:bg-muted/40"
                            >
                                {/* Description */}
                                <td className="py-3.5 px-4 max-w-xs sm:max-w-md">
                                    <div className="font-medium text-foreground line-clamp-2">{c.description}</div>
                                    {c.evidence && (
                                        <p className="text-[11px] text-muted-foreground/80 line-clamp-1 mt-0.5 italic">
                                            "{c.evidence}"
                                        </p>
                                    )}
                                </td>

                                {/* Direction */}
                                <td className="py-3.5 px-3 shrink-0">
                                    <CommitmentDirectionBadge direction={c.direction} />
                                </td>

                                {/* Responsible */}
                                <td className="py-3.5 px-3">
                                    <div className="flex items-center gap-1.5 font-medium text-foreground">
                                        <User className="h-3 w-3 text-muted-foreground shrink-0" />
                                        <span className="truncate max-w-[120px]">
                                            {c.responsible_party || "Unassigned"}
                                        </span>
                                    </div>
                                </td>

                                {/* Counterparty */}
                                <td className="py-3.5 px-3">
                                    <span className="text-muted-foreground truncate max-w-[120px] block">
                                        {c.counterparty || "—"}
                                    </span>
                                </td>

                                {/* Deadline */}
                                <td className="py-3.5 px-3 shrink-0">
                                    <div className="flex flex-col">
                                        <span
                                            className={`font-medium ${
                                                isOverdue
                                                    ? "text-rose-600 dark:text-rose-400 font-semibold"
                                                    : isAtRisk
                                                    ? "text-amber-600 dark:text-amber-400 font-semibold"
                                                    : "text-foreground"
                                            }`}
                                        >
                                            {formatDeadline(c.normalized_due_date, c.original_due_date_text || c.due_date)}
                                        </span>
                                        {c.original_due_date_text && c.normalized_due_date && (
                                            <span className="text-[10px] text-muted-foreground/70">
                                                from: {c.original_due_date_text}
                                            </span>
                                        )}
                                    </div>
                                </td>

                                {/* Source */}
                                <td className="py-3.5 px-3 shrink-0">
                                    <span className="inline-flex items-center gap-1 rounded bg-muted/60 px-2 py-0.5 text-[11px] font-medium text-muted-foreground capitalize">
                                        {c.source_type === "gmail" ? (
                                            <Mail className="h-3 w-3 text-rose-500" />
                                        ) : c.source_type === "meeting" ? (
                                            <Calendar className="h-3 w-3 text-blue-500" />
                                        ) : (
                                            <Clock className="h-3 w-3 text-zinc-500" />
                                        )}
                                        {c.source_type}
                                    </span>
                                </td>

                                {/* Status */}
                                <td className="py-3.5 px-3 shrink-0">
                                    <CommitmentStatusBadge status={effStatus} />
                                </td>

                                {/* Priority */}
                                <td className="py-3.5 px-3 shrink-0">
                                    <CommitmentPriorityBadge priority={c.priority} />
                                </td>

                                {/* Actions Dropdown */}
                                <td
                                    className="py-3.5 px-3 text-right shrink-0"
                                    onClick={(e) => e.stopPropagation()}
                                >
                                    <DropdownMenu>
                                        <DropdownMenuTrigger asChild>
                                            <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                                                <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
                                            </Button>
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end" className="w-44 text-xs">
                                            <DropdownMenuItem onClick={() => onSelectCommitment(c)}>
                                                View Details
                                            </DropdownMenuItem>

                                            {!isDone && (
                                                <DropdownMenuItem onClick={() => onComplete(c.id)}>
                                                    <CheckCircle2 className="h-3.5 w-3.5 mr-2 text-emerald-600" />
                                                    Mark Completed
                                                </DropdownMenuItem>
                                            )}

                                            {isDone && (
                                                <DropdownMenuItem onClick={() => onReopen(c.id)}>
                                                    <RotateCcw className="h-3.5 w-3.5 mr-2 text-blue-600" />
                                                    Reopen
                                                </DropdownMenuItem>
                                            )}

                                            <DropdownMenuItem onClick={() => onDraftFollowUp(c.id)}>
                                                <Send className="h-3.5 w-3.5 mr-2 text-purple-600" />
                                                Draft Follow-Up
                                            </DropdownMenuItem>

                                            <DropdownMenuItem onClick={() => onProposeTask(c.id)}>
                                                <PlusCircle className="h-3.5 w-3.5 mr-2 text-indigo-600" />
                                                Propose WorkGraph Task
                                            </DropdownMenuItem>

                                            <DropdownMenuSeparator />

                                            {!isDismissed ? (
                                                <DropdownMenuItem onClick={() => onDismiss(c.id)}>
                                                    <XCircle className="h-3.5 w-3.5 mr-2 text-muted-foreground" />
                                                    Dismiss
                                                </DropdownMenuItem>
                                            ) : (
                                                <DropdownMenuItem onClick={() => onReopen(c.id)}>
                                                    <RotateCcw className="h-3.5 w-3.5 mr-2 text-muted-foreground" />
                                                    Restore
                                                </DropdownMenuItem>
                                            )}
                                        </DropdownMenuContent>
                                    </DropdownMenu>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

