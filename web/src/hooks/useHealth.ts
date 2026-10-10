import { useQuery } from "@tanstack/react-query";
import { healthService, HealthTelemetry } from "@/services/health.service";

export function useHealth() {
    return useQuery<HealthTelemetry>({
        queryKey: ["system-health"],
        queryFn: () => healthService.getHealth(),
        refetchInterval: 15000,
    });
}
