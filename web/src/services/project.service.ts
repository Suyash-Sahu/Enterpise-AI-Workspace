import { apiClient } from "@/lib/api/client";
import { ENDPOINTS } from "@/lib/api/endpoints";
import {
    ProjectDTO,
    TaskDTO,
    CreateProjectInput,
    CreateWorkItemInput,
    UpdateWorkItemInput,
} from "@/types/project";

export class ProjectService {
    static async getProjects(): Promise<ProjectDTO[]> {
        return apiClient<ProjectDTO[]>(
            ENDPOINTS.PROJECTS.LIST
        );
    }

    static async createProject(
        data: CreateProjectInput
    ): Promise<ProjectDTO> {
        return apiClient<ProjectDTO>(
            ENDPOINTS.PROJECTS.CREATE,
            {
                method: "POST",
                body: data,
            }
        );
    }

    static async getTasks(
        projectId?: string
    ): Promise<TaskDTO[]> {
        return apiClient<TaskDTO[]>(
            ENDPOINTS.PROJECTS.TASKS,
            {
                params: projectId
                    ? { project_id: projectId }
                    : undefined,
            }
        );
    }

    static async createTask(
        data: CreateWorkItemInput
    ): Promise<TaskDTO> {
        return apiClient<TaskDTO>(
            ENDPOINTS.PROJECTS.TASKS,
            {
                method: "POST",
                body: data,
            }
        );
    }

    static async updateTask(
        id: string,
        data: UpdateWorkItemInput
    ): Promise<TaskDTO> {
        return apiClient<TaskDTO>(
            ENDPOINTS.PROJECTS.TASK(id),
            {
                method: "PATCH",
                body: data,
            }
        );
    }
}