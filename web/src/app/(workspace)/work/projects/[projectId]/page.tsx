"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AiKillSwitch } from "@/components/projects/AiKillSwitch";
import { AutonomySettings } from "@/components/projects/AutonomySettings";
import { WorkService } from "@/services/work.service";
import type { ProjectDTO, TaskDTO } from "@/types/project";

export default function ProjectPage() {
    const params = useParams();
    const projectId = params.projectId as string;

    const [project, setProject] = useState<ProjectDTO | null>(null);
    const [tasks, setTasks] = useState<TaskDTO[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!projectId) return;

        async function loadProject() {
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
                setError("Failed to load project.");
            } finally {
                setLoading(false);
            }
        }

        loadProject();
    }, [projectId]);

    if (loading) {
        return (
            <div className="p-6">
                <p className="text-muted-foreground">Loading project...</p>
            </div>
        );
    }

    if (error || !project) {
        return (
            <div className="p-6">
                <h1 className="text-xl font-semibold">Project not found</h1>
                <p className="mt-2 text-muted-foreground">
                    {error ?? "This project could not be loaded."}
                </p>

                <Link
                    href="/work/projects"
                    className="mt-4 inline-block text-sm underline"
                >
                    Back to projects
                </Link>
            </div>
        );
    }

    const total = tasks.length;
    const completed = tasks.filter((task) => task.status === "done").length;
    const inProgress = tasks.filter(
        (task) => task.status === "in_progress"
    ).length;
    const blocked = tasks.filter((task) => task.status === "blocked").length;

    return (
        <div className="space-y-6 p-6">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <Link
                        href="/work/projects"
                        className="text-sm text-muted-foreground hover:underline"
                    >
                        ← Projects
                    </Link>

                    <h1 className="mt-2 text-3xl font-bold">{project.name}</h1>

                    {project.description && (
                        <p className="mt-2 max-w-2xl text-muted-foreground">
                            {project.description}
                        </p>
                    )}

                    <div className="mt-3">
                        <AiKillSwitch projectId={project.id} />
                    </div>
                </div>

                <div className="flex gap-2">
                    <Link
                        href={`/work/projects/${project.id}/board`}
                        className="rounded-md border px-4 py-2 text-sm hover:bg-muted"
                    >
                        Board
                    </Link>

                    <Link
                        href={`/work/projects/${project.id}/new`}
                        className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground"
                    >
                        New work item
                    </Link>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <Stat label="Total" value={total} />
                <Stat label="In Progress" value={inProgress} />
                <Stat label="Completed" value={completed} />
                <Stat label="Blocked" value={blocked} />
            </div>

            <section className="rounded-xl border">
                <div className="border-b p-4">
                    <h2 className="font-semibold">Work Items</h2>
                </div>

                {tasks.length === 0 ? (
                    <div className="p-8 text-center text-muted-foreground">
                        No work items yet.
                    </div>
                ) : (
                    <div className="divide-y">
                        {tasks.map((task) => (
                            <div
                                key={task.id}
                                className="flex items-center justify-between gap-4 p-4"
                            >
                                <div>
                                    <p className="font-medium">{task.title}</p>

                                    {task.description && (
                                        <p className="mt-1 text-sm text-muted-foreground">
                                            {task.description}
                                        </p>
                                    )}
                                </div>

                                <div className="flex items-center gap-3 text-sm">
                                    <span className="rounded-md border px-2 py-1">
                                        {task.priority}
                                    </span>

                                    <span className="rounded-md bg-muted px-2 py-1">
                                        {task.status}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            <AutonomySettings projectId={project.id} />
        </div>
    );
}

function Stat({
    label,
    value,
}: {
    label: string;
    value: number;
}) {
    return (
        <div className="rounded-xl border p-4">
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="mt-1 text-2xl font-bold">{value}</p>
        </div>
    );
}