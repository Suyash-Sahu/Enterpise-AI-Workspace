import { apiClient, ApiResponse } from "@/lib/api-client";

export interface CitationResult {
    chunk_id: string;
    file_id: string;
    source: string;
    owner_id: string;
    page: number;
    chunk_index: number;
    text: string;
    score: number;
    vector_score: number;
    keyword_score: number;
    rerank_score: number;
}

export interface IngestResponse {
    file_id: string;
    source: string;
    owner_id: string;
    chunks_created: number;
    total_characters: number;
    status: string;
}

export interface SearchResponseData {
    query: string;
    count: number;
    results: CitationResult[];
}

export interface AnswerResponseData {
    question: string;
    answer: string;
    citations_count: number;
    citations: CitationResult[];
}

export interface IngestedDocumentInfo {
    id: number;
    file_id: string;
    source: string;
    owner_id: string;
    chunk_count: number;
    ingested_at: string;
}

export const ragService = {
    async ingestDocument(params: {
        file_id: string;
        source?: string;
        owner_id?: string;
        text?: string;
        chunk_size?: number;
        chunk_overlap?: number;
    }): Promise<IngestResponse> {
        const response = await apiClient.post<ApiResponse<IngestResponse>>(
            "/rag/ingest",
            params
        );
        return response.data.data;
    },

    async searchRAG(params: {
        query: string;
        top_k?: number;
        file_id?: string;
        owner_id?: string;
        alpha?: number;
    }): Promise<SearchResponseData> {
        const response = await apiClient.post<ApiResponse<SearchResponseData>>(
            "/rag/search",
            params
        );
        return response.data.data;
    },

    async askRAGAnswer(params: {
        question: string;
        file_id?: string;
        owner_id?: string;
        top_k?: number;
    }): Promise<AnswerResponseData> {
        const response = await apiClient.post<ApiResponse<AnswerResponseData>>(
            "/rag/answer",
            params
        );
        return response.data.data;
    },

    async listIngestedDocuments(owner_id: string = "1"): Promise<IngestedDocumentInfo[]> {
        const response = await apiClient.get<ApiResponse<{ count: number; documents: IngestedDocumentInfo[] }>>(
            "/rag/documents",
            { params: { owner_id } }
        );
        return response.data.data.documents || [];
    },

    async deleteIngestedDocument(file_id: string, owner_id: string = "1"): Promise<boolean> {
        const response = await apiClient.delete<ApiResponse<{ file_id: string; deleted: boolean }>>(
            `/rag/document/${file_id}`,
            { params: { owner_id } }
        );
        return response.data.data.deleted;
    },
};
