"use client";

import { CentralTask } from "@/data/central-store";
import { PriorityBadge } from "@/components/shared/BadgeVariants";
import { Clock, MessageSquare, Tag } from "lucide-react";

interface Props {
    task: CentralTask;
    onClick: () => void;
}

export default function TaskCard({ task, onClick }: Props) {
    return (
        <div
            onClick={onClick}
            className="group cursor-pointer rounded-xl border border-border bg-surface p-3.5 shadow-sm space-y-2.5 transition-all hover:border-primary/50 hover:shadow-md"
        >
            <div className="flex items-start justify-between gap-2">
                <h4 className="text-xs font-bold text-foreground group-hover:text-primary transition-colors leading-snug">
                    {task.title}
                </h4>
                <PriorityBadge priority={task.priority} />
            </div>

            <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">{task.description}</p>

            {/* Labels */}
            <div className="flex flex-wrap gap-1">
                {task.labels.map((lbl) => (
                    <span key={lbl} className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] font-semibold text-muted-foreground">
                        #{lbl}
                    </span>
                ))}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between pt-1 border-t border-border text-xs font-mono text-muted-foreground">
                <div className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    <span>{task.dueDate}</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-0.5">
                        <MessageSquare className="h-3 w-3" />
                        <span>{task.commentsCount}</span>
                    </div>
                    <div className="h-5 w-5 rounded-full bg-primary/20 flex items-center justify-center font-bold text-[10px] text-primary">
                        {task.assignee.name.charAt(0)}
                    </div>
                </div>
            </div>
        </div>
    );
}
