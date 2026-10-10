import { apiClient, ApiResponse } from "@/lib/api-client";

export interface DocumentSummaryResponse {
    summary: string;
    file_id: string;
}

export interface DocumentAskResponse {
    answer: string;
    question: string;
    file_id: string;
}

export interface DocumentExtractionResponse {
    result: any;
    fields: string[];
    file_id: string;
}

export interface DocumentCompareResponse {
    comparison: any;
    first_file_id: string;
    second_file_id: string;
}

export const documentService = {
    async summarize(fileId: string): Promise<string> {
        const res = await apiClient.post<ApiResponse<DocumentSummaryResponse>>("/documents/summarize", { file_id: fileId });
        return res.data.data?.summary || (res.data as any).summary || "";
    },

    async ask(fileId: string, question: string): Promise<string> {
        const res = await apiClient.post<ApiResponse<DocumentAskResponse>>("/documents/ask", { file_id: fileId, question });
        return res.data.data?.answer || (res.data as any).answer || "";
    },

    async bullets(fileId: string): Promise<string> {
        const res = await apiClient.post<ApiResponse<DocumentSummaryResponse>>("/documents/bullets", { file_id: fileId });
        return res.data.data?.summary || (res.data as any).summary || "";
    },

    async extract(fileId: string, fields: string[]): Promise<any> {
        const res = await apiClient.post<ApiResponse<DocumentExtractionResponse>>("/documents/extract", { file_id: fileId, fields });
        return res.data.data?.result || (res.data as any).result || {};
    },

    async compare(firstFileId: string, secondFileId: string): Promise<any> {
        const res = await apiClient.post<ApiResponse<DocumentCompareResponse>>("/documents/compare", {
            first_file_id: firstFileId,
            second_file_id: secondFileId,
        });
        return res.data.data?.comparison || (res.data as any).comparison || {};
    },

    async uploadVaultFile(formData: FormData): Promise<any> {
        const res = await apiClient.post<ApiResponse<any>>("/documents/upload", formData, {
            headers: { "Content-Type": "multipart/form-data" },
        });
        return res.data.data;
    },

    async deleteVaultFile(fileId: string): Promise<any> {
        const res = await apiClient.delete<ApiResponse<any>>(`/documents/${fileId}`);
        return res.data.data;
    },
    async getDocuments(): Promise<any[]> {
        return [];
    },
    async uploadDocument(formData: FormData): Promise<any> {
        return this.uploadVaultFile(formData);
    },
};

export const DocumentService = documentService;

