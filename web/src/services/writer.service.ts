import { apiClient, ApiResponse } from "@/lib/api-client";

export interface WriterGeneratePayload {
    type: "email" | "rewrite" | "reply";
    instruction?: string;
    text?: string;
    email?: string;
}

export interface WriterResponse {
    result: string;
    type: string;
}

export const writerService = {
    async generate(payload: WriterGeneratePayload): Promise<string> {
        const res = await apiClient.post<ApiResponse<WriterResponse>>("/writer/generate", payload);
        return res.data.data?.result || (res.data as any).result || "";
    },
};
