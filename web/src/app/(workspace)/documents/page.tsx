"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import PageHeader from "@/components/shared/PageHeader";
import SearchInput from "@/components/shared/SearchInput";
import { useDriveFiles } from "@/hooks/useDrive";
import { ragService, CitationResult, IngestedDocumentInfo } from "@/services/rag.service";
import {
    useSummarizeDocument,
    useAskDocument,
    useBulletSummary,
    useExtractInformation,
    useCompareDocuments,
    useUploadVaultDocument
} from "@/hooks/useDocumentAI";
import {
    FileText,
    Sparkles,
    HelpCircle,
    FileSearch,
    GitCompare,
    ListChecks,
    Upload,
    BrainCircuit,
    Database,
    Search,
    CheckCircle2,
    Layers,
    Loader2
} from "lucide-react";

export default function DocumentsPage() {
    const [search, setSearch] = useState("");
    const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
    const [question, setQuestion] = useState("");
    const [ragQuery, setRagQuery] = useState("");
    const [ingestedDocs, setIngestedDocs] = useState<IngestedDocumentInfo[]>([]);
    const [ingestingId, setIngestingId] = useState<string | null>(null);
    const [isSearchingRAG, setIsSearchingRAG] = useState(false);
    const [isAskingRAG, setIsAskingRAG] = useState(false);
    
    const [aiResponses, setAiResponses] = useState<Array<{
        type: string;
        content: string;
        timestamp: string;
        citations?: CitationResult[];
    }>>([]);

    const { data: documents, isLoading } = useDriveFiles();

    const summarizeMutation = useSummarizeDocument();
    const askMutation = useAskDocument();
    const bulletMutation = useBulletSummary();
    const extractMutation = useExtractInformation();
    const compareMutation = useCompareDocuments();
    const uploadMutation = useUploadVaultDocument();

    const fetchIngestedList = async () => {
        try {
            const list = await ragService.listIngestedDocuments("1");
            setIngestedDocs(list);
        } catch (e) {
            console.error("Failed to load ingested documents", e);
        }
    };

    useEffect(() => {
        fetchIngestedList();
    }, []);

    const filtered = (documents || []).filter((d) => d.name.toLowerCase().includes(search.toLowerCase()));
    const selectedDoc = (documents || []).find((d) => d.id === selectedDocId) || documents?.[0];

    const addAiMessage = (type: string, content: string, citations?: CitationResult[]) => {
        setAiResponses((prev) => [
            ...prev,
            { type, content, timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), citations },
        ]);
    };

    const handleIngestToRAG = async (fileId: string, name: string) => {
        setIngestingId(fileId);
        try {
            const res = await ragService.ingestDocument({
                file_id: fileId,
                source: name,
                owner_id: "1",
            });
            addAiMessage("RAG Ingestion", `Document '${name}' vector indexed into pgvector!\nCreated ${res.chunks_created} chunks (${res.total_characters} characters).`);
            fetchIngestedList();
        } catch (err: any) {
            addAiMessage("RAG Ingestion Error", err.message);
        } finally {
            setIngestingId(null);
        }
    };

    const handleRAGSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!ragQuery.trim()) return;
        setIsSearchingRAG(true);
        const q = ragQuery;
        setRagQuery("");
        try {
            const res = await ragService.searchRAG({
                query: q,
                top_k: 3,
                file_id: selectedDoc?.id,
                owner_id: "1",
            });
            const textSummary = `Hybrid RAG Search found ${res.count} ranked citations for query: "${q}"`;
            addAiMessage(`Hybrid RAG Search: "${q}"`, textSummary, res.results);
        } catch (err: any) {
            addAiMessage("RAG Search Error", err.message);
        } finally {
            setIsSearchingRAG(false);
        }
    };

    const handleRAGAskAnswer = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!question.trim()) return;
        setIsAskingRAG(true);
        const q = question;
        setQuestion("");
        try {
            const res = await ragService.askRAGAnswer({
                question: q,
                file_id: selectedDoc?.id,
                owner_id: "1",
                top_k: 3,
            });
            addAiMessage(`RAG Grounded Q&A: "${q}"`, res.answer, res.citations);
        } catch (err: any) {
            addAiMessage("RAG Answer Error", err.message);
        } finally {
            setIsAskingRAG(false);
        }
    };

    const handleSummarize = (fileId: string) => {
        summarizeMutation.mutate(fileId, {
            onSuccess: (res) => addAiMessage("Summarize AI", res),
            onError: (err) => addAiMessage("Error", err.message),
        });
    };

    const handleBullets = (fileId: string) => {
        bulletMutation.mutate(fileId, {
            onSuccess: (res) => addAiMessage("Bullet Summary", res),
            onError: (err) => addAiMessage("Error", err.message),
        });
    };

    const handleExtract = (fileId: string) => {
        extractMutation.mutate(
            { fileId, fields: ["author", "specifications", "deadlines"] },
            {
                onSuccess: (res) => addAiMessage("Fields Extraction", JSON.stringify(res, null, 2)),
                onError: (err) => addAiMessage("Error", err.message),
            }
        );
    };

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || e.target.files.length === 0) return;
        const formData = new FormData();
        formData.append("file", e.target.files[0]);
        uploadMutation.mutate(formData, {
            onSuccess: () => toast.success("File uploaded and indexed"),
        });
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Document AI Intelligence & Project 3 RAG Vault"
                description="Ingest Drive docs, perform hybrid RRF vector search, and generate grounded answers with citations on Port 8001."
                breadcrumbs={[{ label: "Workspace" }, { label: "AI Documents & RAG" }]}
                actions={
                    <label className="flex cursor-pointer items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md transition-all">
                        <Upload className="h-4 w-4" />
                        <span>Upload File to Vault</span>
                        <input type="file" onChange={handleFileUpload} className="hidden" />
                    </label>
                }
            />

            <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
                <SearchInput value={search} onChange={setSearch} placeholder="Search..." className="max-w-md" />
                
                {/* RAG Hybrid Search Bar */}
                <form onSubmit={handleRAGSearch} className="flex items-center gap-2 w-full sm:w-auto">
                    <input
                        type="text"
                        value={ragQuery}
                        onChange={(e) => setRagQuery(e.target.value)}
                        placeholder="Search..."
                        className="rounded-xl border border-border bg-surface px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none w-full sm:w-64"
                    />
                    <button
                        type="submit"
                        disabled={!ragQuery.trim() || isSearchingRAG}
                        className="flex items-center gap-1 rounded-xl bg-primary px-3 py-2 text-xs font-bold text-primary-foreground shadow-md hover:bg-primary disabled:opacity-40 transition-all"
                    >
                        {isSearchingRAG ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
                        <span>RAG Search</span>
                    </button>
                </form>
            </div>

            {/* Main Documents Grid */}
            {isLoading ? (
                <div className="rounded-2xl border border-border bg-surface p-8 text-center text-xs text-muted-foreground animate-pulse">
                    Loading indexed document vault...
                </div>
            ) : (
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                    {/* Document Files List */}
                    <div className="lg:col-span-2 space-y-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            {filtered.map((doc) => {
                                const isSelected = doc.id === (selectedDocId || selectedDoc?.id);
                                const isIngested = ingestedDocs.some((d) => d.file_id === doc.id);
                                const isIngesting = ingestingId === doc.id;

                                return (
                                    <div
                                        key={doc.id}
                                        onClick={() => setSelectedDocId(doc.id)}
                                        className={`cursor-pointer rounded-2xl border p-4 shadow-sm transition-all space-y-3 ${
                                            isSelected
                                                ? "border-primary bg-primary/10 shadow-md"
                                                : "border-border bg-surface hover:border-primary/40"
                                        }`}
                                    >
                                        <div className="flex items-start justify-between">
                                            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary font-mono text-xs font-bold uppercase border border-primary/20">
                                                DOC
                                            </div>
                                            {isIngested ? (
                                                <span className="flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 font-mono text-xs font-bold text-success border border-success/20">
                                                    <CheckCircle2 className="h-3 w-3" />
                                                    <span>RAG Indexed</span>
                                                </span>
                                            ) : (
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleIngestToRAG(doc.id, doc.name);
                                                    }}
                                                    disabled={isIngesting}
                                                    className="flex items-center gap-1 rounded-full bg-primary/20 hover:bg-primary px-2.5 py-1 font-mono text-xs font-bold text-primary hover:text-primary-foreground border border-primary/30 transition-all"
                                                >
                                                    {isIngesting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Database className="h-3 w-3" />}
                                                    <span>Ingest to RAG</span>
                                                </button>
                                            )}
                                        </div>

                                        <div>
                                            <h4 className="text-xs font-bold text-foreground truncate">{doc.name}</h4>
                                            <p className="text-xs font-mono text-muted-foreground truncate">ID: {doc.id}</p>
                                        </div>

                                        {/* Action Buttons Row */}
                                        <div className="grid grid-cols-3 gap-1.5 pt-2 border-t border-border">
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleSummarize(doc.id);
                                                }}
                                                className="flex items-center justify-center gap-1 rounded-lg bg-primary/20 px-2 py-1 text-xs font-bold text-primary hover:bg-primary hover:text-primary-foreground transition-all"
                                            >
                                                <Sparkles className="h-3 w-3" />
                                                <span>Summarize</span>
                                            </button>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleBullets(doc.id);
                                                }}
                                                className="flex items-center justify-center gap-1 rounded-lg bg-primary/20 px-2 py-1 text-xs font-bold text-primary hover:bg-primary hover:text-primary-foreground transition-all"
                                            >
                                                <ListChecks className="h-3 w-3" />
                                                <span>Bullets</span>
                                            </button>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleExtract(doc.id);
                                                }}
                                                className="flex items-center justify-center gap-1 rounded-lg bg-primary/20 px-2 py-1 text-xs font-bold text-primary hover:bg-primary hover:text-primary-foreground transition-all"
                                            >
                                                <FileSearch className="h-3 w-3" />
                                                <span>Extract</span>
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Chat-style Response & Citations Panel */}
                    <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4 flex flex-col justify-between h-[620px]">
                        <div>
                            <div className="flex items-center justify-between border-b border-border pb-3">
                                <div className="flex items-center gap-2">
                                    <BrainCircuit className="h-5 w-5 text-primary" />
                                    <h3 className="text-sm font-bold text-foreground">RAG Grounded Response Panel</h3>
                                </div>
                                <span className="font-mono text-xs text-primary">{selectedDoc?.name || "Active File"}</span>
                            </div>

                            {/* Chat Responses & Citations Area */}
                            <div className="mt-4 space-y-4 max-h-[440px] overflow-y-auto pr-1">
                                {aiResponses.length === 0 ? (
                                    <div className="p-8 text-center text-xs text-muted-foreground">
                                        Ingest documents, run RAG Search, or ask grounded Q&A to view AI answers and ranked citations here.
                                    </div>
                                ) : (
                                    aiResponses.map((res, idx) => (
                                        <div key={idx} className="rounded-xl border border-primary/30 bg-background p-3.5 space-y-2">
                                            <div className="flex items-center justify-between font-bold text-xs text-primary">
                                                <span>{res.type}</span>
                                                <span className="font-mono text-xs text-muted-foreground">{res.timestamp}</span>
                                            </div>
                                            
                                            <p className="text-xs text-foreground leading-relaxed whitespace-pre-wrap font-mono">{res.content}</p>

                                            {/* Render Ranked Citations */}
                                            {res.citations && res.citations.length > 0 && (
                                                <div className="pt-2 border-t border-border space-y-2">
                                                    <span className="font-mono text-xs font-bold text-primary flex items-center gap-1">
                                                        <Layers className="h-3 w-3" />
                                                        <span>Citations & Relevance Scores ({res.citations.length})</span>
                                                    </span>
                                                    {res.citations.map((cit, cIdx) => (
                                                        <div key={cIdx} className="rounded-lg bg-surface/80 p-2.5 text-xs font-mono border border-border space-y-1">
                                                            <div className="flex justify-between text-muted-foreground text-xs">
                                                                <span className="text-primary font-bold">Source {cIdx + 1}: {cit.source} (Page {cit.page})</span>
                                                                <span className="text-success font-bold">Score: {cit.score}</span>
                                                            </div>
                                                            <p className="text-xs text-foreground/90 italic">"{cit.text}"</p>
                                                            <div className="flex gap-3 text-[10px] text-muted-foreground font-mono pt-1">
                                                                <span>Vector: {cit.vector_score}</span>
                                                                <span>BM25: {cit.keyword_score}</span>
                                                                <span>Rerank: {cit.rerank_score}</span>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>

                        {/* Ask RAG Grounded Answer Form */}
                        <form onSubmit={handleRAGAskAnswer} className="flex items-center gap-2 pt-3 border-t border-border">
                            <input
                                type="text"
                                value={question}
                                onChange={(e) => setQuestion(e.target.value)}
                                placeholder="Ask about your documents..."
                                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                            />
                            <button
                                type="submit"
                                disabled={!question.trim() || isAskingRAG}
                                className="flex items-center gap-1 rounded-xl bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground shadow-md hover:bg-primary disabled:opacity-40 transition-all shrink-0"
                            >
                                {isAskingRAG ? <Loader2 className="h-4 w-4 animate-spin" /> : <HelpCircle className="h-4 w-4" />}
                                <span>Ask RAG</span>
                            </button>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
