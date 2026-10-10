"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

import { WorkService } from "@/services/work.service";
import type {
    ProjectDTO,
    TaskDTO,
    WorkStatus,
} from "@/types/project";
import { bucketOf } from "@/types/project";

const COLUMNS: {
    status: WorkStatus;
    label: string;
}[] = [
        { status: "open", label: "Open" },
        { status: "in_progress", label: "In Progress" },
        { status: "blocked", label: "Blocked" },
        { status: "done", label: "Done" },
    ];

export default function ProjectBoardPage() {
    const params = useParams();
    const router = useRouter();

    const projectId = params.projectId as string;

    const [project, setProject] = useState<ProjectDTO | null>(null);
    const [tasks, setTasks] = useState<TaskDTO[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [updatingTaskId, setUpdatingTaskId] = useState<string | null>(null);

    useEffect(() => {
        async function loadBoard() {
            try {
                setLoading(true);
                setError(null);

                const [projectData, taskData] = await Promise.all([
                    WorkService.getProject(projectId),
                    WorkService.getWorkItems(projectId),
                ]);

                setProject(projectData);
                setTasks(taskData);
            } catch (err) {
                console.error(err);
                setError("Failed to load project board.");
            } finally {
                setLoading(false);
            }
        }

        if (projectId) {
            loadBoard();
        }
    }, [projectId]);

    const groupedTasks = useMemo(() => {
        return COLUMNS.reduce<Record<WorkStatus, TaskDTO[]>>(
            (groups, column) => {
                // in_review/backlog/todo fold into their board column
                groups[column.status] = tasks.filter(
                    (task) => bucketOf(task.status) === column.status,
                );

                return groups;
            },
            {
                backlog: [],
                open: [],
                todo: [],
                in_progress: [],
                in_review: [],
                blocked: [],
                done: [],
                cancelled: [],
            },
        );
    }, [tasks]);

    async function handleStatusChange(
        taskId: string,
        status: WorkStatus,
    ) {
        const currentTask = tasks.find((task) => task.id === taskId);

        if (!currentTask || currentTask.status === status) {
            return;
        }

        const previousStatus = currentTask.status;

        // Optimistic update
        setTasks((current) =>
            current.map((task) =>
                task.id === taskId
                    ? { ...task, status }
                    : task,
            ),
        );

        try {
            setUpdatingTaskId(taskId);

            const updatedTask = await WorkService.updateWorkItem(
                taskId,
                { status },
            );

            setTasks((current) =>
                current.map((task) =>
                    task.id === taskId ? updatedTask : task,
                ),
            );
        } catch (err) {
            console.error(err);

            // Rollback
            setTasks((current) =>
                current.map((task) =>
                    task.id === taskId
                        ? { ...task, status: previousStatus }
                        : task,
                ),
            );

            setError("Failed to update work item status.");
        } finally {
            setUpdatingTaskId(null);
        }
    }

    if (loading) {
        return (
            <main className="p-6">
                <div className="text-sm text-muted-foreground">
                    Loading board...
                </div>
            </main>
        );
    }

    if (error && !project) {
        return (
            <main className="p-6">
                <div className="rounded-lg border p-6">
                    <h1 className="text-lg font-semibold">
                        Unable to load board
                    </h1>

                    <p className="mt-2 text-sm text-muted-foreground">
                        {error}
                    </p>

                    <Link
                        href={`/work/projects/${projectId}`}
                        className="mt-4 inline-block text-sm underline"
                    >
                        Back to project
                    </Link>
                </div>
            </main>
        );
    }

    return (
        <main className="space-y-6 p-6">
            {/* Header */}
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <Link
                        href={`/work/projects/${projectId}`}
                        className="text-sm text-muted-foreground hover:underline"
                    >
                        ← {project?.name ?? "Project"}
                    </Link>

                    <h1 className="mt-2 text-2xl font-semibold">
                        Board
                    </h1>

                    <p className="mt-1 text-sm text-muted-foreground">
                        Manage work items by status.
                    </p>
                </div>

                <Link
                    href={`/work/projects/${projectId}/new`}
                    className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
                >
                    + New Work Item
                </Link>
            </div>

            {error && (
                <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
                    {error}
                </div>
            )}

            {/* Board */}
            <div className="grid gap-4 overflow-x-auto md:grid-cols-2 xl:grid-cols-4">
                {COLUMNS.map((column) => {
                    const columnTasks = groupedTasks[column.status];

                    return (
                        <section
                            key={column.status}
                            className="min-h-[500px] rounded-xl border bg-muted/20 p-3"
                        >
                            <div className="mb-4 flex items-center justify-between">
                                <h2 className="font-medium">
                                    {column.label}
                                </h2>

                                <span className="rounded-full bg-muted px-2 py-1 text-xs">
                                    {columnTasks.length}
                                </span>
                            </div>

                            <div className="space-y-3">
                                {columnTasks.map((task) => (
                                    <article
                                        key={task.id}
                                        className="rounded-lg border bg-background p-4 shadow-sm"
                                    >
                                        <button
                                            type="button"
                                            onClick={() =>
                                                router.push(`/work/items/${task.id}`)
                                            }
                                            className="w-full text-left"
                                        >
                                            <h3 className="font-medium">
                                                {task.title}
                                            </h3>

                                            {task.description && (
                                                <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                                                    {task.description}
                                                </p>
                                            )}

                                            <div className="mt-3 flex flex-wrap gap-2 text-xs">
                                                <span className="rounded-full border px-2 py-1">
                                                    {task.priority}
                                                </span>

                                                {task.assignee && (
                                                    <span className="rounded-full border px-2 py-1">
                                                        {task.assignee}
                                                    </span>
                                                )}
                                            </div>
                                        </button>

                                        <div className="mt-4">
                                            <label
                                                htmlFor={`status-${task.id}`}
                                                className="sr-only"
                                            >
                                                Change status
                                            </label>

                                            <select
                                                id={`status-${task.id}`}
                                                value={task.status}
                                                disabled={updatingTaskId === task.id}
                                                onChange={(event) =>
                                                    handleStatusChange(
                                                        task.id,
                                                        event.target.value as WorkStatus,
                                                    )
                                                }
                                                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                                            >
                                                {COLUMNS.map((option) => (
                                                    <option
                                                        key={option.status}
                                                        value={option.status}
                                                    >
                                                        {option.label}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                    </article>
                                ))}

                                {columnTasks.length === 0 && (
                                    <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                                        No work items
                                    </div>
                                )}
                            </div>
                        </section>
                    );
                })}
            </div>
        </main>
    );
}