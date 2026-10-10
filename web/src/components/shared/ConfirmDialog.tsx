"use client";

import { AlertTriangle, X } from "lucide-react";

interface Props {
    isOpen: boolean;
    title: string;
    description: string;
    confirmText?: string;
    confirmPhrase?: string;
    onConfirm: () => void;
    onClose: () => void;
}

export default function ConfirmDialog({
    isOpen,
    title,
    description,
    confirmText = "Delete",
    onConfirm,
    onClose,
}: Props) {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in">
            <div className="w-full max-w-md overflow-hidden rounded-2xl border border-destructive/30 bg-surface p-6 shadow-md space-y-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5 text-destructive">
                        <AlertTriangle className="h-5 w-5 shrink-0" />
                        <h3 className="text-base font-bold text-foreground">{title}</h3>
                    </div>
                    <button onClick={onClose} className="rounded-lg p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
                        <X className="h-4 w-4" />
                    </button>
                </div>

                <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>

                <div className="flex items-center justify-end gap-2.5 pt-2">
                    <button
                        onClick={onClose}
                        className="rounded-xl border border-border px-4 py-2 text-xs font-semibold text-foreground hover:bg-muted/50"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={() => {
                            onConfirm();
                            onClose();
                        }}
                        className="rounded-xl bg-destructive px-4 py-2 text-xs font-semibold text-white shadow-lg hover:bg-red-700"
                    >
                        {confirmText}
                    </button>
                </div>
            </div>
        </div>
    );
}
