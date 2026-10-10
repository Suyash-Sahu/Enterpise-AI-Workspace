import { apiClient, ApiResponse } from "@/lib/api-client";

export interface HealthTelemetry {
    backend: string;
    database: string;
    google: string;
    ollama: string;
    openrouter: string;
    version: string;
    uptime: string;
}

export const healthService = {
    async getHealth(): Promise<HealthTelemetry> {
        const res = await apiClient.get<ApiResponse<HealthTelemetry>>("/health");
        return res.data.data;
    },
};
