"use client";

import { FormEvent, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
    ArrowLeft,
    Loader2,
} from "lucide-react";

import { WorkService } from "@/services/work.service";

export default function NewWorkItemPage() {
    const params = useParams();
    const router = useRouter();

    const projectId = params.projectId as string;

    const [title, setTitle] = useState("");
    const [description, setDescription] =
        useState("");
    const [assignee, setAssignee] =
        useState("");

    const [priority, setPriority] =
        useState<
            "low" | "medium" | "high" | "urgent"
        >("medium");

    const [dueDate, setDueDate] =
        useState("");

    const [saving, setSaving] = useState(false);
    const [error, setError] =
        useState<string | null>(null);

    async function handleSubmit(
        event: FormEvent<HTMLFormElement>
    ) {
        event.preventDefault();

        if (!title.trim()) {
            setError("Work item title is required.");
            return;
        }

        try {
            setSaving(true);
            setError(null);

            const task =
                await WorkService.createWorkItem({
                    title: title.trim(),
                    description:
                        description.trim() || undefined,
                    project_id: projectId,
                    assignee:
                        assignee.trim() || undefined,
                    priority,
                    due_date: dueDate
                        ? new Date(dueDate).toISOString()
                        : undefined,
                });

            router.push(
                `/work/projects/${projectId}`
            );
        } catch (err) {
            console.error(
                "Failed to create work item:",
                err
            );

            setError(
                err instanceof Error
                    ? err.message
                    : "Failed to create work item"
            );
        } finally {
            setSaving(false);
        }
    }

    return (
        <main className="max-w-2xl space-y-6 p-6">
            <Link
                href={`/work/projects/${projectId}`}
                className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
            >
                <ArrowLeft className="h-4 w-4" />

                Back to project
            </Link>

            <div>
                <h1 className="text-2xl font-semibold">
                    New work item
                </h1>

                <p className="mt-1 text-sm text-muted-foreground">
                    Add a task to this project.
                </p>
            </div>

            <form
                onSubmit={handleSubmit}
                className="space-y-5 rounded-xl border p-6"
            >
                {error && (
                    <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                        {error}
                    </div>
                )}

                <div className="space-y-2">
                    <label className="text-sm font-medium">
                        Title
                    </label>

                    <input
                        value={title}
                        onChange={(e) =>
                            setTitle(e.target.value)
                        }
                        placeholder="e.g. Implement Work dashboard"
                        disabled={saving}
                        className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                    />
                </div>

                <div className="space-y-2">
                    <label className="text-sm font-medium">
                        Description
                    </label>

                    <textarea
                        value={description}
                        onChange={(e) =>
                            setDescription(e.target.value)
                        }
                        rows={5}
                        placeholder="Describe the work..."
                        disabled={saving}
                        className="w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                    />
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                        <label className="text-sm font-medium">
                            Assignee
                        </label>

                        <input
                            value={assignee}
                            onChange={(e) =>
                                setAssignee(e.target.value)
                            }
                            placeholder="Assignee"
                            disabled={saving}
                            className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-medium">
                            Priority
                        </label>

                        <select
                            value={priority}
                            onChange={(e) =>
                                setPriority(
                                    e.target.value as
                                    | "low"
                                    | "medium"
                                    | "high"
                                    | "urgent"
                                )
                            }
                            disabled={saving}
                            className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                        >
                            <option value="low">
                                Low
                            </option>

                            <option value="medium">
                                Medium
                            </option>

                            <option value="high">
                                High
                            </option>

                            <option value="urgent">
                                Urgent
                            </option>
                        </select>
                    </div>
                </div>

                <div className="space-y-2">
                    <label className="text-sm font-medium">
                        Due date
                    </label>

                    <input
                        type="date"
                        value={dueDate}
                        onChange={(e) =>
                            setDueDate(e.target.value)
                        }
                        disabled={saving}
                        className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                    />
                </div>

                <div className="flex justify-end gap-3">
                    <Link
                        href={`/work/projects/${projectId}`}
                        className="rounded-lg border px-4 py-2 text-sm hover:bg-muted"
                    >
                        Cancel
                    </Link>

                    <button
                        type="submit"
                        disabled={saving}
                        className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                    >
                        {saving && (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        )}

                        {saving
                            ? "Creating..."
                            : "Create work item"}
                    </button>
                </div>
            </form>
        </main>
    );
}