import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { executionManagerService } from "@/services/execution-manager.service";

export function useExecutionHealth() {
    return useQuery({
        queryKey: ["execution-manager", "health"],
        queryFn: () => executionManagerService.getHealth(),
        staleTime: 30000,
    });
}

export function useExecutionHistory(limit: number = 50) {
    return useQuery({
        queryKey: ["execution-manager", "history", limit],
        queryFn: () => executionManagerService.getHistory(limit),
        staleTime: 5000,
    });
}

export function useExecuteTask() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (params: {
            task_type: string;
            input: Record<string, any>;
            execution_mode?: string;
            idempotency_key?: string;
            request_id?: string;
            timeout?: number;
        }) => executionManagerService.executeTask(params),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["execution-manager", "history"] });
        },
    });
}
