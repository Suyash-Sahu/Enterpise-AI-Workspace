"use client";

import { useState } from "react";
import PageHeader from "@/components/shared/PageHeader";
import { useSupervisorHealth, useSupervisorExecute } from "@/hooks/useSupervisor";
import { SupervisorResultData } from "@/services/supervisor.service";
import {
    Bot,
    Sparkles,
    Cpu,
    CheckCircle2,
    Clock,
    ShieldCheck,
    Database,
    FileText,
    Search,
    AlertCircle,
    Copy,
    Check,
    Layers,
    Server,
    Loader2,
    ArrowRight,
    Terminal
} from "lucide-react";

export default function AMOFSupervisorPage() {
    const [question, setQuestion] = useState("");
    const [executionMode, setExecutionMode] = useState("auto");
    const [result, setResult] = useState<SupervisorResultData | null>(null);
    const [copied, setCopied] = useState(false);

    const { data: health, isLoading: healthLoading } = useSupervisorHealth();
    const executeMutation = useSupervisorExecute();

    const samplePrompts = [
        "How many documents do I have indexed?",
        "How does hybrid search work in my documents?",
        "Write a concise overview of the AMOF supervisor framework.",
        "Summarize the latest document specs.",
    ];

    const handleExecute = async (promptText?: string) => {
        const queryText = promptText || question;
        if (!queryText.trim()) return;

        try {
            const res = await executeMutation.mutateAsync({
                question: queryText,
                execution_mode: executionMode,
            });
            setResult(res);
        } catch (err) {
            console.error("Supervisor execution failed:", err);
        }
    };

    const handleCopy = (text: string) => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const getCapabilityIcon = (cap: string) => {
        switch (cap) {
            case "database_query":
                return <Database className="h-4 w-4 text-primary" />;
            case "rag_search":
            case "rag_answer":
                return <Search className="h-4 w-4 text-info" />;
            case "document_summary":
                return <FileText className="h-4 w-4 text-success" />;
            default:
                return <Bot className="h-4 w-4 text-warning" />;
        }
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Project 7 — AMOF Supervisor Orchestrator"
                description="Autonomous Multi-Agent Intent Router, DAG Plan Execution, & Grounded Response Synthesis on Port 8001."
                breadcrumbs={[{ label: "Workspace" }, { label: "AMOF Supervisor" }]}
                actions={
                    <div className="flex items-center gap-2 font-mono text-xs">
                        <span className="flex items-center gap-1.5 rounded-xl bg-primary/10 px-3 py-1.5 font-bold text-primary border border-primary/20">
                            <Bot className="h-4 w-4" />
                            <span>P7 Orchestrator</span>
                        </span>
                        <span className="flex items-center gap-1.5 rounded-xl bg-success/10 px-3 py-1.5 font-bold text-success border border-success/20">
                            <Server className="h-4 w-4" />
                            <span>Port 8001</span>
                        </span>
                    </div>
                }
            />

            {/* Operational Telemetry Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="rounded-2xl border border-border bg-surface p-4 flex items-center gap-3 shadow-sm">
                    <div className="rounded-xl bg-primary/10 border border-primary/20 p-2.5 text-primary">
                        <Cpu className="h-5 w-5" />
                    </div>
                    <div>
                        <div className="text-xs font-mono text-muted-foreground">Backend Host</div>
                        <div className="text-xs font-bold text-foreground">Port 8001 Shared Server</div>
                    </div>
                </div>

                <div className="rounded-2xl border border-border bg-surface p-4 flex items-center gap-3 shadow-sm">
                    <div className="rounded-xl bg-success/10 border border-success/20 p-2.5 text-success">
                        <Bot className="h-5 w-5" />
                    </div>
                    <div>
                        <div className="text-xs font-mono text-muted-foreground">Supervisor Status</div>
                        <div className="text-xs font-bold text-success flex items-center gap-1.5">
                            <span className="h-2 w-2 rounded-full bg-success animate-pulse" />
                            {health?.status === "online" ? "Online & Active" : "Initializing"}
                        </div>
                    </div>
                </div>

                <div className="rounded-2xl border border-border bg-surface p-4 flex items-center gap-3 shadow-sm">
                    <div className="rounded-xl bg-info/10 border border-info/20 p-2.5 text-info">
                        <Layers className="h-5 w-5" />
                    </div>
                    <div>
                        <div className="text-xs font-mono text-muted-foreground">Plan Depth Bound</div>
                        <div className="text-xs font-bold text-foreground">{health?.max_steps || 5} DAG Steps (Sequential)</div>
                    </div>
                </div>

                <div className="rounded-2xl border border-border bg-surface p-4 flex items-center gap-3 shadow-sm">
                    <div className="rounded-xl bg-warning/10 border border-warning/20 p-2.5 text-warning">
                        <ShieldCheck className="h-5 w-5" />
                    </div>
                    <div>
                        <div className="text-xs font-mono text-muted-foreground">Tenant Isolation</div>
                        <div className="text-xs font-bold text-foreground">JWT Token Protected</div>
                    </div>
                </div>
            </div>

            {/* Input & Execution Bar */}
            <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
                    <div className="flex items-center gap-2 text-foreground">
                        <Sparkles className="h-4 w-4 text-primary" />
                        <h3 className="text-sm font-bold">Ask AMOF Supervisor</h3>
                    </div>

                    {/* Execution Mode Selector */}
                    <div className="flex items-center gap-1.5 rounded-xl border border-border bg-background p-1 font-mono text-xs">
                        <span className="text-xs text-muted-foreground px-2 font-medium">Mode:</span>
                        {["auto", "local", "cloud"].map((mode) => (
                            <button
                                key={mode}
                                onClick={() => setExecutionMode(mode)}
                                className={`px-3 py-1 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                                    executionMode === mode
                                        ? "bg-primary text-primary-foreground shadow-sm"
                                        : "text-muted-foreground hover:text-foreground hover:bg-surface/50"
                                }`}
                            >
                                {mode.toUpperCase()}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex flex-col sm:flex-row gap-3">
                    <div className="relative flex-1">
                        <Search className="absolute left-3.5 top-3.5 h-4 w-4 text-muted-foreground" />
                        <input
                            type="text"
                            value={question}
                            onChange={(e) => setQuestion(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && handleExecute()}
                            placeholder="Ask anything... e.g. How many documents do I have indexed?"
                            className="w-full rounded-xl border border-border bg-background pl-10 pr-4 py-3 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
                        />
                    </div>
                    <button
                        onClick={() => handleExecute()}
                        disabled={executeMutation.isPending || !question.trim()}
                        className="flex items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3 text-xs font-bold text-primary-foreground shadow-md disabled:opacity-40 transition-all shrink-0 cursor-pointer"
                    >
                        {executeMutation.isPending ? (
                            <>
                                <Loader2 className="h-4 w-4 animate-spin" />
                                <span>Orchestrating...</span>
                            </>
                        ) : (
                            <>
                                <Sparkles className="h-4 w-4" />
                                <span>Ask Supervisor</span>
                            </>
                        )}
                    </button>
                </div>

                {/* Sample Prompt Chips */}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                    <span className="text-xs text-muted-foreground font-mono">Suggestions:</span>
                    {samplePrompts.map((prompt, idx) => (
                        <button
                            key={idx}
                            onClick={() => {
                                setQuestion(prompt);
                                handleExecute(prompt);
                            }}
                            className="text-xs bg-background hover:bg-surface border border-border text-muted-foreground hover:text-foreground px-3 py-1 rounded-lg transition-all cursor-pointer"
                        >
                            {prompt}
                        </button>
                    ))}
                </div>
            </div>

            {/* Results Section */}
            {result && (
                <div className="space-y-6">
                    {/* Intent & Confidence Header Card */}
                    <div className="rounded-2xl border border-border bg-surface p-5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 shadow-sm">
                        <div className="flex items-center gap-3">
                            <div className="rounded-xl bg-primary/10 border border-primary/20 p-2.5 text-primary">
                                {getCapabilityIcon(result.intent.capability)}
                            </div>
                            <div>
                                <div className="text-xs font-mono text-muted-foreground">Detected Capability Intent</div>
                                <div className="text-sm font-bold text-foreground flex items-center gap-2">
                                    <span className="capitalize">{result.intent.capability.replace("_", " ")}</span>
                                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-primary/20 text-primary border border-primary/30">
                                        {Math.round(result.intent.confidence * 100)}% Confidence
                                    </span>
                                </div>
                                <div className="text-xs text-muted-foreground mt-0.5">{result.intent.reason}</div>
                            </div>
                        </div>

                        <div className="flex items-center gap-3 text-xs font-mono">
                            <div className="bg-background px-3 py-1.5 rounded-xl border border-border text-muted-foreground">
                                Trace ID: <span className="text-foreground">{result.trace_id}</span>
                            </div>
                            <div className="bg-background px-3 py-1.5 rounded-xl border border-border text-muted-foreground flex items-center gap-1.5">
                                <Clock className="h-3.5 w-3.5 text-primary" />
                                <span>{result.execution_time}s</span>
                            </div>
                        </div>
                    </div>

                    {/* Execution Plan Stepper */}
                    <div className="rounded-2xl border border-border bg-surface p-5 space-y-4 shadow-sm">
                        <div className="flex items-center justify-between border-b border-border pb-3">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2 font-mono">
                                <Layers className="h-4 w-4 text-primary" />
                                Execution Plan & DAG Steps ({result.steps.length} Steps)
                            </h3>
                            <span className="text-xs font-mono text-muted-foreground">Sequential Pipeline</span>
                        </div>

                        <div className="space-y-3">
                            {result.steps.map((step, idx) => (
                                <div
                                    key={step.step_id}
                                    className="rounded-xl border border-border bg-background/90 p-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3"
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="h-7 w-7 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-bold flex items-center justify-center font-mono">
                                            {idx + 1}
                                        </div>
                                        <div>
                                            <div className="text-xs font-bold text-foreground flex items-center gap-2">
                                                <span className="capitalize">{step.capability.replace("_", " ")}</span>
                                                <span className="text-xs font-mono px-2 py-0.5 rounded bg-surface text-muted-foreground border border-border">
                                                    {step.purpose}
                                                </span>
                                            </div>
                                            {step.execution_id && (
                                                <div className="text-xs text-muted-foreground font-mono mt-0.5">
                                                    P5 Exec ID: {step.execution_id}
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-3 text-xs font-mono">
                                        <div className="flex items-center gap-1.5 text-success font-bold bg-success/10 px-2.5 py-1 rounded-lg border border-success/20">
                                            <CheckCircle2 className="h-3.5 w-3.5" />
                                            <span>{step.status}</span>
                                        </div>
                                        <div className="text-muted-foreground">
                                            {step.execution_time}s
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Synthesized Answer Card */}
                    <div className="rounded-2xl border border-border bg-surface p-6 space-y-4 shadow-sm">
                        <div className="flex justify-between items-center border-b border-border pb-3">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2 font-mono">
                                <Sparkles className="h-4 w-4 text-primary" />
                                Synthesized Grounded Response
                            </h3>
                            <button
                                onClick={() => handleCopy(result.answer)}
                                className="text-xs bg-background hover:bg-surface text-muted-foreground hover:text-foreground px-3 py-1.5 rounded-xl border border-border flex items-center gap-1.5 transition-all cursor-pointer"
                            >
                                {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
                                <span>{copied ? "Copied" : "Copy Answer"}</span>
                            </button>
                        </div>

                        <div className="text-xs text-foreground leading-relaxed whitespace-pre-wrap rounded-xl border border-border bg-background/90 p-5 font-sans">
                            {result.answer}
                        </div>
                    </div>

                    {/* Sources & Citations Grid */}
                    {result.sources && result.sources.length > 0 && (
                        <div className="rounded-2xl border border-border bg-surface p-5 space-y-4 shadow-sm">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2 font-mono">
                                <Search className="h-4 w-4 text-info" />
                                Attributed Sources & Trace Citations ({result.sources.length})
                            </h3>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {result.sources.map((src, idx) => (
                                    <div key={idx} className="rounded-xl border border-border bg-background p-3.5 text-xs space-y-1.5">
                                        <div className="font-bold text-foreground flex justify-between">
                                            <span>Source #{idx + 1}</span>
                                            {src.type && <span className="font-mono text-primary text-xs">{src.type}</span>}
                                        </div>
                                        {src.source && <div className="text-muted-foreground font-mono text-xs truncate">{src.source}</div>}
                                        {src.sql && <div className="text-muted-foreground font-mono text-xs bg-surface p-2 rounded-lg truncate">{src.sql}</div>}
                                        {src.content && <div className="text-muted-foreground line-clamp-2 text-xs">{src.content}</div>}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
