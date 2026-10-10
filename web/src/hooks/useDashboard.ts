import { useQuery } from "@tanstack/react-query";
import { workspaceService, WorkspaceDashboardData } from "@/services/workspace.service";

export function useDashboard() {
    return useQuery<WorkspaceDashboardData>({
        queryKey: ["workspace-dashboard"],
        queryFn: () => workspaceService.getDashboard(),
        refetchInterval: 30000,
        staleTime: 10000,
    });
}
