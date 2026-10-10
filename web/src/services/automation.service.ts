import { apiClient } from "@/lib/api/client";
import { ENDPOINTS } from "@/lib/api/endpoints";
import {
    AutomationCreateDTO,
    AutomationDTO,
    AutomationDraftDTO,
    AutomationRunResultDTO,
} from "@/types/automation";

export class AutomationService {
    static async list(): Promise<AutomationDTO[]> {
        return apiClient<AutomationDTO[]>(ENDPOINTS.AUTOMATIONS.LIST);
    }

    static async draftFromText(text: string): Promise<AutomationDraftDTO> {
        return apiClient<AutomationDraftDTO>(ENDPOINTS.AUTOMATIONS.FROM_TEXT, {
            method: "POST",
            body: { text },
        });
    }

    static async create(data: AutomationCreateDTO): Promise<AutomationDTO> {
        return apiClient<AutomationDTO>(ENDPOINTS.AUTOMATIONS.CREATE, {
            method: "POST",
            body: data,
        });
    }

    static async update(id: string, data: Partial<AutomationCreateDTO>): Promise<AutomationDTO> {
        return apiClient<AutomationDTO>(ENDPOINTS.AUTOMATIONS.UPDATE(id), {
            method: "PATCH",
            body: data,
        });
    }

    static async runNow(id: string): Promise<AutomationRunResultDTO> {
        return apiClient<AutomationRunResultDTO>(ENDPOINTS.AUTOMATIONS.RUN(id), {
            method: "POST",
        });
    }

    static async runDigestNow(): Promise<Record<string, unknown>> {
        return apiClient<Record<string, unknown>>(ENDPOINTS.AUTOMATIONS.DIGEST_RUN_NOW, {
            method: "POST",
        });
    }

    static async latestDigest(): Promise<Record<string, unknown>> {
        return apiClient<Record<string, unknown>>(ENDPOINTS.AUTOMATIONS.DIGEST_LATEST);
    }
}
