"use client";

import { useProjectStore } from "@/stores/project.store";
import { PriorityBadge } from "@/components/shared/BadgeVariants";
import { X, Clock, User, CheckSquare, MessageSquare, Send } from "lucide-react";
import { useState } from "react";

interface Props {
    taskId: string | null;
    onClose: () => void;
}

export default function TaskModal({ taskId, onClose }: Props) {
    const { tasks, moveTaskStatus } = useProjectStore();
    const [newComment, setNewComment] = useState("");

    if (!taskId) return null;
    const task = tasks.find((t) => t.id === taskId);
    if (!task) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in">
            <div className="w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-surface p-6 shadow-md space-y-4">
                <div className="flex items-start justify-between">
                    <div>
                        <div className="flex items-center gap-2">
                            <PriorityBadge priority={task.priority} />
                            <span className="font-mono text-xs text-muted-foreground">ID: {task.id}</span>
                        </div>
                        <h3 className="mt-1 text-lg font-bold text-foreground">{task.title}</h3>
                    </div>
                    <button onClick={onClose} className="rounded-lg p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
                        <X className="h-4 w-4" />
                    </button>
                </div>

                {/* Status Switcher */}
                <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-muted-foreground">Status:</span>
                    {(["Todo", "In Progress", "Review", "Testing", "Done"] as const).map((st) => (
                        <button
                            key={st}
                            onClick={() => moveTaskStatus(task.id, st)}
                            className={`rounded-lg px-2.5 py-1 text-xs font-mono font-bold transition-all ${
                                task.status === st
                                    ? "bg-primary text-primary-foreground shadow-sm"
                                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                            }`}
                        >
                            {st}
                        </button>
                    ))}
                </div>

                <div className="space-y-1">
                    <h4 className="text-xs font-bold text-foreground">Description</h4>
                    <p className="text-xs text-muted-foreground leading-relaxed bg-background p-3 rounded-xl border border-border">
                        {task.description}
                    </p>
                </div>

                {/* Task Metadata */}
                <div className="grid grid-cols-2 gap-4 rounded-xl border border-border bg-muted/30 p-3 text-xs">
                    <div>
                        <span className="text-muted-foreground">Assignee:</span>
                        <div className="mt-1 font-bold text-foreground">{task.assignee.name}</div>
                    </div>
                    <div>
                        <span className="text-muted-foreground">Due Date:</span>
                        <div className="mt-1 font-mono font-bold text-foreground">{task.dueDate}</div>
                    </div>
                </div>

                {/* Comments */}
                <div className="space-y-2 pt-2 border-t border-border">
                    <h4 className="text-xs font-bold text-foreground">Comments & Activity</h4>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            placeholder="Add a comment..."
                            value={newComment}
                            onChange={(e) => setNewComment(e.target.value)}
                            className="flex-1 rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                        />
                        <button className="rounded-xl bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground shadow-sm">
                            <Send className="h-3.5 w-3.5" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
