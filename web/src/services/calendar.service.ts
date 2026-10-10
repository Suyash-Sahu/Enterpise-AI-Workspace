import { apiClient } from "@/lib/api/client";
import { ENDPOINTS } from "@/lib/api/endpoints";
import { CalendarEventCreate, CalendarEventDTO } from "@/types/calendar";

export class CalendarService {
    static async listEvents(timeMin: string, timeMax: string): Promise<CalendarEventDTO[]> {
        const res = await apiClient<{ count: number; events: CalendarEventDTO[] }>(
            ENDPOINTS.CALENDAR.EVENTS,
            { params: { time_min: timeMin, time_max: timeMax } }
        );
        return res.events;
    }

    static async createEvent(data: CalendarEventCreate): Promise<CalendarEventDTO> {
        return apiClient<CalendarEventDTO>(ENDPOINTS.CALENDAR.EVENTS, {
            method: "POST",
            body: data,
        });
    }
}
