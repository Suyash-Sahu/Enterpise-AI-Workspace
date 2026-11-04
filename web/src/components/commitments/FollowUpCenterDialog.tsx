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
import { FollowUpDraftDTO } from "@/types/commitment";
import { toast } from "sonner";
import { Send, Copy, Check, Sparkles, AlertCircle } from "lucide-react";

interface FollowUpCenterDialogProps {
    open: boolean;
    onClose: () => void;
    draft: FollowUpDraftDTO | null;
    isLoading?: boolean;
}

export function FollowUpCenterDialog({
    open,
    onClose,
    draft,
    isLoading = false,
}: FollowUpCenterDialogProps) {
    const [subject, setSubject] = useState("");
    const [body, setBody] = useState("");
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        if (draft) {
            setSubject(draft.subject || "");
            setBody(draft.body || "");
        }
    }, [draft]);

    const handleCopy = () => {
        const text = `Subject: ${subject}\n\n${body}`;
        navigator.clipboard.writeText(text);
        setCopied(true);
        toast.success("Draft copied to clipboard");
        setTimeout(() => setCopied(false), 2000);
    };

    if (!draft && !isLoading) return null;

    return (
        <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <div className="flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-primary" />
                        <DialogTitle className="text-base font-semibold">
                            AI Follow-Up Assistant
                        </DialogTitle>
                    </div>
                    <DialogDescription className="text-xs text-muted-foreground">
                        {draft?.reason || "Drafting a professional reminder to keep deliverables on schedule."}
                    </DialogDescription>
                </DialogHeader>

                {isLoading ? (
                    <div className="py-8 text-center text-xs text-muted-foreground">
                        Generating context-aware follow-up draft...
                    </div>
                ) : (
                    <div className="space-y-3 text-xs">
                        <div className="rounded-md border border-amber-500/20 bg-amber-500/5 p-2.5 text-[11px] text-amber-700 dark:text-amber-300 flex items-start gap-2">
                            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                            <span>
                                Follow-ups require human approval and are never sent automatically. Review and edit before sending.
                            </span>
                        </div>

                        <div>
                            <label className="font-medium text-foreground block mb-1">
                                Recipient / Counterparty
                            </label>
                            <Input
                                value={draft?.counterparty || "Recipient"}
                                disabled
                                className="bg-muted text-muted-foreground"
                            />
                        </div>

                        <div>
                            <label className="font-medium text-foreground block mb-1">
                                Subject Line
                            </label>
                            <Input
                                value={subject}
                                onChange={(e) => setSubject(e.target.value)}
                            />
                        </div>

                        <div>
                            <label className="font-medium text-foreground block mb-1">
                                Message Body
                            </label>
                            <textarea
                                rows={6}
                                className="w-full rounded-md border border-input bg-background p-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring font-sans"
                                value={body}
                                onChange={(e) => setBody(e.target.value)}
                            />
                        </div>
                    </div>
                )}

                <DialogFooter className="pt-2">
                    <Button variant="outline" size="sm" onClick={onClose}>
                        Close
                    </Button>
                    <Button
                        size="sm"
                        onClick={handleCopy}
                        disabled={isLoading || !body.trim()}
                        className="gap-1.5"
                    >
                        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                        {copied ? "Copied" : "Copy Draft"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

