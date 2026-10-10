import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { evaluationService } from "@/services/evaluation.service";

export function useEvaluationHealth() {
    return useQuery({
        queryKey: ["evaluation", "health"],
        queryFn: () => evaluationService.getHealth(),
        refetchInterval: 15000,
    });
}

export function useEvaluationRuns() {
    return useQuery({
        queryKey: ["evaluation", "runs"],
        queryFn: () => evaluationService.listRuns(),
    });
}

export function useEvaluationRunDetails(runId?: string) {
    return useQuery({
        queryKey: ["evaluation", "runs", runId],
        queryFn: () => evaluationService.getRunDetails(runId!),
        enabled: !!runId,
    });
}

export function useEvaluationResults(runId?: string) {
    return useQuery({
        queryKey: ["evaluation", "results", runId],
        queryFn: () => evaluationService.getRunResults(runId!),
        enabled: !!runId,
    });
}

export function useStartEvaluationRun() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (params: { dataset_version?: string; run_baselines?: boolean; run_ablations?: boolean }) =>
            evaluationService.startRun(params),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["evaluation"] });
        },
    });
}
