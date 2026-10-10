"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { WorkService } from "@/services/work.service";
import { ItemActivity } from "@/components/projects/ItemActivity";
import { ItemComments } from "@/components/projects/ItemComments";

import type {
    TaskDTO,
    TaskDependencyDTO,
    WorkPriority,
    WorkStatus,
} from "@/types/project";

const STATUS_OPTIONS: {
    value: WorkStatus;
    label: string;
}[] = [
        {
            value: "open",
            label: "Open",
        },
        {
            value: "in_progress",
            label: "In Progress",
        },
        {
            value: "blocked",
            label: "Blocked",
        },
        {
            value: "done",
            label: "Done",
        },
        {
            value: "cancelled",
            label: "Cancelled",
        },
    ];

const PRIORITY_OPTIONS: {
    value: WorkPriority;
    label: string;
}[] = [
        {
            value: "low",
            label: "Low",
        },
        {
            value: "medium",
            label: "Medium",
        },
        {
            value: "high",
            label: "High",
        },
        {
            value: "urgent",
            label: "Urgent",
        },
    ];

export default function WorkItemDetailPage() {
    const params = useParams();

    const itemId = String(params.itemId);

    const [task, setTask] = useState<TaskDTO | null>(
        null,
    );

    const [allTasks, setAllTasks] = useState<TaskDTO[]>(
        [],
    );

    const [dependencies, setDependencies] =
        useState<TaskDependencyDTO[]>([]);

    const [selectedDependency, setSelectedDependency] =
        useState("");

    const [title, setTitle] = useState("");
    const [description, setDescription] =
        useState("");

    const [status, setStatus] =
        useState<WorkStatus>("open");

    const [priority, setPriority] =
        useState<WorkPriority>("medium");

    const [assignee, setAssignee] = useState("");

    const [dueDate, setDueDate] = useState("");

    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    const [dependencyLoading, setDependencyLoading] =
        useState(false);

    const [error, setError] =
        useState<string | null>(null);

    const [dependencyError, setDependencyError] =
        useState<string | null>(null);

    /*
     * Load the work item and dependency information.
     */
    useEffect(() => {
        let cancelled = false;

        async function loadData() {
            try {
                setLoading(true);
                setError(null);
                setDependencyError(null);

                const [
                    taskData,
                    taskList,
                    dependencyData,
                ] = await Promise.all([
                    WorkService.getWorkItem(itemId),
                    WorkService.getWorkItems(),
                    WorkService.getDependencies(itemId),
                ]);

                if (cancelled) {
                    return;
                }

                setTask(taskData);
                setAllTasks(taskList);
                setDependencies(dependencyData);

                setTitle(taskData.title);
                setDescription(
                    taskData.description ?? "",
                );

                setStatus(taskData.status);
                setPriority(taskData.priority);

                setAssignee(
                    taskData.assignee ?? "",
                );

                /*
                 * Convert backend datetime into
                 * YYYY-MM-DD for the date input.
                 */
                if (taskData.due_date) {
                    const date =
                        new Date(taskData.due_date);

                    if (
                        !Number.isNaN(
                            date.getTime(),
                        )
                    ) {
                        setDueDate(
                            date
                                .toISOString()
                                .slice(0, 10),
                        );
                    } else {
                        setDueDate("");
                    }
                } else {
                    setDueDate("");
                }
            } catch (err) {
                if (cancelled) {
                    return;
                }

                console.error(err);

                setError(
                    "Failed to load work item.",
                );
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        loadData();

        return () => {
            cancelled = true;
        };
    }, [itemId]);

    /*
     * Tasks that can be selected as dependencies.
     *
     * We exclude:
     * - the current task itself
     * - tasks that are already dependencies
     */
    const availableDependencyTasks =
        useMemo(() => {
            const dependencyIds = new Set(
                dependencies.map(
                    (dependency) =>
                        dependency.depends_on_task_id,
                ),
            );

            return allTasks.filter(
                (candidate) =>
                    candidate.id !== itemId &&
                    !dependencyIds.has(
                        candidate.id,
                    ),
            );
        }, [
            allTasks,
            dependencies,
            itemId,
        ]);

    /*
     * Save work item.
     */
    async function handleSave() {
        try {
            setSaving(true);
            setError(null);

            const updated =
                await WorkService.updateWorkItem(
                    itemId,
                    {
                        title,
                        description:
                            description || undefined,
                        status,
                        priority,
                        assignee:
                            assignee || undefined,

                        /*
                         * Keep this as a date-only
                         * string plus midnight.
                         *
                         * This avoids the previous
                         * Invalid Date / RangeError
                         * problem.
                         */
                        due_date: dueDate
                            ? `${dueDate}T00:00:00`
                            : undefined,
                    },
                );

            setTask(updated);

            /*
             * Synchronize local form state with
             * the saved backend response.
             */
            setTitle(updated.title);

            setDescription(
                updated.description ?? "",
            );

            setStatus(updated.status);
            setPriority(updated.priority);

            setAssignee(
                updated.assignee ?? "",
            );

            if (updated.due_date) {
                const parsedDate =
                    new Date(
                        updated.due_date,
                    );

                if (
                    !Number.isNaN(
                        parsedDate.getTime(),
                    )
                ) {
                    setDueDate(
                        parsedDate
                            .toISOString()
                            .slice(0, 10),
                    );
                }
            } else {
                setDueDate("");
            }
        } catch (err) {
            console.error(err);

            setError(
                "Failed to save work item.",
            );
        } finally {
            setSaving(false);
        }
    }

    /*
     * Add dependency.
     */
    async function handleAddDependency() {
        if (!selectedDependency) {
            return;
        }

        try {
            setDependencyLoading(true);
            setDependencyError(null);

            const dependency =
                await WorkService.addDependency(
                    itemId,
                    selectedDependency,
                );

            setDependencies((current) => [
                ...current,
                dependency,
            ]);

            /*
             * Update the task's local depends_on
             * list as well.
             */
            setTask((current) => {
                if (!current) {
                    return current;
                }

                return {
                    ...current,
                    depends_on: [
                        ...current.depends_on,
                        dependency.depends_on_task_id,
                    ],
                };
            });

            setSelectedDependency("");
        } catch (err) {
            console.error(err);

            // Server rejects self/circular/foreign links with a specific reason.
            setDependencyError(
                err instanceof Error && err.message
                    ? err.message
                    : "Failed to add dependency.",
            );
        } finally {
            setDependencyLoading(false);
        }
    }

    /*
     * Remove dependency.
     */
    async function handleRemoveDependency(
        dependsOnTaskId: string,
    ) {
        try {
            setDependencyLoading(true);
            setDependencyError(null);

            await WorkService.removeDependency(
                itemId,
                dependsOnTaskId,
            );

            setDependencies((current) =>
                current.filter(
                    (dependency) =>
                        dependency.depends_on_task_id !==
                        dependsOnTaskId,
                ),
            );

            /*
             * Keep local task state synchronized.
             */
            setTask((current) => {
                if (!current) {
                    return current;
                }

                return {
                    ...current,
                    depends_on:
                        current.depends_on.filter(
                            (id) =>
                                id !==
                                dependsOnTaskId,
                        ),
                };
            });
        } catch (err) {
            console.error(err);

            setDependencyError(
                "Failed to remove dependency.",
            );
        } finally {
            setDependencyLoading(false);
        }
    }

    /*
     * Loading state.
     */
    if (loading) {
        return (
            <main className="p-6">
                <p className="text-sm text-muted-foreground">
                    Loading work item...
                </p>
            </main>
        );
    }

    /*
     * Error state.
     */
    if (!task) {
        return (
            <main className="space-y-4 p-6">
                <h1 className="text-2xl font-semibold">
                    Work item not found
                </h1>

                <p className="text-sm text-muted-foreground">
                    {error ??
                        "The requested work item could not be found."}
                </p>

                <Link
                    href="/work/my-work"
                    className="inline-flex rounded-md border px-4 py-2 text-sm hover:bg-muted"
                >
                    Back to My Work
                </Link>
            </main>
        );
    }

    return (
        <main className="mx-auto max-w-5xl space-y-6 p-6">
            {/* Header */}
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                    <Link
                        href="/work/my-work"
                        className="text-sm text-muted-foreground hover:underline"
                    >
                        ← Back to My Work
                    </Link>

                    <h1 className="mt-2 text-2xl font-semibold">
                        Work Item
                    </h1>
                </div>

                <button
                    type="button"
                    onClick={handleSave}
                    disabled={saving}
                    className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {saving
                        ? "Saving..."
                        : "Save changes"}
                </button>
            </div>

            {/* Error */}
            {error && (
                <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
                    {error}
                </div>
            )}

            {/* Main information */}
            <section className="rounded-xl border p-5">
                <div className="space-y-5">
                    {/* Title */}
                    <div>
                        <label
                            htmlFor="title"
                            className="text-sm font-medium"
                        >
                            Title
                        </label>

                        <input
                            id="title"
                            value={title}
                            onChange={(event) =>
                                setTitle(
                                    event.target.value,
                                )
                            }
                            className="mt-2 w-full rounded-md border bg-background px-3 py-2 text-sm"
                        />
                    </div>

                    {/* Description */}
                    <div>
                        <label
                            htmlFor="description"
                            className="text-sm font-medium"
                        >
                            Description
                        </label>

                        <textarea
                            id="description"
                            value={description}
                            onChange={(event) =>
                                setDescription(
                                    event.target.value,
                                )
                            }
                            rows={6}
                            className="mt-2 w-full resize-y rounded-md border bg-background px-3 py-2 text-sm"
                            placeholder="Describe this work item..."
                        />
                    </div>

                    {/* Status / Priority */}
                    <div className="grid gap-4 md:grid-cols-2">
                        <div>
                            <label
                                htmlFor="status"
                                className="text-sm font-medium"
                            >
                                Status
                            </label>

                            <select
                                id="status"
                                value={status}
                                onChange={(event) =>
                                    setStatus(
                                        event.target
                                            .value as WorkStatus,
                                    )
                                }
                                className="mt-2 w-full rounded-md border bg-background px-3 py-2 text-sm"
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
                                            {
                                                option.label
                                            }
                                        </option>
                                    ),
                                )}
                            </select>
                        </div>

                        <div>
                            <label
                                htmlFor="priority"
                                className="text-sm font-medium"
                            >
                                Priority
                            </label>

                            <select
                                id="priority"
                                value={priority}
                                onChange={(event) =>
                                    setPriority(
                                        event.target
                                            .value as WorkPriority,
                                    )
                                }
                                className="mt-2 w-full rounded-md border bg-background px-3 py-2 text-sm"
                            >
                                {PRIORITY_OPTIONS.map(
                                    (option) => (
                                        <option
                                            key={
                                                option.value
                                            }
                                            value={
                                                option.value
                                            }
                                        >
                                            {
                                                option.label
                                            }
                                        </option>
                                    ),
                                )}
                            </select>
                        </div>
                    </div>

                    {/* Assignee / Due date */}
                    <div className="grid gap-4 md:grid-cols-2">
                        <div>
                            <label
                                htmlFor="assignee"
                                className="text-sm font-medium"
                            >
                                Assignee
                            </label>

                            <input
                                id="assignee"
                                value={assignee}
                                onChange={(event) =>
                                    setAssignee(
                                        event.target
                                            .value,
                                    )
                                }
                                className="mt-2 w-full rounded-md border bg-background px-3 py-2 text-sm"
                                placeholder="Assignee"
                            />
                        </div>

                        <div>
                            <label
                                htmlFor="dueDate"
                                className="text-sm font-medium"
                            >
                                Due date
                            </label>

                            <input
                                id="dueDate"
                                type="date"
                                value={dueDate}
                                onChange={(event) =>
                                    setDueDate(
                                        event.target
                                            .value,
                                    )
                                }
                                className="mt-2 w-full rounded-md border bg-background px-3 py-2 text-sm"
                            />
                        </div>
                    </div>
                </div>
            </section>

            {/* Dependencies */}
            <section className="rounded-xl border p-5">
                <div>
                    <h2 className="font-semibold">
                        Dependencies
                    </h2>

                    <p className="mt-1 text-sm text-muted-foreground">
                        Work items that must be completed
                        before this item.
                    </p>
                </div>

                {/* Dependency error */}
                {dependencyError && (
                    <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm">
                        {dependencyError}
                    </div>
                )}

                {/* Existing dependencies */}
                <div className="mt-4 space-y-2">
                    {dependencies.length === 0 ? (
                        <div className="rounded-md border border-dashed p-4">
                            <p className="text-sm text-muted-foreground">
                                No dependencies.
                            </p>
                        </div>
                    ) : (
                        dependencies.map(
                            (dependency) => {
                                const dependencyTask =
                                    allTasks.find(
                                        (candidate) =>
                                            candidate.id ===
                                            dependency.depends_on_task_id,
                                    );

                                return (
                                    <div
                                        key={
                                            dependency.depends_on_task_id
                                        }
                                        className="flex flex-col gap-3 rounded-md border px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
                                    >
                                        <div className="min-w-0">
                                            <p className="text-xs text-muted-foreground">
                                                Depends on
                                            </p>

                                            <Link
                                                href={`/work/items/${dependency.depends_on_task_id}`}
                                                className="text-sm font-medium hover:underline"
                                            >
                                                {dependencyTask?.title ??
                                                    dependency.depends_on_task_id}
                                            </Link>

                                            {dependencyTask && (
                                                <p className="mt-1 text-xs text-muted-foreground">
                                                    Status:{" "}
                                                    {
                                                        dependencyTask.status
                                                    }
                                                </p>
                                            )}
                                        </div>

                                        <button
                                            type="button"
                                            disabled={
                                                dependencyLoading
                                            }
                                            onClick={() =>
                                                handleRemoveDependency(
                                                    dependency.depends_on_task_id,
                                                )
                                            }
                                            className="rounded-md border px-3 py-1.5 text-xs hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                                        >
                                            Remove
                                        </button>
                                    </div>
                                );
                            },
                        )
                    )}
                </div>

                {/* Add dependency */}
                <div className="mt-5 border-t pt-5">
                    <label
                        htmlFor="dependency"
                        className="text-sm font-medium"
                    >
                        Add dependency
                    </label>

                    <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                        <select
                            id="dependency"
                            value={
                                selectedDependency
                            }
                            onChange={(event) =>
                                setSelectedDependency(
                                    event.target
                                        .value,
                                )
                            }
                            disabled={
                                dependencyLoading ||
                                availableDependencyTasks.length ===
                                0
                            }
                            className="flex-1 rounded-md border bg-background px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            <option value="">
                                Select a work item...
                            </option>

                            {availableDependencyTasks.map(
                                (availableTask) => (
                                    <option
                                        key={
                                            availableTask.id
                                        }
                                        value={
                                            availableTask.id
                                        }
                                    >
                                        {
                                            availableTask.title
                                        }
                                    </option>
                                ),
                            )}
                        </select>

                        <button
                            type="button"
                            onClick={
                                handleAddDependency
                            }
                            disabled={
                                dependencyLoading ||
                                !selectedDependency
                            }
                            className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {dependencyLoading
                                ? "Saving..."
                                : "Add dependency"}
                        </button>
                    </div>

                    {availableDependencyTasks.length ===
                        0 && (
                            <p className="mt-2 text-xs text-muted-foreground">
                                No other work items are available
                                to add as dependencies.
                            </p>
                        )}
                </div>
            </section>

            <ItemComments taskId={itemId} />

            <ItemActivity taskId={itemId} refreshKey={task?.updated_at} />

            {/* Metadata */}
            <section className="rounded-xl border p-5">
                <h2 className="font-semibold">
                    Metadata
                </h2>

                <div className="mt-4 grid gap-4 text-sm md:grid-cols-2">
                    <div>
                        <p className="text-xs text-muted-foreground">
                            Work item ID
                        </p>

                        <p className="mt-1 break-all">
                            {task.id}
                        </p>
                    </div>

                    <div>
                        <p className="text-xs text-muted-foreground">
                            Project ID
                        </p>

                        <p className="mt-1 break-all">
                            {task.project_id ??
                                "No project"}
                        </p>
                    </div>

                    <div>
                        <p className="text-xs text-muted-foreground">
                            Created by
                        </p>

                        <p className="mt-1">
                            {task.created_by}
                        </p>
                    </div>

                    <div>
                        <p className="text-xs text-muted-foreground">
                            Source
                        </p>

                        <p className="mt-1">
                            {task.source_type}
                        </p>
                    </div>

                    <div>
                        <p className="text-xs text-muted-foreground">
                            Created
                        </p>

                        <p className="mt-1">
                            {new Date(
                                task.created_at,
                            ).toLocaleString()}
                        </p>
                    </div>

                    <div>
                        <p className="text-xs text-muted-foreground">
                            Updated
                        </p>

                        <p className="mt-1">
                            {new Date(
                                task.updated_at,
                            ).toLocaleString()}
                        </p>
                    </div>
                </div>
            </section>
        </main>
    );
}

