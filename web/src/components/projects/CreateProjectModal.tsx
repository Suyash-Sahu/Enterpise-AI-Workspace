"use client";

import { useState } from "react";
import { X, FolderPlus, Sparkles } from "lucide-react";

interface Props {
    isOpen: boolean;
    onClose: () => void;
    onCreate: (project: { name: string; description: string; sprintName: string }) => void;
}

export default function CreateProjectModal({ isOpen, onClose, onCreate }: Props) {
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [sprintName, setSprintName] = useState("Sprint 1 — Core Setup");

    if (!isOpen) return null;

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!name.trim()) return;
        onCreate({ name, description, sprintName });
        onClose();
        setName("");
        setDescription("");
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in">
            <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-border bg-surface p-6 shadow-md space-y-4">
                <div className="flex items-center justify-between border-b border-border pb-3">
                    <div className="flex items-center gap-2">
                        <FolderPlus className="h-5 w-5 text-primary" />
                        <h3 className="text-sm font-bold text-foreground">Create New Enterprise Project</h3>
                    </div>
                    <button onClick={onClose} className="rounded-lg p-1 text-muted-foreground hover:bg-muted">
                        <X className="h-4 w-4" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4 text-xs">
                    <div className="space-y-1">
                        <label className="block font-semibold text-foreground">Project Name</label>
                        <input
                            type="text"
                            placeholder="e.g. AMOF Hybrid Execution Engine"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                            required
                        />
                    </div>

                    <div className="space-y-1">
                        <label className="block font-semibold text-foreground">Description</label>
                        <textarea
                            rows={3}
                            placeholder="Describe project objectives and scope..."
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                        />
                    </div>

                    <div className="space-y-1">
                        <label className="block font-semibold text-foreground">Initial Sprint Name</label>
                        <input
                            type="text"
                            value={sprintName}
                            onChange={(e) => setSprintName(e.target.value)}
                            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                        />
                    </div>

                    <div className="flex items-center justify-end gap-2 pt-2">
                        <button
                            type="button"
                            onClick={onClose}
                            className="rounded-xl border border-border bg-surface px-4 py-2 text-xs font-semibold text-foreground hover:bg-muted"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className="flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md"
                        >
                            <Sparkles className="h-3.5 w-3.5" />
                            <span>Create Project</span>
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
