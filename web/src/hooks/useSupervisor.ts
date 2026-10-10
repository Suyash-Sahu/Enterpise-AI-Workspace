import { useQuery, useMutation } from "@tanstack/react-query";
import { supervisorService } from "@/services/supervisor.service";

export function useSupervisorHealth() {
    return useQuery({
        queryKey: ["supervisor", "health"],
        queryFn: () => supervisorService.getHealth(),
        refetchInterval: 30000,
    });
}

export function useSupervisorExecute() {
    return useMutation({
        mutationFn: (params: {
            question: string;
            execution_mode?: string;
            timeout?: number;
            conversation_id?: string;
        }) => supervisorService.executeSupervisor(params),
    });
}

export function useSupervisorClassify() {
    return useMutation({
        mutationFn: (params: {
            question: string;
            execution_mode?: string;
        }) => supervisorService.classifyIntent(params),
    });
}

export function useSupervisorPlan() {
    return useMutation({
        mutationFn: (params: {
            question: string;
            execution_mode?: string;
        }) => supervisorService.createPlan(params),
    });
}
