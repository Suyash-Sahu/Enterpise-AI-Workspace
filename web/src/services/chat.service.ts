import { apiClient } from "@/lib/api/client";
import { ENDPOINTS } from "@/lib/api/endpoints";
import { ApiResponse } from "@/types/common";
import { ChatQueryResponseDTO } from "@/types/chat";

export class ChatService {
    static async executeQuery(prompt: string, agent_id: string = "supervisor", model_id: string = "gpt-4o"): Promise<ChatQueryResponseDTO> {
        const res = await apiClient<ApiResponse<ChatQueryResponseDTO>>(ENDPOINTS.CHAT.QUERY, {
            method: "POST",
            params: { prompt, agent_id, model_id },
        });
        return res.data;
    }
}
