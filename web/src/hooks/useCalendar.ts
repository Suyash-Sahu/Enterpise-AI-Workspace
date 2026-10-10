import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarService } from "@/services/calendar.service";
import { CalendarEventCreate } from "@/types/calendar";

export function useCalendarEvents(timeMin: string, timeMax: string) {
    return useQuery({
        queryKey: ["calendar-events", timeMin, timeMax],
        queryFn: () => CalendarService.listEvents(timeMin, timeMax),
    });
}

export function useCreateCalendarEvent() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: CalendarEventCreate) => CalendarService.createEvent(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
        },
    });
}
