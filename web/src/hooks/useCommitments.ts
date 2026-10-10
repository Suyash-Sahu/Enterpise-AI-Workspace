import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CommitmentService } from "@/services/commitment.service";

export function useCommitments(status?: string) {
    return useQuery({
        queryKey: ["commitments", status ?? "all"],
        queryFn: () => CommitmentService.list(status),
    });
}

export function useScanCommitments() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: () => CommitmentService.scan(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["commitments"] });
        },
    });
}

export function useCommitmentSweep() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: () => CommitmentService.sweep(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["commitments"] });
        },
    });
}
