import { useMutation, useQuery } from "@tanstack/react-query";
import { MeetingService } from "@/services/meeting.service";
import { MeetingCreate } from "@/types/meeting";

export function useCreateMeeting() {
    return useMutation({
        mutationFn: (data: MeetingCreate) => MeetingService.createMeeting(data),
    });
}

export function useMeetingFollowUps() {
    return useQuery({
        queryKey: ["meeting-follow-ups"],
        queryFn: () => MeetingService.getFollowUps(),
    });
}
