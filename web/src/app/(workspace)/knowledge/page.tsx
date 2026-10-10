"use client";

import { useState } from "react";
import PageHeader from "@/components/shared/PageHeader";
import KnowledgeGraph from "@/components/knowledge/KnowledgeGraph";
import { BrainCircuit, Sparkles, Layers, CheckCircle2, Bookmark, Clock, Search, ExternalLink } from "lucide-react";

export default function KnowledgePage() {
    const [query, setQuery] = useState("How does the AMOF Hybrid RAG pipeline rank document vectors?");
    const [activeTab, setActiveTab] = useState<"search" | "saved" | "collections" | "facts">("search");
    const [isSearching, setIsSearching] = useState(false);

    const savedQueries = [
        "AMOF RAG vector ranking algorithm",
        "OAuth 2.0 scopes for Gmail & Drive",
        "MFA OTP authentication rules",
    ];

    const facts = [
        { key: "Orchestrator Core", value: "AMOF Adaptive Multi-Agent Framework v3.1", confidence: "99.8%" },
        { key: "Vector Index DB", value: "Qdrant Vector Engine (Cosine Distance)", confidence: "99.4%" },
        { key: "Sparse Search Engine", value: "BM25 rank_bm25 Tokenizer", confidence: "98.9%" },
        { key: "Reciprocal Rank Fusion", value: "RRF Alpha = 0.6", confidence: "99.1%" },
    ];

    const handleSearch = () => {
        setIsSearching(true);
        setTimeout(() => setIsSearching(false), 500);
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Enterprise Knowledge Hub (RAG Engine)"
                description="Where extracted facts, semantic relationships, and vector knowledge live."
                breadcrumbs={[{ label: "Workspace" }, { label: "Knowledge Hub" }]}
            />

            {/* Sub View Tabs */}
            <div className="flex items-center gap-1.5 border-b border-border pb-3">
                {[
                    { id: "search", label: "Semantic RAG Search", icon: Search },
                    { id: "saved", label: "Saved Queries", icon: Bookmark },
                    { id: "collections", label: "Collections", icon: Layers },
                    { id: "facts", label: "AI Memory Facts", icon: BrainCircuit },
                ].map((t) => {
                    const Icon = t.icon;
                    const isSelected = activeTab === t.id;
                    return (
                        <button
                            key={t.id}
                            onClick={() => setActiveTab(t.id as any)}
                            className={`flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all ${
                                isSelected
                                    ? "bg-primary text-primary-foreground shadow-md font-bold"
                                    : "border border-border bg-surface text-muted-foreground hover:bg-muted/50"
                            }`}
                        >
                            <Icon className="h-3.5 w-3.5" />
                            <span>{t.label}</span>
                        </button>
                    );
                })}
            </div>

            {/* RAG Hybrid Search Prompt */}
            <div className="rounded-2xl border border-primary/30 bg-surface p-5 shadow-md space-y-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-primary font-bold text-xs">
                        <BrainCircuit className="h-4 w-4" />
                        <span>Hybrid RAG Semantic Search (BM25 + Vector)</span>
                    </div>
                    <span className="font-mono text-xs font-bold text-success bg-success/10 px-2.5 py-0.5 rounded-full border border-success/20">
                        Synthesized Answer Confidence: 99.2%
                    </span>
                </div>

                <div className="flex gap-2">
                    <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Ask a question about your knowledge base..."
                        className="flex-1 rounded-xl border border-border bg-background px-4 py-2.5 text-xs text-foreground focus:border-primary focus:outline-none"
                    />
                    <button
                        onClick={handleSearch}
                        className="flex items-center gap-1.5 rounded-xl bg-primary px-5 py-2.5 text-xs font-semibold text-primary-foreground shadow-md transition-all"
                    >
                        <Sparkles className="h-4 w-4" />
                        <span>Query RAG</span>
                    </button>
                </div>
            </div>

            {/* Main Tabs Content */}
            {activeTab === "search" && (
                <div className="space-y-6">
                    {/* Synthesized Answer Panel */}
                    <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm space-y-3">
                        <div className="flex items-center gap-2 border-b border-border pb-3">
                            <Sparkles className="h-5 w-5 text-primary" />
                            <h3 className="text-sm font-bold text-foreground">Synthesized RAG Response</h3>
                        </div>

                        <p className="text-xs text-foreground leading-relaxed bg-background p-4 rounded-xl border border-border">
                            The **AMOF Hybrid RAG Pipeline** ranks document vectors by combining sparse BM25 keyword matching scores with dense Qdrant vector embeddings using **Reciprocal Rank Fusion (RRF)** with an alpha parameter of 0.6. This ensures both exact keyword precision and semantic context are represented in the top-k retrieved chunks.
                        </p>

                        {/* Citations */}
                        <div className="flex items-center gap-2 text-xs">
                            <span className="font-bold text-muted-foreground font-mono">Citations:</span>
                            <span className="rounded-lg bg-primary/10 px-2.5 py-1 font-mono text-xs font-bold text-primary">
                                [1] Enterprise_AI_Workspace_PRD.pdf (p. 14)
                            </span>
                            <span className="rounded-lg bg-info/10 px-2.5 py-1 font-mono text-xs font-bold text-info">
                                [2] AMOF_Agent_Topology_Architecture.docx (p. 3)
                            </span>
                        </div>
                    </div>

                    {/* Knowledge Graph Visualization */}
                    <div className="space-y-3">
                        <h3 className="text-sm font-bold text-foreground">Interactive Knowledge Graph Topology</h3>
                        <KnowledgeGraph />
                    </div>
                </div>
            )}

            {activeTab === "saved" && (
                <div className="rounded-2xl border border-border bg-surface p-6 space-y-3">
                    <h3 className="text-sm font-bold text-foreground">Saved Queries & Bookmarks</h3>
                    <div className="space-y-2">
                        {savedQueries.map((sq, i) => (
                            <button
                                key={i}
                                onClick={() => {
                                    setQuery(sq);
                                    setActiveTab("search");
                                }}
                                className="flex w-full items-center justify-between rounded-xl border border-border bg-background p-3 text-xs text-left hover:border-primary/40 transition-colors"
                            >
                                <span className="font-bold text-foreground">{sq}</span>
                                <ExternalLink className="h-3.5 w-3.5 text-primary" />
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {activeTab === "facts" && (
                <div className="rounded-2xl border border-border bg-surface p-6 space-y-4">
                    <h3 className="text-sm font-bold text-foreground">Verified Enterprise AI Memory Facts</h3>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        {facts.map((f, i) => (
                            <div key={i} className="rounded-xl border border-border bg-background p-4 text-xs space-y-1">
                                <div className="flex items-center justify-between">
                                    <span className="font-mono text-xs font-bold text-primary">{f.key}</span>
                                    <span className="font-mono text-[10px] text-success font-bold">{f.confidence}</span>
                                </div>
                                <p className="font-bold text-foreground">{f.value}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
