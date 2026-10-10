import { useMutation, useQueryClient } from "@tanstack/react-query";
import { documentService } from "@/services/document.service";

export function useSummarizeDocument() {
    return useMutation({
        mutationFn: (fileId: string) => documentService.summarize(fileId),
    });
}

export function useAskDocument() {
    return useMutation({
        mutationFn: ({ fileId, question }: { fileId: string; question: string }) =>
            documentService.ask(fileId, question),
    });
}

export function useBulletSummary() {
    return useMutation({
        mutationFn: (fileId: string) => documentService.bullets(fileId),
    });
}

export function useExtractInformation() {
    return useMutation({
        mutationFn: ({ fileId, fields }: { fileId: string; fields: string[] }) =>
            documentService.extract(fileId, fields),
    });
}

export function useCompareDocuments() {
    return useMutation({
        mutationFn: ({ firstFileId, secondFileId }: { firstFileId: string; secondFileId: string }) =>
            documentService.compare(firstFileId, secondFileId),
    });
}

export function useUploadVaultDocument() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (formData: FormData) => documentService.uploadVaultFile(formData),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["drive-files"] });
            queryClient.invalidateQueries({ queryKey: ["workspace-dashboard"] });
        },
    });
}
