export interface DocumentDTO {
    id: string;
    name: string;
    type: "pdf" | "docx" | "gdoc" | "xlsx" | "csv" | "txt";
    size: string;
    updatedAt: string;
    owner: string;
    summary: string;
    collections: string[];
}

export interface KnowledgeSearchDTO {
    query: string;
    synthesized_answer: string;
    results: Array<{
        chunk_id: string;
        content: string;
        source_title: string;
        rrf_score: number;
    }>;
    citations: Array<{
        document: string;
        page: number;
    }>;
}
