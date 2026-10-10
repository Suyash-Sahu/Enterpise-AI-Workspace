import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { googleService, GmailMessage, GmailLabel, GmailProfile } from "@/services/google.service";
import { ApprovalService } from "@/services/approval.service";

export function useGmailMessages() {
    return useQuery<GmailMessage[]>({
        queryKey: ["gmail-messages"],
        queryFn: () => googleService.fetchGmailMessages(),
        staleTime: 15000,
    });
}

export function useUnreadGmail(limit: number = 20) {
    return useQuery<GmailMessage[]>({
        queryKey: ["gmail-unread", limit],
        queryFn: () => googleService.fetchUnreadGmail(limit),
    });
}

export function useGmailLabels() {
    return useQuery<GmailLabel[]>({
        queryKey: ["gmail-labels"],
        queryFn: () => googleService.fetchGmailLabels(),
    });
}

export function useGmailProfile() {
    return useQuery<GmailProfile>({
        queryKey: ["gmail-profile"],
        queryFn: () => googleService.fetchGmailProfile(),
    });
}

/**
 * Send a composed email.
 *
 * Requires the id of an already-approved approval record — the backend refuses
 * to send without one. Previously this called send with no approval id, so the
 * request always failed with 403 and the failure was hidden by a fabricated
 * success message in the service layer.
 */
export function useSendEmail() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({
            to,
            subject,
            body,
            approvalId,
        }: {
            to: string;
            subject: string;
            body: string;
            approvalId: number;
        }) => googleService.sendEmail(to, subject, body, approvalId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["gmail-messages"] });
            queryClient.invalidateQueries({ queryKey: ["workspace-dashboard"] });
        },
    });
}

/** Request approval to send an email; returns the pending approval's id. */
export function useRequestSendApproval() {
    return useMutation({
        mutationFn: ({ to, subject, body }: { to: string; subject: string; body: string }) =>
            ApprovalService.create({
                action_type: "gmail.send",
                title: `Send email: ${subject || "(no subject)"}`,
                payload: { to, subject, body },
            }),
    });
}

export function useSaveDraft() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ to, subject, body }: { to: string; subject: string; body: string }) =>
            googleService.saveDraft(to, subject, body),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["gmail-messages"] });
        },
    });
}
