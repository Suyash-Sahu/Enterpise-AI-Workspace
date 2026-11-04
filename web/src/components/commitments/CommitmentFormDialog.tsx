"use client";

import React, { useState, useEffect } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CommitmentDTO, CommitmentCreateInput, CommitmentUpdateInput } from "@/types/commitment";

interface CommitmentFormDialogProps {
    open: boolean;
    onClose: () => void;
    onSubmitCreate: (input: CommitmentCreateInput) => void;
    onSubmitUpdate?: (id: string, input: CommitmentUpdateInput) => void;
    editingCommitment?: CommitmentDTO | null;
    isSubmitting?: boolean;
}

export function CommitmentFormDialog({
    open,
    onClose,
    onSubmitCreate,
    onSubmitUpdate,
    editingCommitment,
    isSubmitting = false,
}: CommitmentFormDialogProps) {
    const isEdit = Boolean(editingCommitment);

    const [description, setDescription] = useState("");
    const [responsibleParty, setResponsibleParty] = useState("");
    const [counterparty, setCounterparty] = useState("");
    const [direction, setDirection] = useState<"owed_by_me" | "owed_to_me" | "mutual" | "unknown">("owed_by_me");
    const [dueDate, setDueDate] = useState("");
    const [priority, setPriority] = useState<"low" | "medium" | "high">("medium");
    const [evidence, setEvidence] = useState("");

    useEffect(() => {
        if (editingCommitment) {
            setDescription(editingCommitment.description || "");
            setResponsibleParty(editingCommitment.responsible_party || "");
            setCounterparty(editingCommitment.counterparty || "");
            setDirection(editingCommitment.direction || "owed_by_me");
            setDueDate(editingCommitment.due_date || "");
            setPriority(editingCommitment.priority || "medium");
            setEvidence(editingCommitment.evidence || "");
        } else {
            setDescription("");
            setResponsibleParty("");
            setCounterparty("");
            setDirection("owed_by_me");
            setDueDate("");
            setPriority("medium");
            setEvidence("");
        }
    }, [editingCommitment, open]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!description.trim()) return;

        if (isEdit && editingCommitment && onSubmitUpdate) {
            onSubmitUpdate(editingCommitment.id, {
                description: description.trim(),
                responsible_party: responsibleParty.trim() || undefined,
                counterparty: counterparty.trim() || undefined,
                direction,
                due_date: dueDate.trim() || undefined,
                priority,
            });
        } else {
            onSubmitCreate({
                description: description.trim(),
                responsible_party: responsibleParty.trim() || undefined,
                counterparty: counterparty.trim() || undefined,
                direction,
                due_date: dueDate.trim() || undefined,
                priority,
                evidence: evidence.trim() || undefined,
                source_type: "manual",
            });
        }
    };

    return (
        <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
            <DialogContent className="sm:max-w-lg">
                <form onSubmit={handleSubmit} className="space-y-4">
                    <DialogHeader>
                        <DialogTitle className="text-lg font-semibold">
                            {isEdit ? "Edit Commitment" : "New Commitment"}
                        </DialogTitle>
                        <DialogDescription className="text-xs text-muted-foreground">
                            {isEdit
                                ? "Update ownership, direction, or deadline details."
                                : "Track a new promise, obligation, or deliverable."}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-3 text-xs">
                        <div>
                            <label className="font-medium text-foreground block mb-1">
                                Promise / Deliverable Description <span className="text-rose-500">*</span>
                            </label>
                            <Input
                                placeholder="e.g. Send finalized Q4 forecast to client"
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                required
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="font-medium text-foreground block mb-1">
                                    Direction
                                </label>
                                <select
                                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                                    value={direction}
                                    onChange={(e) => setDirection(e.target.value as any)}
                                >
                                    <option value="owed_by_me">Owed by Me (I promised)</option>
                                    <option value="owed_to_me">Owed to Me (They promised)</option>
                                    <option value="mutual">Mutual Agreement</option>
                                    <option value="unknown">Unknown / Pending Review</option>
                                </select>
                            </div>

                            <div>
                                <label className="font-medium text-foreground block mb-1">
                                    Priority
                                </label>
                                <select
                                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                                    value={priority}
                                    onChange={(e) => setPriority(e.target.value as any)}
                                >
                                    <option value="low">Low Priority</option>
                                    <option value="medium">Medium Priority</option>
                                    <option value="high">High Priority / Urgent</option>
                                </select>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="font-medium text-foreground block mb-1">
                                    Responsible Person
                                </label>
                                <Input
                                    placeholder="e.g. You or Rahul"
                                    value={responsibleParty}
                                    onChange={(e) => setResponsibleParty(e.target.value)}
                                />
                            </div>

                            <div>
                                <label className="font-medium text-foreground block mb-1">
                                    Counterparty
                                </label>
                                <Input
                                    placeholder="e.g. Alice or Client"
                                    value={counterparty}
                                    onChange={(e) => setCounterparty(e.target.value)}
                                />
                            </div>
                        </div>

                        <div>
                            <label className="font-medium text-foreground block mb-1">
                                Target Deadline
                            </label>
                            <Input
                                placeholder="e.g. Next Friday, Tomorrow, or 2026-11-15"
                                value={dueDate}
                                onChange={(e) => setDueDate(e.target.value)}
                            />
                        </div>

                        {!isEdit && (
                            <div>
                                <label className="font-medium text-foreground block mb-1">
                                    Supporting Evidence or Context Notes
                                </label>
                                <Input
                                    placeholder="e.g. Discussed during standup sync"
                                    value={evidence}
                                    onChange={(e) => setEvidence(e.target.value)}
                                />
                            </div>
                        )}
                    </div>

                    <DialogFooter className="pt-2">
                        <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isSubmitting}>
                            Cancel
                        </Button>
                        <Button type="submit" size="sm" disabled={isSubmitting || !description.trim()}>
                            {isSubmitting ? "Saving..." : isEdit ? "Save Changes" : "Create Commitment"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

