"use client";

import { useProjectStore } from "@/stores/project.store";
import TaskCard from "./TaskCard";
import { Plus } from "lucide-react";

interface Props {
    onSelectTask: (taskId: string) => void;
}

const COLUMNS: { id: "Todo" | "In Progress" | "Review" | "Testing" | "Done"; label: string; color: string }[] = [
    { id: "Todo", label: "To Do", color: "border-muted text-muted-foreground" },
    { id: "In Progress", label: "In Progress", color: "border-info/50 text-info" },
    { id: "Review", label: "Code Review", color: "border-primary/50 text-primary" },
    { id: "Testing", label: "Testing & QA", color: "border-warning/50 text-warning" },
    { id: "Done", label: "Completed", color: "border-success/50 text-success" },
];

export default function KanbanBoard({ onSelectTask }: Props) {
    const { tasks, moveTaskStatus } = useProjectStore();

    return (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5 overflow-x-auto pb-4">
            {COLUMNS.map((col) => {
                const columnTasks = tasks.filter((t) => t.status === col.id);
                return (
                    <div key={col.id} className="flex flex-col gap-3 rounded-2xl border border-border bg-surface/50 p-3 min-w-[240px]">
                        {/* Column Header */}
                        <div className={`flex items-center justify-between border-b pb-2 px-1 font-mono text-xs font-bold ${col.color}`}>
                            <span>{col.label}</span>
                            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{columnTasks.length}</span>
                        </div>

                        {/* Cards Container */}
                        <div className="flex-1 space-y-2.5 min-h-[300px]">
                            {columnTasks.map((task) => (
                                <TaskCard key={task.id} task={task} onClick={() => onSelectTask(task.id)} />
                            ))}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
