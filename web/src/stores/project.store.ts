import { create } from "zustand";
import { SEED_PROJECTS, SEED_TASKS, CentralProject, CentralTask } from "@/data/central-store";

interface ProjectState {
    projects: CentralProject[];
    tasks: CentralTask[];
    selectedProjectId: string;
    moveTaskStatus: (taskId: string, newStatus: CentralTask["status"]) => void;
    addTask: (task: Omit<CentralTask, "id">) => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
    projects: SEED_PROJECTS,
    tasks: SEED_TASKS,
    selectedProjectId: "proj-1",
    moveTaskStatus: (taskId, newStatus) =>
        set((state) => ({
            tasks: state.tasks.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t)),
        })),
    addTask: (taskData) =>
        set((state) => ({
            tasks: [
                ...state.tasks,
                {
                    ...taskData,
                    id: `task-${Date.now()}`,
                },
            ],
        })),
}));
