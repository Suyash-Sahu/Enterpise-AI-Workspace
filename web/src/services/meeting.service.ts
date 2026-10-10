import { apiClient } from "@/lib/api/client";
import { ENDPOINTS } from "@/lib/api/endpoints";
import { MeetingCreate, MeetingDTO } from "@/types/meeting";
import { TaskDTO } from "@/types/project";

export class MeetingService {
    static async createMeeting(data: MeetingCreate): Promise<MeetingDTO> {
        return apiClient<MeetingDTO>(ENDPOINTS.MEETINGS.CREATE, {
            method: "POST",
            body: data,
        });
    }

    static async getFollowUps(): Promise<TaskDTO[]> {
        return apiClient<TaskDTO[]>(ENDPOINTS.MEETINGS.FOLLOW_UPS);
    }
}
