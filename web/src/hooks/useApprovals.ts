import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ApprovalService } from "@/services/approval.service";

export function useApprovals() {
    return useQuery({
        queryKey: ["approvals"],
        queryFn: () => ApprovalService.getApprovals(),
    });
}

export function useApproveRequest() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (id: string) => ApprovalService.approve(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["approvals"] });
        },
    });
}

export function useRejectRequest() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (id: string) => ApprovalService.reject(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["approvals"] });
        },
    });
}
