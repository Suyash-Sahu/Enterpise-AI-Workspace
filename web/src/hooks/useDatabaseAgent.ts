import { useQuery, useMutation } from "@tanstack/react-query";
import { databaseAgentService } from "@/services/database-agent.service";

export function useDatabaseHealth() {
    return useQuery({
        queryKey: ["db-agent", "health"],
        queryFn: () => databaseAgentService.getHealth(),
        staleTime: 30000,
    });
}

export function useDatabaseSchema() {
    return useQuery({
        queryKey: ["db-agent", "schema"],
        queryFn: () => databaseAgentService.getSchema(),
        staleTime: 60000,
    });
}

export function useDatabaseQuery() {
    return useMutation({
        mutationFn: (params: { question: string; limit?: number; owner_id?: string }) =>
            databaseAgentService.queryDatabase(params),
    });
}
