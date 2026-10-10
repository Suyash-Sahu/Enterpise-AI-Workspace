"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { WorkService } from "@/services/work.service";
import type {
    ProjectDTO,
    TaskDTO,
    WorkStatus,
} from "@/types/project";

const STATUS_OPTIONS: {
    value: WorkStatus;
    label: string;
}[] = [
        { value: "open", label: "Open" },
        { value: "in_progress", label: "In Progress" },
        { value: "blocked", label: "Blocked" },
        { value: "done", label: "Done" },
        { value: "cancelled", label: "Cancelled" },
    ];

export default function MyWorkPage() {
    const [tasks, setTasks] = useState<TaskDTO[]>([]);
    const [projects, setProjects] = useState<ProjectDTO[]>([]);

    const [statusFilter, setStatusFilter] =
        useState<WorkStatus | "all">("all");

    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const [error, setError] = useState<string | null>(null);

    const [updatingTaskId, setUpdatingTaskId] =
        useState<string | null>(null);

    const [search, setSearch] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");

    /*
     * Debounce search input.
     *
     * This prevents an API request on every single keystroke.
     */
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(search);
        }, 300);

        return () => {
            clearTimeout(timer);
        };
    }, [search]);

    /*
     * Load projects and work items.
     *
     * Important:
     * - Initial load shows the full-page loading state.
     * - Search/filter refresh does NOT replace the page.
     *   This keeps the search input mounted and preserves focus.
     */
    useEffect(() => {
        let cancelled = false;

        async function loadWork() {
            try {
                setError(null);

                /*
                 * Only show the full-page loading screen
                 * when we have not loaded anything yet.
                 */
                if (tasks.length === 0) {
                    setLoading(true);
                } else {
                    setRefreshing(true);
                }

                const [projectData, taskData] =
                    await Promise.all([
                        WorkService.getProjects(),

                        WorkService.getWorkItems(undefined, {
                            search:
                                debouncedSearch.trim() || undefined,

                            status:
                                statusFilter === "all"
                                    ? undefined
                                    : statusFilter,
                        }),
                    ]);

                if (cancelled) {
                    return;
                }

                setProjects(projectData);
                setTasks(taskData);
            } catch (err) {
                if (cancelled) {
                    return;
                }

                console.error(err);

                setError(
                    "Failed to load your work.",
                );
            } finally {
                if (!cancelled) {
                    setLoading(false);
                    setRefreshing(false);
                }
            }
        }

        loadWork();

        return () => {
            cancelled = true;
        };
    }, [debouncedSearch, statusFilter]);

    /*
     * Map project IDs to project names.
     */
    const projectMap = useMemo(() => {
        return new Map(
            projects.map((project) => [
                project.id,
                project.name,
            ]),
        );
    }, [projects]);

    /*
     * The backend already performs search and status filtering,
     * so the returned tasks are the final list.
     */
    const filteredTasks = tasks;

    /*
     * Calculate summary statistics.
     *
     * These statistics are based on the currently loaded tasks.
     */
    const stats = useMemo(() => {
        return {
            total: tasks.length,

            open: tasks.filter(
                (task) => task.status === "open",
            ).length,

            inProgress: tasks.filter(
                (task) => task.status === "in_progress",
            ).length,

            blocked: tasks.filter(
                (task) => task.status === "blocked",
            ).length,

            done: tasks.filter(
                (task) => task.status === "done",
            ).length,
        };
    }, [tasks]);

    /*
     * Update task status.
     *
     * Uses an optimistic update so the UI changes immediately.
     * If the API fails, the previous status is restored.
     */
    async function handleStatusChange(
        task: TaskDTO,
        status: WorkStatus,
    ) {
        if (task.status === status) {
            return;
        }

        const previousStatus = task.status;

        /*
         * Optimistic update.
         */
        setTasks((current) =>
            current.map((item) =>
                item.id === task.id
                    ? {
                        ...item,
                        status,
                    }
                    : item,
            ),
        );

        try {
            setUpdatingTaskId(task.id);
            setError(null);

            const updated =
                await WorkService.updateWorkItem(
                    task.id,
                    {
                        status,
                    },
                );

            setTasks((current) =>
                current.map((item) =>
                    item.id === task.id
                        ? updated
                        : item,
                ),
            );
        } catch (err) {
            console.error(err);

            /*
             * Roll back optimistic update.
             */
            setTasks((current) =>
                current.map((item) =>
                    item.id === task.id
                        ? {
                            ...item,
                            status: previousStatus,
                        }
                        : item,
                ),
            );

            setError(
                "Failed to update work item status.",
            );
        } finally {
            setUpdatingTaskId(null);
        }
    }

    /*
     * Initial loading state only.
     *
     * Search/filter refreshes do NOT enter this block
     * because the existing tasks keep the page mounted.
     */
    if (loading) {
        return (
            <main className="space-y-6 p-6">
                <div>
                    <h1 className="text-2xl font-semibold">
                        My Work
                    </h1>

                    <p className="mt-1 text-sm text-muted-foreground">
                        Work items across your workspace.
                    </p>
                </div>

                <div className="rounded-xl border p-6">
                    <p className="text-sm text-muted-foreground">
                        Loading your work...
                    </p>
                </div>
            </main>
        );
    }

    return (
        <main className="space-y-6 p-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-semibold">
                    My Work
                </h1>

                <p className="mt-1 text-sm text-muted-foreground">
                    Work items across your workspace.
                </p>
            </div>

            {/* Error */}
            {error && (
                <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
                    {error}
                </div>
            )}

            {/* Stats */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                {/* Total */}
                <button
                    type="button"
                    onClick={() => setStatusFilter("all")}
                    className="rounded-xl border bg-background p-4 text-left hover:bg-muted/50"
                >
                    <p className="text-sm text-muted-foreground">
                        Total
                    </p>

                    <p className="mt-1 text-2xl font-semibold">
                        {stats.total}
                    </p>
                </button>

                {/* Open */}
                <button
                    type="button"
                    onClick={() => setStatusFilter("open")}
                    className="rounded-xl border bg-background p-4 text-left hover:bg-muted/50"
                >
                    <p className="text-sm text-muted-foreground">
                        Open
                    </p>

                    <p className="mt-1 text-2xl font-semibold">
                        {stats.open}
                    </p>
                </button>

                {/* In Progress */}
                <button
                    type="button"
                    onClick={() =>
                        setStatusFilter("in_progress")
                    }
                    className="rounded-xl border bg-background p-4 text-left hover:bg-muted/50"
                >
                    <p className="text-sm text-muted-foreground">
                        In Progress
                    </p>

                    <p className="mt-1 text-2xl font-semibold">
                        {stats.inProgress}
                    </p>
                </button>

                {/* Blocked */}
                <button
                    type="button"
                    onClick={() =>
                        setStatusFilter("blocked")
                    }
                    className="rounded-xl border bg-background p-4 text-left hover:bg-muted/50"
                >
                    <p className="text-sm text-muted-foreground">
                        Blocked
                    </p>

                    <p className="mt-1 text-2xl font-semibold">
                        {stats.blocked}
                    </p>
                </button>

                {/* Done */}
                <button
                    type="button"
                    onClick={() => setStatusFilter("done")}
                    className="rounded-xl border bg-background p-4 text-left hover:bg-muted/50"
                >
                    <p className="text-sm text-muted-foreground">
                        Done
                    </p>

                    <p className="mt-1 text-2xl font-semibold">
                        {stats.done}
                    </p>
                </button>
            </div>

            {/* Work items header */}
            <div>
                <h2 className="font-semibold">
                    Work items
                </h2>

                <p className="text-sm text-muted-foreground">
                    {filteredTasks.length} item
                    {filteredTasks.length === 1
                        ? ""
                        : "s"}
                </p>
            </div>

            {/* Search + Filter */}
            <div className="flex flex-col gap-3 md:flex-row md:items-center">
                {/* Search */}
                <div className="relative flex-1">
                    <input
                        value={search}
                        onChange={(event) =>
                            setSearch(event.target.value)
                        }
                        placeholder="Search work items..."
                        className="w-full rounded-md border bg-background px-3 py-2 pr-24 text-sm"
                    />

                    {refreshing && (
                        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                            Searching...
                        </span>
                    )}
                </div>

                {/* Status filter */}
                <select
                    value={statusFilter}
                    onChange={(event) =>
                        setStatusFilter(
                            event.target.value as
                            | WorkStatus
                            | "all",
                        )
                    }
                    className="rounded-md border bg-background px-3 py-2 text-sm md:w-48"
                >
                    <option value="all">
                        All statuses
                    </option>

                    {STATUS_OPTIONS.map((option) => (
                        <option
                            key={option.value}
                            value={option.value}
                        >
                            {option.label}
                        </option>
                    ))}
                </select>
            </div>

            {/* Work list */}
            {filteredTasks.length === 0 ? (
                <div className="rounded-xl border border-dashed p-10 text-center">
                    <h3 className="font-medium">
                        {search.trim()
                            ? "No matching work items"
                            : "No work items"}
                    </h3>

                    <p className="mt-1 text-sm text-muted-foreground">
                        {search.trim()
                            ? "Try a different search term."
                            : "Create a work item from a project to see it here."}
                    </p>
                </div>
            ) : (
                <div className="overflow-hidden rounded-xl border">
                    <div className="divide-y">
                        {filteredTasks.map((task) => (
                            <div
                                key={task.id}
                                className="flex flex-col gap-4 p-4 md:flex-row md:items-center md:justify-between"
                            >
                                {/* Work item information */}
                                <Link
                                    href={`/ work / items / ${task.id} `}
                                    className="min-w-0 flex-1"
                                >
                                    <h3 className="font-medium hover:underline">
                                        {task.title}
                                    </h3>

                                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                                        {/* Project */}
                                        {task.project_id && (
                                            <span className="rounded-full border px-2 py-1">
                                                {projectMap.get(
                                                    task.project_id,
                                                ) ??
                                                    "Unknown project"}
                                            </span>
                                        )}

                                        {/* Priority */}
                                        <span className="rounded-full border px-2 py-1">
                                            {task.priority}
                                        </span>

                                        {/* Assignee */}
                                        {task.assignee && (
                                            <span className="rounded-full border px-2 py-1">
                                                {task.assignee}
                                            </span>
                                        )}

                                        {/* Due date */}
                                        {task.due_date && (
                                            <span className="rounded-full border px-2 py-1">
                                                Due{" "}
                                                {new Date(
                                                    task.due_date,
                                                ).toLocaleDateString()}
                                            </span>
                                        )}
                                    </div>
                                </Link>

                                {/* Status */}
                                <select
                                    value={task.status}
                                    disabled={
                                        updatingTaskId ===
                                        task.id
                                    }
                                    onChange={(event) =>
                                        handleStatusChange(
                                            task,
                                            event.target
                                                .value as WorkStatus,
                                        )
                                    }
                                    className="rounded-md border bg-background px-3 py-2 text-sm md:w-40"
                                >
                                    {STATUS_OPTIONS.map(
                                        (option) => (
                                            <option
                                                key={
                                                    option.value
                                                }
                                                value={
                                                    option.value
                                                }
                                            >
                                                {option.label}
                                            </option>
                                        ),
                                    )}
                                </select>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </main>
    );
}

