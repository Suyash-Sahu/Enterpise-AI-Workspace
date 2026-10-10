"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
    ArrowRight,
    CheckCircle2,
    AlertTriangle,
    Clock3,
    FolderKanban,
    ListTodo,
    Plus,
} from "lucide-react";

import { AiCommandBar, AiInsights } from "@/components/projects/AiInsights";
import { AiKillSwitch } from "@/components/projects/AiKillSwitch";
import { WorkService } from "@/services/work.service";
import type {
    DashboardDTO,
    ProjectDTO,
    TaskDTO,
    WorkStatus,
} from "@/types/project";

const STATUS_LABELS: Record<WorkStatus, string> = {
    backlog: "Backlog",
    open: "Todo",
    todo: "Todo",
    in_progress: "In Progress",
    in_review: "In Review",
    blocked: "Blocked",
    done: "Done",
    cancelled: "Cancelled",
};

export default function WorkPage() {
    const [projects, setProjects] = useState<ProjectDTO[]>([]);
    const [dashboard, setDashboard] = useState<DashboardDTO | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function loadWork() {
            try {
                setLoading(true);
                setError(null);

                const [projectsResult, dashboardResult] = await Promise.all([
                    WorkService.getProjects(),
                    WorkService.getDashboard(),
                ]);

                setProjects(projectsResult);
                setDashboard(dashboardResult);
            } catch (err) {
                console.error("Failed to load Work", err);
                setError("Unable to load your work right now.");
            } finally {
                setLoading(false);
            }
        }

        loadWork();
    }, []);

    const counts = dashboard?.counts ?? { open: 0, in_progress: 0, blocked: 0, done: 0 };

    if (loading) {
        return (
            <div className="space-y-6">
                <div>
                    <div className="h-8 w-48 animate-pulse rounded bg-muted" />
                    <div className="mt-2 h-4 w-72 animate-pulse rounded bg-muted" />
                </div>

                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {Array.from({ length: 4 }).map((_, index) => (
                        <div
                            key={index}
                            className="h-28 animate-pulse rounded-lg border bg-muted/30"
                        />
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-2xl font-semibold tracking-tight">
                        Work
                    </h1>

                    <p className="mt-1 text-sm text-muted-foreground">
                        Manage projects and work items from one place.
                    </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                    <AiKillSwitch />
                    <Link
                        href="/work/automations"
                        className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
                    >
                        Automations
                    </Link>
                    <Link
                        href="/work/inbox"
                        className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
                    >
                        AI Inbox
                    </Link>
                    <Link
                        href="/work/projects"
                        className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
                    >
                        <FolderKanban className="h-4 w-4" />
                        Projects
                    </Link>

                    <Link
                        href="/work/projects"
                        className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                    >
                        <Plus className="h-4 w-4" />
                        New Project
                    </Link>
                </div>
            </div>

            {error && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    {error}
                </div>
            )}

            <AiCommandBar />

            {/* Stats (server-side counts) */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard label="Open" value={counts.open} icon={<ListTodo className="h-5 w-5" />} />
                <StatCard label="In Progress" value={counts.in_progress} icon={<Clock3 className="h-5 w-5" />} />
                <StatCard label="Blocked" value={counts.blocked} icon={<AlertTriangle className="h-5 w-5" />} />
                <StatCard label="Done" value={counts.done} icon={<CheckCircle2 className="h-5 w-5" />} />
            </div>

            <AiInsights />

            {/* Projects */}
            <section className="space-y-4">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-lg font-semibold">
                            Projects
                        </h2>

                        <p className="text-sm text-muted-foreground">
                            Your active workspaces.
                        </p>
                    </div>

                    <Link
                        href="/work/projects"
                        className="inline-flex items-center gap-1 text-sm font-medium hover:underline"
                    >
                        View all
                        <ArrowRight className="h-4 w-4" />
                    </Link>
                </div>

                {projects.length === 0 ? (
                    <div className="rounded-lg border border-dashed p-8 text-center">
                        <FolderKanban className="mx-auto h-8 w-8 text-muted-foreground" />

                        <h3 className="mt-3 font-medium">
                            No projects yet
                        </h3>

                        <p className="mt-1 text-sm text-muted-foreground">
                            Create your first project to start organizing work.
                        </p>
                    </div>
                ) : (
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                        {projects.slice(0, 6).map((project) => (
                            <Link
                                key={project.id}
                                href={`/work/projects/${project.id}`}
                                className="rounded-lg border bg-card p-5 transition-colors hover:bg-accent/40"
                            >
                                <div className="flex items-start justify-between gap-4">
                                    <div className="min-w-0">
                                        <h3 className="truncate font-medium">
                                            {project.name}
                                        </h3>

                                        <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                                            {project.description ||
                                                "No description"}
                                        </p>
                                    </div>

                                    <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                                </div>

                                <div className="mt-4 text-xs text-muted-foreground">
                                    {project.status}
                                </div>
                            </Link>
                        ))}
                    </div>
                )}
            </section>

            <ItemSection title="Due today" items={dashboard?.due_today ?? []} empty="Nothing due today." />
            <ItemSection title="Overdue" items={dashboard?.overdue ?? []} empty="Nothing overdue." />
            <ItemSection title="Recently updated" items={dashboard?.recently_updated ?? []} empty="No work items yet." />
        </div>
    );
}

function StatCard({
    label,
    value,
    icon,
}: {
    label: string;
    value: number;
    icon: React.ReactNode;
}) {
    return (
        <div className="rounded-lg border bg-card p-5">
            <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                    {label}
                </span>

                <span className="text-muted-foreground">
                    {icon}
                </span>
            </div>

            <p className="mt-3 text-2xl font-semibold">
                {value}
            </p>
        </div>
    );
}

function ItemSection({
    title,
    items,
    empty,
}: {
    title: string;
    items: TaskDTO[];
    empty: string;
}) {
    return (
        <section className="space-y-3">
            <h2 className="text-lg font-semibold">{title}</h2>

            {items.length === 0 ? (
                <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                    {empty}
                </p>
            ) : (
                <div className="divide-y rounded-lg border">
                    {items.map((item) => (
                        <Link
                            key={item.id}
                            href={`/work/items/${item.id}`}
                            className="flex items-center justify-between gap-4 p-4 hover:bg-accent/40"
                        >
                            <div className="min-w-0">
                                <p className="truncate text-sm font-medium">{item.title}</p>
                                {item.due_date && (
                                    <p className="mt-1 text-xs text-muted-foreground">
                                        Due {new Date(item.due_date).toLocaleDateString()}
                                    </p>
                                )}
                            </div>
                            <div className="flex shrink-0 items-center gap-3">
                                <span className="rounded-full bg-muted px-2.5 py-1 text-xs">
                                    {STATUS_LABELS[item.status]}
                                </span>
                                <span className="text-xs capitalize text-muted-foreground">
                                    {item.priority}
                                </span>
                            </div>
                        </Link>
                    ))}
                </div>
            )}
        </section>
    );
}
