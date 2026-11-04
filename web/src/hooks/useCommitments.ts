import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CommitmentService, ListCommitmentsParams } from "@/services/commitment.service";
import {
    CommitmentCreateInput,
    CommitmentUpdateInput,
    CommitmentVerificationInput,
} from "@/types/commitment";

export function useCommitments(params?: ListCommitmentsParams | string) {
    const queryParams: ListCommitmentsParams | undefined =
        typeof params === "string" ? { status: params } : params;

    return useQuery({
        queryKey: ["commitments", queryParams],
        queryFn: () => CommitmentService.list(queryParams),
    });
}

export function useCommitment(id?: string) {
    return useQuery({
        queryKey: ["commitment", id],
        queryFn: () => CommitmentService.get(id!),
        enabled: !!id,
    });
}

export function useCommitmentStats() {
    return useQuery({
        queryKey: ["commitment-stats"],
        queryFn: () => CommitmentService.getStats(),
    });
}

export function useCommitmentAnalytics() {
    return useQuery({
        queryKey: ["commitment-analytics"],
        queryFn: () => CommitmentService.getAnalytics(),
    });
}

export function useCommitmentEvents(commitmentId?: string) {
    return useQuery({
        queryKey: ["commitment-events", commitmentId],
        queryFn: () => CommitmentService.getEvents(commitmentId!),
        enabled: !!commitmentId,
    });
}

export function useActiveCommitmentRun() {
    const queryClient = useQueryClient();

    return useQuery({
        queryKey: ["commitment-run-active"],
        queryFn: () => CommitmentService.getActiveRun(),
        refetchInterval: (query) => {
            const data = query.state.data;
            if (data && (data.status === "running" || data.status === "queued")) {
                return 1500;
            }
            return false;
        },
    });
}

export function useCommitmentRun(runId: string | null) {
    const queryClient = useQueryClient();

    return useQuery({
        queryKey: ["commitment-run", runId],
        queryFn: () => CommitmentService.getRun(runId!),
        enabled: !!runId,
        refetchInterval: (query) => {
            const data = query.state.data;
            if (data && (data.status === "running" || data.status === "queued")) {
                return 1500;
            }
            return false;
        },
    });
}

export function useCommitmentRunsList() {
    return useQuery({
        queryKey: ["commitment-runs-list"],
        queryFn: () => CommitmentService.listRuns(),
    });
}

export function useStartCommitmentRun() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            run_type,
            max_emails,
        }: {
            run_type: "scan" | "sweep";
            max_emails?: number;
        }) => CommitmentService.startRun(run_type, max_emails),
        onSuccess: (data) => {
            queryClient.setQueryData(["commitment-run", data.id], data);
            queryClient.setQueryData(["commitment-run-active"], data);
            queryClient.invalidateQueries({ queryKey: ["commitment-runs-list"] });
        },
    });
}

export function useCancelCommitmentRun() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (runId: string) => CommitmentService.cancelRun(runId),
        onSuccess: (data) => {
            queryClient.setQueryData(["commitment-run", data.id], data);
            queryClient.invalidateQueries({ queryKey: ["commitment-run-active"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-runs-list"] });
            queryClient.invalidateQueries({ queryKey: ["commitments"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-stats"] });
        },
    });
}

export function useCreateCommitment() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (data: CommitmentCreateInput) => CommitmentService.create(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["commitments"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-stats"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-analytics"] });
        },
    });
}

export function useUpdateCommitment() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: CommitmentUpdateInput }) =>
            CommitmentService.update(id, data),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: ["commitments"] });
            queryClient.invalidateQueries({ queryKey: ["commitment", id] });
            queryClient.invalidateQueries({ queryKey: ["commitment-stats"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-analytics"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-events", id] });
        },
    });
}

export function useCompleteCommitment() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: string) => CommitmentService.complete(id),
        onSuccess: (_, id) => {
            queryClient.invalidateQueries({ queryKey: ["commitments"] });
            queryClient.invalidateQueries({ queryKey: ["commitment", id] });
            queryClient.invalidateQueries({ queryKey: ["commitment-stats"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-analytics"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-events", id] });
        },
    });
}

export function useDismissCommitment() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: string) => CommitmentService.dismiss(id),
        onSuccess: (_, id) => {
            queryClient.invalidateQueries({ queryKey: ["commitments"] });
            queryClient.invalidateQueries({ queryKey: ["commitment", id] });
            queryClient.invalidateQueries({ queryKey: ["commitment-stats"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-analytics"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-events", id] });
        },
    });
}

export function useReopenCommitment() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: string) => CommitmentService.reopen(id),
        onSuccess: (_, id) => {
            queryClient.invalidateQueries({ queryKey: ["commitments"] });
            queryClient.invalidateQueries({ queryKey: ["commitment", id] });
            queryClient.invalidateQueries({ queryKey: ["commitment-stats"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-analytics"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-events", id] });
        },
    });
}

export function useVerifyCommitment() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data?: CommitmentVerificationInput }) =>
            CommitmentService.verify(id, data),
        onSuccess: (_, { id }) => {
            queryClient.invalidateQueries({ queryKey: ["commitments"] });
            queryClient.invalidateQueries({ queryKey: ["commitment", id] });
            queryClient.invalidateQueries({ queryKey: ["commitment-stats"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-analytics"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-events", id] });
        },
    });
}

export function useGenerateFollowUp() {
    return useMutation({
        mutationFn: (id: string) => CommitmentService.generateFollowUp(id),
    });
}

export function useProposeCommitmentTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: string) => CommitmentService.proposeTask(id),
        onSuccess: (_, id) => {
            queryClient.invalidateQueries({ queryKey: ["commitment", id] });
            queryClient.invalidateQueries({ queryKey: ["commitment-events", id] });
        },
    });
}

// Backward-compatible hooks
export function useScanCommitments() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: () => CommitmentService.scan(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["commitments"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-stats"] });
        },
    });
}

export function useCommitmentSweep() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: () => CommitmentService.sweep(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["commitments"] });
            queryClient.invalidateQueries({ queryKey: ["commitment-stats"] });
        },
    });
}
