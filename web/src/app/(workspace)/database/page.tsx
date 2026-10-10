"use client";

import { useState } from "react";
import PageHeader from "@/components/shared/PageHeader";
import { useDatabaseHealth, useDatabaseSchema, useDatabaseQuery } from "@/hooks/useDatabaseAgent";
import { DatabaseResultData } from "@/services/database-agent.service";
import {
    Database,
    Search,
    ShieldCheck,
    Terminal,
    Table as TableIcon,
    Sparkles,
    Loader2,
    Code,
    AlertCircle,
    CheckCircle2,
    Cpu
} from "lucide-react";

export default function DatabaseAgentPage() {
    const [question, setQuestion] = useState("");
    const [lastResult, setLastResult] = useState<DatabaseResultData | null>(null);

    const { data: health, isLoading: healthLoading } = useDatabaseHealth();
    const { data: schema, isLoading: schemaLoading } = useDatabaseSchema();
    const queryMutation = useDatabaseQuery();

    const sampleQuestions = [
        "How many documents do I have indexed?",
        "Show me my recent uploaded documents",
        "How many text chunks exist in the vector database?",
        "List all my workspace document sources",
    ];

    const handleAskQuestion = (q: string) => {
        if (!q.trim()) return;
        setQuestion(q);
        queryMutation.mutate(
            { question: q, limit: 20, owner_id: "1" },
            {
                onSuccess: (data) => setLastResult(data),
            }
        );
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Project 4 — Database Agent (NL-to-SQL)"
                description="Ask natural-language questions about your workspace data. Converted to safe, read-only SQL via AST security validation on Port 8001."
                breadcrumbs={[{ label: "Workspace" }, { label: "Database Agent" }]}
                actions={
                    <div className="flex items-center gap-2 font-mono text-xs">
                        <span className="flex items-center gap-1.5 rounded-xl bg-success/10 px-3 py-1.5 font-bold text-success border border-success/20">
                            <ShieldCheck className="h-4 w-4" />
                            <span>AST Security Active</span>
                        </span>
                        <span className="flex items-center gap-1.5 rounded-xl bg-primary/10 px-3 py-1.5 font-bold text-primary border border-primary/20">
                            <Database className="h-4 w-4" />
                            <span>Port 8001</span>
                        </span>
                    </div>
                }
            />

            {/* NL Question Input Box */}
            <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm space-y-4">
                <form
                    onSubmit={(e) => {
                        e.preventDefault();
                        handleAskQuestion(question);
                    }}
                    className="flex flex-col sm:flex-row gap-3"
                >
                    <div className="relative flex-1">
                        <Search className="absolute left-3.5 top-3 h-4 w-4 text-muted-foreground" />
                        <input
                            type="text"
                            value={question}
                            onChange={(e) => setQuestion(e.target.value)}
                            placeholder="Ask your database (e.g. 'How many documents have I uploaded?')..."
                            className="w-full rounded-xl border border-border bg-background pl-10 pr-4 py-2.5 text-xs text-foreground focus:border-primary focus:outline-none"
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={!question.trim() || queryMutation.isPending}
                        className="flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-xs font-bold text-primary-foreground shadow-md disabled:opacity-40 transition-all shrink-0"
                    >
                        {queryMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Sparkles className="h-4 w-4" />
                        )}
                        <span>Ask Database</span>
                    </button>
                </form>

                {/* Sample Prompt Chips */}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                    <span className="text-xs font-mono font-semibold text-muted-foreground flex items-center gap-1">
                        <Cpu className="h-3 w-3" /> Sample Questions:
                    </span>
                    {sampleQuestions.map((q, idx) => (
                        <button
                            key={idx}
                            onClick={() => handleAskQuestion(q)}
                            className="rounded-lg bg-surface hover:bg-primary/10 border border-border hover:border-primary/40 px-2.5 py-1 text-xs font-mono text-muted-foreground hover:text-primary transition-all"
                        >
                            "{q}"
                        </button>
                    ))}
                </div>
            </div>

            {/* Response Section */}
            {queryMutation.isError && (
                <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-xs text-destructive font-mono flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>Query Failed: {(queryMutation.error as Error).message}</span>
                </div>
            )}

            {lastResult && (
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                    {/* Generated SQL & Explanation Column */}
                    <div className="lg:col-span-1 space-y-4">
                        {/* Generated SQL Card */}
                        <div className="rounded-2xl border border-primary/30 bg-primary/5 p-4 space-y-3">
                            <div className="flex items-center justify-between font-mono text-xs font-bold text-primary border-b border-primary/20 pb-2">
                                <span className="flex items-center gap-1.5">
                                    <Code className="h-4 w-4 text-primary" /> Generated Read-Only SQL
                                </span>
                                <span className="text-xs text-muted-foreground">{lastResult.execution_time}s</span>
                            </div>
                            <pre className="text-xs font-mono text-foreground bg-background/80 p-3 rounded-xl border border-border overflow-x-auto whitespace-pre-wrap leading-relaxed">
                                {lastResult.sql}
                            </pre>
                        </div>

                        {/* Grounded AI Explanation Card */}
                        <div className="rounded-2xl border border-success/30 bg-success/5 p-4 space-y-2">
                            <div className="flex items-center gap-1.5 font-mono text-xs font-bold text-success border-b border-success/20 pb-2">
                                <Sparkles className="h-4 w-4" /> AI Grounded Explanation
                            </div>
                            <p className="text-xs font-mono text-foreground leading-relaxed">
                                {lastResult.explanation || "No explanation provided."}
                            </p>
                        </div>
                    </div>

                    {/* Formatted Data Grid Table Column */}
                    <div className="lg:col-span-2 rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4">
                        <div className="flex items-center justify-between border-b border-border pb-3">
                            <div className="flex items-center gap-2">
                                <TableIcon className="h-5 w-5 text-primary" />
                                <h3 className="text-sm font-bold text-foreground">Query Results Data Grid</h3>
                            </div>
                            <span className="font-mono text-xs text-success font-bold bg-success/10 px-2.5 py-0.5 rounded-full border border-success/20">
                                {lastResult.row_count} Row(s) Returned
                            </span>
                        </div>

                        {lastResult.rows.length === 0 ? (
                            <div className="p-12 text-center text-xs text-muted-foreground">
                                No records returned from the database query.
                            </div>
                        ) : (
                            <div className="overflow-x-auto rounded-xl border border-border">
                                <table className="w-full text-left font-mono text-xs">
                                    <thead className="bg-background text-muted-foreground border-b border-border">
                                        <tr>
                                            {lastResult.columns.map((col, idx) => (
                                                <th key={idx} className="px-4 py-2.5 font-bold uppercase text-xs tracking-wider">
                                                    {col}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border/40">
                                        {lastResult.rows.map((row, rIdx) => (
                                            <tr key={rIdx} className="hover:bg-primary/5 transition-colors">
                                                {lastResult.columns.map((col, cIdx) => (
                                                    <td key={cIdx} className="px-4 py-2.5 text-foreground truncate max-w-xs">
                                                        {String(row[col] ?? "NULL")}
                                                    </td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Allowed Schema Inspector Section */}
            <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-3">
                <div className="flex items-center justify-between border-b border-border pb-3">
                    <div className="flex items-center gap-2 font-bold text-xs text-foreground">
                        <Terminal className="h-4 w-4 text-primary" />
                        <span>Allowed Database Schema Allowlist ({schema?.tables.length || 0} Tables)</span>
                    </div>
                    <span className="font-mono text-xs text-muted-foreground">
                        Strict Security Allowlist Inspection
                    </span>
                </div>

                {schemaLoading ? (
                    <div className="p-4 text-center text-xs text-muted-foreground animate-pulse font-mono">
                        Loading database schema metadata...
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pt-1">
                        {schema?.tables.map((tbl, idx) => (
                            <div key={idx} className="rounded-xl border border-border bg-background p-3 space-y-2 font-mono text-xs">
                                <div className="font-bold text-primary flex items-center justify-between border-b border-border pb-1">
                                    <span>{tbl.name}</span>
                                    <span className="text-xs text-muted-foreground">{tbl.columns.length} cols</span>
                                </div>
                                <div className="space-y-1 text-xs text-muted-foreground max-h-28 overflow-y-auto">
                                    {tbl.columns.map((col, cIdx) => (
                                        <div key={cIdx} className="flex justify-between">
                                            <span className="text-foreground/90">{col.name}</span>
                                            <span className="text-primary text-xs">{col.type}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
