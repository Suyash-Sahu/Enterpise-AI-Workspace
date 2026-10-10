"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
    ArrowLeft,
    FolderKanban,
    Loader2,
} from "lucide-react";

import { WorkService } from "@/services/work.service";

export default function NewProjectPage() {
    const router = useRouter();

    const [name, setName] = useState("");
    const [description, setDescription] =
        useState("");

    const [saving, setSaving] = useState(false);
    const [error, setError] =
        useState<string | null>(null);

    async function handleSubmit(
        event: FormEvent<HTMLFormElement>
    ) {
        event.preventDefault();

        const trimmedName = name.trim();

        if (!trimmedName) {
            setError("Project name is required.");
            return;
        }

        try {
            setSaving(true);
            setError(null);

            const project =
                await WorkService.createProject({
                    name: trimmedName,
                    description:
                        description.trim() || undefined,
                });

            router.push(
                `/work/projects/${project.id}`
            );
        } catch (err) {
            console.error(
                "Failed to create project:",
                err
            );

            setError(
                err instanceof Error
                    ? err.message
                    : "Failed to create project"
            );
        } finally {
            setSaving(false);
        }
    }

    return (
        <main className="max-w-2xl space-y-6 p-6">
            <Link
                href="/work/projects"
                className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
            >
                <ArrowLeft className="h-4 w-4" />

                Back to projects
            </Link>

            <div>
                <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-primary/10 p-2">
                        <FolderKanban className="h-5 w-5 text-primary" />
                    </div>

                    <div>
                        <h1 className="text-2xl font-semibold">
                            New Project
                        </h1>

                        <p className="text-sm text-muted-foreground">
                            Create a project for your work.
                        </p>
                    </div>
                </div>
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
                    <label
                        htmlFor="name"
                        className="text-sm font-medium"
                    >
                        Project name
                    </label>

                    <input
                        id="name"
                        value={name}
                        onChange={(event) =>
                            setName(event.target.value)
                        }
                        placeholder="e.g. AMOF Work"
                        disabled={saving}
                        className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                    />
                </div>

                <div className="space-y-2">
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
                                event.target.value
                            )
                        }
                        placeholder="What is this project about?"
                        rows={5}
                        disabled={saving}
                        className="w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                    />
                </div>

                <div className="flex justify-end gap-3">
                    <Link
                        href="/work/projects"
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
                            : "Create project"}
                    </button>
                </div>
            </form>
        </main>
    );
}