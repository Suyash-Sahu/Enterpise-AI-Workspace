import { apiClient } from "@/lib/api/client";
import { ENDPOINTS } from "@/lib/api/endpoints";

import {
    ProjectDTO,
    TaskDTO,
    TaskDependencyDTO,
    CreateProjectInput,
    UpdateProjectInput,
    CreateWorkItemInput,
    UpdateWorkItemInput,
    WorkStatus,
    DependencyKind,
    ActivityDTO,
    DashboardDTO,
    ProjectStatsDTO,
    TaskLinksDTO,
    ProposalDTO,
    ProposalStatus,
    AiSettingsDTO,
    AutonomyLevel,
    MutatingKind,
    CommandResultDTO,
    FocusPlanDTO,
    RiskReportDTO,
    AutomationDTO,
    AutomationRunDTO,
    AutomationPreviewDTO,
    AutomationBuildDTO,
    CommentDTO,
} from "@/types/project";

export class WorkService {
    // ------------------------------------------------------------------
    // Projects
    // ------------------------------------------------------------------

    static async getProjects(): Promise<ProjectDTO[]> {
        return apiClient<ProjectDTO[]>(
            ENDPOINTS.PROJECTS.LIST
        );
    }

    static async getProject(
        id: string
    ): Promise<ProjectDTO> {
        return apiClient<ProjectDTO>(
            `/workgraph/projects/${id}`
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

    static async updateProject(
        id: string,
        data: UpdateProjectInput
    ): Promise<ProjectDTO> {
        return apiClient<ProjectDTO>(
            `/workgraph/projects/${id}`,
            {
                method: "PATCH",
                body: data,
            }
        );
    }

    static async getDependencies(
        taskId: string,
    ): Promise<TaskDependencyDTO[]> {
        return apiClient<TaskDependencyDTO[]>(
            `/workgraph/tasks/${taskId}/dependencies`,
        );
    }  
    
    static async addDependency(
    taskId: string,
    dependsOnTaskId: string,
    kind: DependencyKind = "BLOCKED_BY",
): Promise<TaskDependencyDTO> {
    return apiClient<TaskDependencyDTO>(
        `/workgraph/tasks/${taskId}/dependencies`,
        {
            method: "POST",
            body: {
                depends_on_task_id: dependsOnTaskId,
                kind,
            },
        },
    );
}

static async removeDependency(
    taskId: string,
    dependsOnTaskId: string,
): Promise<void> {
    await apiClient(
        `/workgraph/tasks/${taskId}/dependencies/${dependsOnTaskId}`,
        {
            method: "DELETE",
        },
    );
}

    // ------------------------------------------------------------------
    // Dashboard / board / activity (server-side aggregates)
    // ------------------------------------------------------------------

    static async getDashboard(): Promise<DashboardDTO> {
        return apiClient<DashboardDTO>("/workgraph/dashboard");
    }

    static async getProjectStats(id: string): Promise<ProjectStatsDTO> {
        return apiClient<ProjectStatsDTO>(`/workgraph/projects/${id}/stats`);
    }

    static async getActivity(taskId: string): Promise<ActivityDTO[]> {
        return apiClient<ActivityDTO[]>(`/workgraph/tasks/${taskId}/activity`);
    }

    static async getLinks(taskId: string): Promise<TaskLinksDTO> {
        return apiClient<TaskLinksDTO>(`/workgraph/tasks/${taskId}/links`);
    }

    // ------------------------------------------------------------------
    // AI layer: inbox, kill switch, autonomy
    // ------------------------------------------------------------------

    static async getInbox(status?: ProposalStatus): Promise<ProposalDTO[]> {
        return apiClient<ProposalDTO[]>("/workgraph/inbox", {
            params: status ? { status } : undefined,
        });
    }

    static async decideProposal(
        id: string,
        approve: boolean,
        editedPayload?: Record<string, unknown>,
    ): Promise<ProposalDTO> {
        return apiClient<ProposalDTO>(
            `/workgraph/inbox/${id}/${approve ? "approve" : "reject"}`,
            {
                method: "POST",
                body: editedPayload ? { edited_payload: editedPayload } : {},
            },
        );
    }

    static async runCommand(command: string, projectId?: string): Promise<CommandResultDTO> {
        return apiClient<CommandResultDTO>("/workgraph/ai/execute", {
            method: "POST",
            body: { command, project_id: projectId ?? null },
        });
    }

    static async getFocusPlan(): Promise<FocusPlanDTO> {
        return apiClient<FocusPlanDTO>("/workgraph/ai/focus-plan");
    }

    static async getRisks(): Promise<RiskReportDTO> {
        return apiClient<RiskReportDTO>("/workgraph/ai/risks");
    }

    static async scanRisks(): Promise<ProposalDTO[]> {
        return apiClient<ProposalDTO[]>("/workgraph/ai/risks/scan", { method: "POST", body: {} });
    }

    // Automations (rules are drafts until previewed; the server enforces it)
    static async getAutomations(): Promise<AutomationDTO[]> {
        return apiClient<AutomationDTO[]>("/workgraph/automations");
    }

    static async getAutomation(id: string): Promise<{ automation: AutomationDTO; runs: AutomationRunDTO[] }> {
        return apiClient(`/workgraph/automations/${id}`);
    }

    static async buildAutomation(text: string, projectId?: string): Promise<AutomationBuildDTO> {
        return apiClient<AutomationBuildDTO>("/workgraph/automations", {
            method: "POST",
            body: { text, project_id: projectId ?? null },
        });
    }

    static async previewAutomation(id: string): Promise<AutomationPreviewDTO> {
        return apiClient<AutomationPreviewDTO>(`/workgraph/automations/${id}/preview`, { method: "POST", body: {} });
    }

    static async automationAction(id: string, action: "activate" | "pause" | "resume"): Promise<AutomationDTO> {
        return apiClient<AutomationDTO>(`/workgraph/automations/${id}/${action}`, { method: "POST", body: {} });
    }

    static async runAutomation(id: string): Promise<AutomationRunDTO | null> {
        return apiClient<AutomationRunDTO | null>(`/workgraph/automations/${id}/run`, { method: "POST", body: {} });
    }

    // Comments
    static async getComments(taskId: string): Promise<CommentDTO[]> {
        return apiClient<CommentDTO[]>(`/workgraph/tasks/${taskId}/comments`);
    }

    static async addComment(taskId: string, body: string): Promise<CommentDTO> {
        return apiClient<CommentDTO>(`/workgraph/tasks/${taskId}/comments`, { method: "POST", body: { body } });
    }

    static async editComment(id: string, body: string): Promise<CommentDTO> {
        return apiClient<CommentDTO>(`/workgraph/comments/${id}`, { method: "PATCH", body: { body } });
    }

    static async deleteComment(id: string): Promise<void> {
        await apiClient(`/workgraph/comments/${id}`, { method: "DELETE" });
    }

    static async getAiSettings(): Promise<AiSettingsDTO> {
        return apiClient<AiSettingsDTO>("/workgraph/ai/settings");
    }

    static async setKillSwitch(enabled: boolean, projectId?: string) {
        return apiClient<{ scope: string; ai_enabled: boolean; cancelled: number }>(
            "/workgraph/ai/kill-switch",
            { method: "PUT", body: { enabled, project_id: projectId ?? null } },
        );
    }

    static async setAutonomy(projectId: string, actionKind: MutatingKind, level: AutonomyLevel) {
        return apiClient("/workgraph/ai/autonomy", {
            method: "PUT",
            body: { project_id: projectId, action_kind: actionKind, level },
        });
    }

    // ------------------------------------------------------------------
    // Work items
    // ------------------------------------------------------------------

    static async getWorkItems(
        projectId?: string,
        filters?: {
            search?: string;
            status?: WorkStatus;
            assignee?: string;
            priority?: string;
            overdue?: boolean;
        },
    ): Promise<TaskDTO[]> {
        const params: Record<string, string> = {};

        if (projectId) {
            params.project_id = projectId;
        }

        if (filters?.search) {
            params.search = filters.search;
        }

        if (filters?.status) {
            params.status = filters.status;
        }

        if (filters?.assignee) {
            params.assignee = filters.assignee;
        }

        if (filters?.priority) {
            params.priority = filters.priority;
        }

        if (filters?.overdue) {
            params.overdue = "true";
        }

        return apiClient<TaskDTO[]>(
            ENDPOINTS.PROJECTS.TASKS,
            {
                params:
                    Object.keys(params).length > 0
                    ? params
                    : undefined,
            },
        );
    }

    static async getWorkItem(
        id: string
    ): Promise<TaskDTO> {
        return apiClient<TaskDTO>(
            ENDPOINTS.PROJECTS.TASK(id)
        );
    }

    static async createWorkItem(
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

    static async updateWorkItem(
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