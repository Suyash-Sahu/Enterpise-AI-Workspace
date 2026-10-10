"use client";

import { useState } from "react";
import PageHeader from "@/components/shared/PageHeader";
import { useExecutionHealth, useExecutionHistory, useExecuteTask } from "@/hooks/useExecutionManager";
import { ExecutionResponseData } from "@/services/execution-manager.service";
import {
    Cpu,
    Play,
    ShieldCheck,
    Clock,
    RotateCw,
    Sparkles,
    Loader2,
    Database,
    FileText,
    CheckCircle2,
    AlertCircle,
    Layers,
    Server,
    Zap,
    History
} from "lucide-react";

export default function ExecutionManagerPage() {
    const [taskType, setTaskType] = useState("text_generation");
    const [executionMode, setExecutionMode] = useState("auto");
    const [inputQuery, setInputQuery] = useState("");
    const [idempotencyKey, setIdempotencyKey] = useState("");
    const [lastResult, setLastResult] = useState<ExecutionResponseData | null>(null);

    const { data: health, isLoading: healthLoading } = useExecutionHealth();
    const { data: history, isLoading: historyLoading } = useExecutionHistory(20);
    const executeMutation = useExecuteTask();

    const handleExecute = () => {
        if (!inputQuery.trim()) return;

        let payloadInput: Record<string, any> = {};
        if (taskType === "rag_search") {
            payloadInput = { query: inputQuery, top_k: 5 };
        } else if (taskType === "rag_answer" || taskType === "database_query") {
            payloadInput = { question: inputQuery };
        } else if (taskType === "document_summary") {
            payloadInput = { text: inputQuery };
        } else {
            payloadInput = { prompt: inputQuery };
        }

        executeMutation.mutate(
            {
                task_type: taskType,
                input: payloadInput,
                execution_mode: executionMode,
                idempotency_key: idempotencyKey.trim() || undefined,
            },
            {
                onSuccess: (data) => setLastResult(data),
            }
        );
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Project 5 — AI Execution Manager"
                description="Orchestrates AI task lifecycle state tracking, capability routing, bounded retries, timeout policies, and execution metrics on Port 8001."
                breadcrumbs={[{ label: "Workspace" }, { label: "Execution Manager" }]}
                actions={
                    <div className="flex items-center gap-2 font-mono text-xs">
                        <span className="flex items-center gap-1.5 rounded-xl bg-primary/10 px-3 py-1.5 font-bold text-primary border border-primary/20">
                            <Cpu className="h-4 w-4" />
                            <span>Orchestration Layer</span>
                        </span>
                        <span className="flex items-center gap-1.5 rounded-xl bg-success/10 px-3 py-1.5 font-bold text-success border border-success/20">
                            <Server className="h-4 w-4" />
                            <span>Port 8001</span>
                        </span>
                    </div>
                }
            />

            {/* Main Execution Controls Section */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                {/* Form Inputs */}
                <div className="lg:col-span-1 rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4">
                    <div className="flex items-center gap-2 border-b border-border pb-3">
                        <Zap className="h-5 w-5 text-primary" />
                        <h3 className="text-sm font-bold text-foreground">Task Execution Controls</h3>
                    </div>

                    {/* Task Type Selector */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-muted-foreground font-mono">Task Capability</label>
                        <select
                            value={taskType}
                            onChange={(e) => setTaskType(e.target.value)}
                            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-mono text-foreground focus:border-primary focus:outline-none"
                        >
                            <option value="text_generation">text_generation (AIService)</option>
                            <option value="rag_answer">rag_answer (P3 RAG Pipeline)</option>
                            <option value="rag_search">rag_search (P3 Hybrid Search)</option>
                            <option value="database_query">database_query (P4 DB Agent)</option>
                            <option value="document_summary">document_summary (Document Summary)</option>
                        </select>
                    </div>

                    {/* Execution Mode Selector */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-muted-foreground font-mono">Execution Mode</label>
                        <select
                            value={executionMode}
                            onChange={(e) => setExecutionMode(e.target.value)}
                            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-mono text-foreground focus:border-primary focus:outline-none"
                        >
                            <option value="auto">auto (Smart Selector)</option>
                            <option value="local">local (Prefers Ollama)</option>
                            <option value="cloud">cloud (Prefers OpenRouter)</option>
                        </select>
                    </div>

                    {/* Optional Idempotency Key */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-muted-foreground font-mono">Idempotency Key (Optional)</label>
                        <input
                            type="text"
                            value={idempotencyKey}
                            onChange={(e) => setIdempotencyKey(e.target.value)}
                            placeholder="e.g. task-dedup-key-101"
                            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-mono text-foreground focus:border-primary focus:outline-none"
                        />
                    </div>

                    {/* Prompt / Input Payload Box */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-muted-foreground font-mono">Task Input Query / Prompt</label>
                        <textarea
                            value={inputQuery}
                            onChange={(e) => setInputQuery(e.target.value)}
                            rows={4}
                            placeholder="Enter task input prompt or question..."
                            className="w-full rounded-xl border border-border bg-background p-3 text-xs font-mono text-foreground focus:border-primary focus:outline-none"
                        />
                    </div>

                    <button
                        onClick={handleExecute}
                        disabled={!inputQuery.trim() || executeMutation.isPending}
                        className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary py-2.5 text-xs font-bold text-primary-foreground shadow-md disabled:opacity-40 transition-all"
                    >
                        {executeMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Play className="h-4 w-4 fill-current" />
                        )}
                        <span>Submit Task Execution</span>
                    </button>
                </div>

                {/* Live Result & Telemetry Details */}
                <div className="lg:col-span-2 rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4">
                    <div className="flex items-center justify-between border-b border-border pb-3">
                        <div className="flex items-center gap-2">
                            <Layers className="h-5 w-5 text-primary" />
                            <h3 className="text-sm font-bold text-foreground">Execution Lifecycle Inspector</h3>
                        </div>
                        {lastResult && (
                            <span className={`font-mono text-xs font-bold px-2.5 py-0.5 rounded-full border ${
                                lastResult.status === "COMPLETED"
                                    ? "bg-success/10 text-success border-success/20"
                                    : "bg-destructive/10 text-destructive border-destructive/20"
                            }`}>
                                Status: {lastResult.status}
                            </span>
                        )}
                    </div>

                    {executeMutation.isError && (
                        <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-xs text-destructive font-mono flex items-center gap-2">
                            <AlertCircle className="h-4 w-4 shrink-0" />
                            <span>Execution Error: {(executeMutation.error as Error).message}</span>
                        </div>
                    )}

                    {!lastResult && !executeMutation.isPending ? (
                        <div className="p-16 text-center text-xs text-muted-foreground font-mono space-y-2">
                            <Cpu className="h-8 w-8 mx-auto text-muted-foreground/40" />
                            <p>No active execution task submitted yet. Submit a task using the controls on the left.</p>
                        </div>
                    ) : executeMutation.isPending ? (
                        <div className="p-16 text-center text-xs text-muted-foreground font-mono space-y-3">
                            <Loader2 className="h-8 w-8 mx-auto animate-spin text-primary" />
                            <p className="text-primary font-bold">State Machine: RUNNING...</p>
                            <p className="text-xs">Enforcing timeout policies, capability handler, and metrics capture...</p>
                        </div>
                    ) : lastResult ? (
                        <div className="space-y-4">
                            {/* Execution Telemetry Badges */}
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
                                <div className="rounded-xl bg-background p-3 border border-border space-y-0.5">
                                    <span className="text-xs text-muted-foreground">EXECUTION ID</span>
                                    <p className="font-bold text-foreground truncate">{lastResult.execution_id}</p>
                                </div>
                                <div className="rounded-xl bg-background p-3 border border-border space-y-0.5">
                                    <span className="text-xs text-muted-foreground">RUNTIME PROVIDER</span>
                                    <p className="font-bold text-primary truncate">{lastResult.provider || "N/A"}</p>
                                </div>
                                <div className="rounded-xl bg-background p-3 border border-border space-y-0.5">
                                    <span className="text-xs text-muted-foreground">MODEL</span>
                                    <p className="font-bold text-primary truncate">{lastResult.model || "N/A"}</p>
                                </div>
                                <div className="rounded-xl bg-background p-3 border border-border space-y-0.5">
                                    <span className="text-xs text-muted-foreground">EXECUTION TIME</span>
                                    <p className="font-bold text-success">{lastResult.execution_time}s</p>
                                </div>
                            </div>

                            {/* Standardized Result Output */}
                            <div className="rounded-xl border border-border bg-background p-4 space-y-2">
                                <span className="text-xs font-mono font-bold text-muted-foreground uppercase tracking-wider">
                                    Standardized Task Output Result
                                </span>
                                <pre className="text-xs font-mono text-foreground bg-surface p-3 rounded-lg border border-border overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto">
                                    {JSON.stringify(lastResult.result, null, 2)}
                                </pre>
                            </div>
                        </div>
                    ) : null}
                </div>
            </div>

            {/* Execution History Log Table */}
            <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4">
                <div className="flex items-center justify-between border-b border-border pb-3">
                    <div className="flex items-center gap-2 font-bold text-xs text-foreground">
                        <History className="h-4 w-4 text-primary" />
                        <span>Tenant Execution History Logs ({history?.total || 0} Records)</span>
                    </div>
                    <span className="font-mono text-xs text-muted-foreground">
                        Multi-Tenant Isolated Trace Log
                    </span>
                </div>

                {historyLoading ? (
                    <div className="p-6 text-center text-xs text-muted-foreground animate-pulse font-mono">
                        Loading tenant execution history...
                    </div>
                ) : history?.items.length === 0 ? (
                    <div className="p-6 text-center text-xs text-muted-foreground font-mono">
                        No execution records stored yet.
                    </div>
                ) : (
                    <div className="overflow-x-auto rounded-xl border border-border">
                        <table className="w-full text-left font-mono text-xs">
                            <thead className="bg-background text-muted-foreground border-b border-border">
                                <tr>
                                    <th className="px-4 py-2.5 font-bold uppercase text-xs">Execution ID</th>
                                    <th className="px-4 py-2.5 font-bold uppercase text-xs">Task Type</th>
                                    <th className="px-4 py-2.5 font-bold uppercase text-xs">Status</th>
                                    <th className="px-4 py-2.5 font-bold uppercase text-xs">Provider / Model</th>
                                    <th className="px-4 py-2.5 font-bold uppercase text-xs">Duration</th>
                                    <th className="px-4 py-2.5 font-bold uppercase text-xs">Retries</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border/40">
                                {history?.items.map((item, idx) => (
                                    <tr key={idx} className="hover:bg-primary/5 transition-colors">
                                        <td className="px-4 py-2.5 font-bold text-primary truncate max-w-[120px]">
                                            {item.execution_id}
                                        </td>
                                        <td className="px-4 py-2.5 text-foreground">{item.task_type}</td>
                                        <td className="px-4 py-2.5">
                                            <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                                                item.status === "COMPLETED"
                                                    ? "bg-success/10 text-success border border-success/20"
                                                    : "bg-destructive/10 text-destructive border border-destructive/20"
                                            }`}>
                                                {item.status}
                                            </span>
                                        </td>
                                        <td className="px-4 py-2.5 text-muted-foreground truncate max-w-[180px]">
                                            {item.provider || "N/A"} ({item.model || "N/A"})
                                        </td>
                                        <td className="px-4 py-2.5 text-success font-bold">{item.execution_time}s</td>
                                        <td className="px-4 py-2.5 text-muted-foreground">{item.retry_count}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
