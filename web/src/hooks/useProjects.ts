import {
    useMutation,
    useQuery,
    useQueryClient,
} from "@tanstack/react-query";

import { ProjectService } from "@/services/project.service";
import {
    CreateProjectInput,
    CreateWorkItemInput,
    UpdateWorkItemInput,
} from "@/types/project";

export function useProjects() {
    return useQuery({
        queryKey: ["work", "projects"],
        queryFn: () => ProjectService.getProjects(),
    });
}

export function useTasks(projectId?: string) {
    return useQuery({
        queryKey: ["work", "tasks", projectId ?? "all"],
        queryFn: () => ProjectService.getTasks(projectId),
    });
}

export function useCreateProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (data: CreateProjectInput) =>
            ProjectService.createProject(data),

        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ["work", "projects"],
            });
        },
    });
}

export function useCreateWorkItem() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (data: CreateWorkItemInput) =>
            ProjectService.createTask(data),

        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ["work", "tasks"],
            });
        },
    });
}

export function useUpdateWorkItem() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            id,
            data,
        }: {
            id: string;
            data: UpdateWorkItemInput;
        }) => ProjectService.updateTask(id, data),

        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ["work", "tasks"],
            });
        },
    });
}