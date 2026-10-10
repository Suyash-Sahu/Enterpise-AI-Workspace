"use client";

import { useState } from "react";
import PageHeader from "@/components/shared/PageHeader";
import CreateProjectModal from "@/components/projects/CreateProjectModal";
import TaskModal from "@/components/projects/TaskModal";
import KanbanBoard from "@/components/projects/KanbanBoard";
import { useProjects, useTasks } from "@/hooks/useProjects";
import { Plus, LayoutGrid, ListTodo, Calendar, BarChart3, FolderGit2, Settings, Sparkles, Filter } from "lucide-react";

export default function ProjectsPage() {
    const [activeTab, setActiveTab] = useState<"overview" | "board" | "backlog" | "sprints" | "calendar" | "analytics" | "files" | "settings">("board");
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

    const { data: projects, isLoading: isProjectsLoading } = useProjects();
    const { data: tasks, isLoading: isTasksLoading } = useTasks();

    return (
        <div className="space-y-6">
            <PageHeader
                title="Projects & Sprints"
                description="Manage enterprise AI task graphs, Kanban boards, and sprint milestones."
                breadcrumbs={[{ label: "Workspace" }, { label: "Projects" }]}
                actions={
                    <button
                        onClick={() => setIsCreateOpen(true)}
                        className="flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md transition-all"
                    >
                        <Plus className="h-4 w-4" />
                        <span>Create Project</span>
                    </button>
                }
            />

            {/* View Tabs */}
            <div className="flex items-center gap-1.5 overflow-x-auto border-b border-border pb-3">
                {[
                    { id: "board", label: "Kanban Board", icon: LayoutGrid },
                    { id: "overview", label: "Overview", icon: FolderGit2 },
                    { id: "backlog", label: "Backlog", icon: ListTodo },
                    { id: "calendar", label: "Schedule", icon: Calendar },
                    { id: "analytics", label: "Analytics", icon: BarChart3 },
                    { id: "settings", label: "Settings", icon: Settings },
                ].map((tab) => {
                    const Icon = tab.icon;
                    const isSelected = activeTab === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id as any)}
                            className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all ${
                                isSelected
                                    ? "bg-primary text-primary-foreground shadow-md font-bold"
                                    : "border border-border bg-surface text-muted-foreground hover:bg-muted/50"
                            }`}
                        >
                            <Icon className="h-3.5 w-3.5" />
                            <span>{tab.label}</span>
                        </button>
                    );
                })}
            </div>

            {/* Main Content Area */}
            {isProjectsLoading || isTasksLoading ? (
                <div className="rounded-2xl border border-border bg-surface p-6 text-xs text-muted-foreground animate-pulse">
                    Loading projects and tasks from FastAPI backend...
                </div>
            ) : activeTab === "board" ? (
                <div className="space-y-4">
                    <KanbanBoard onSelectTask={(taskId) => setSelectedTaskId(taskId)} />
                </div>
            ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {projects?.map((proj) => (
                        <div key={proj.id} className="rounded-2xl border border-border bg-surface p-5 space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="rounded-full bg-primary/10 px-3 py-1 font-mono text-xs font-bold text-primary">
                                    {proj.status}
                                </span>
                            </div>
                            <h4 className="text-sm font-bold text-foreground">{proj.name}</h4>
                            <p className="text-xs text-muted-foreground leading-relaxed">{proj.description}</p>
                        </div>
                    ))}
                </div>
            )}

            {/* Modals */}
            <CreateProjectModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} onCreate={() => {}} />
            <TaskModal taskId={selectedTaskId} onClose={() => setSelectedTaskId(null)} />
        </div>
    );
}
