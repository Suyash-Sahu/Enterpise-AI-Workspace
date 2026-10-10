import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AutomationService } from "@/services/automation.service";
import { AutomationCreateDTO } from "@/types/automation";

export function useAutomations() {
    return useQuery({
        queryKey: ["automations"],
        queryFn: () => AutomationService.list(),
    });
}

export function useDraftAutomationFromText() {
    return useMutation({
        mutationFn: (text: string) => AutomationService.draftFromText(text),
    });
}

export function useCreateAutomation() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: AutomationCreateDTO) => AutomationService.create(data),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["automations"] }),
    });
}

export function useUpdateAutomation() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: Partial<AutomationCreateDTO> }) =>
            AutomationService.update(id, data),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["automations"] }),
    });
}

export function useRunAutomationNow() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (id: string) => AutomationService.runNow(id),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["automations"] }),
    });
}

export function useLatestDigest() {
    return useQuery({
        queryKey: ["digest-latest"],
        queryFn: () => AutomationService.latestDigest(),
        retry: false,
    });
}

export function useRunDigestNow() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: () => AutomationService.runDigestNow(),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["digest-latest"] }),
    });
}
