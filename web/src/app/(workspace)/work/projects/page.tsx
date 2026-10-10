"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
    FolderKanban,
    Plus,
    RefreshCw,
    AlertCircle,
} from "lucide-react";

import { WorkService } from "@/services/work.service";
import { ProjectDTO } from "@/types/project";

export default function WorkProjectsPage() {
    const [projects, setProjects] = useState<ProjectDTO[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    async function loadProjects() {
        try {
            setLoading(true);
            setError(null);

            const data = await WorkService.getProjects();

            setProjects(data);
        } catch (err) {
            console.error("Failed to load projects:", err);

            setError(
                err instanceof Error
                    ? err.message
                    : "Failed to load projects"
            );
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        loadProjects();
    }, []);

    return (
        <main className="space-y-6 p-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-semibold">
                        Projects
                    </h1>

                    <p className="mt-1 text-sm text-muted-foreground">
                        Manage your AMOF Work projects.
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={loadProjects}
                        disabled={loading}
                        className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50"
                    >
                        <RefreshCw
                            className={`h-4 w-4 ${loading ? "animate-spin" : ""
                                }`}
                        />

                        Refresh
                    </button>

                    <Link
                        href="/work/projects/new"
                        className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
                    >
                        <Plus className="h-4 w-4" />

                        New Project
                    </Link>
                </div>
            </div>

            {/* Error */}
            {error && (
                <div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
                    <AlertCircle className="mt-0.5 h-4 w-4 text-destructive" />

                    <div>
                        <p className="font-medium">
                            Failed to load projects
                        </p>

                        <p className="mt-1 text-muted-foreground">
                            {error}
                        </p>
                    </div>
                </div>
            )}

            {/* Loading */}
            {loading && (
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {[1, 2, 3].map((item) => (
                        <div
                            key={item}
                            className="h-36 animate-pulse rounded-xl border bg-muted/30"
                        />
                    ))}
                </div>
            )}

            {/* Empty */}
            {!loading && !error && projects.length === 0 && (
                <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-16 text-center">
                    <FolderKanban className="h-10 w-10 text-muted-foreground" />

                    <h2 className="mt-4 font-semibold">
                        No projects yet
                    </h2>

                    <p className="mt-1 text-sm text-muted-foreground">
                        Create your first project to start organizing work.
                    </p>

                    <Link
                        href="/work/projects/new"
                        className="mt-5 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
                    >
                        <Plus className="h-4 w-4" />

                        Create project
                    </Link>
                </div>
            )}

            {/* Projects */}
            {!loading && projects.length > 0 && (
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {projects.map((project) => (
                        <Link
                            key={project.id}
                            href={`/work/projects/${project.id}`}
                            className="group rounded-xl border p-5 transition hover:border-primary/50 hover:bg-muted/30"
                        >
                            <div className="flex items-start justify-between">
                                <div className="rounded-lg bg-primary/10 p-2">
                                    <FolderKanban className="h-5 w-5 text-primary" />
                                </div>

                                <span className="rounded-full bg-muted px-2.5 py-1 text-xs">
                                    {project.status}
                                </span>
                            </div>

                            <h2 className="mt-4 font-semibold group-hover:text-primary">
                                {project.name}
                            </h2>

                            <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                                {project.description ||
                                    "No project description."}
                            </p>

                            <p className="mt-4 text-xs text-muted-foreground">
                                Created{" "}
                                {new Date(
                                    project.created_at
                                ).toLocaleDateString()}
                            </p>
                        </Link>
                    ))}
                </div>
            )}
        </main>
    );
}