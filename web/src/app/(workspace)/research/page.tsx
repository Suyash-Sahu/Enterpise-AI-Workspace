"use client";

import { useState } from "react";
import PageHeader from "@/components/shared/PageHeader";
import {
    useEvaluationHealth,
    useEvaluationRuns,
    useEvaluationRunDetails,
    useEvaluationResults,
    useStartEvaluationRun,
} from "@/hooks/useEvaluation";
import { evaluationService } from "@/services/evaluation.service";
import {
    BarChart3,
    Play,
    RefreshCw,
    Download,
    FileSpreadsheet,
    FileCode,
    CheckCircle2,
    XCircle,
    Clock,
    Shield,
    Database,
    Zap,
    Cpu,
    DollarSign,
    Layers,
    AlertTriangle,
    Info,
    Check,
    Sparkles,
} from "lucide-react";

export default function ResearchEvaluationPage() {
    const { data: health, isLoading: isHealthLoading, refetch: refetchHealth } = useEvaluationHealth();
    const { data: runs, isLoading: isRunsLoading, refetch: refetchRuns } = useEvaluationRuns();
    const startRunMutation = useStartEvaluationRun();

    const [selectedRunId, setSelectedRunId] = useState<string | undefined>(undefined);

    const activeRunId = selectedRunId || (runs && runs.length > 0 ? runs[0].run_id : undefined);
    const { data: activeRun, isLoading: isRunDetailsLoading } = useEvaluationRunDetails(activeRunId);
    const { data: activeResults, isLoading: isResultsLoading } = useEvaluationResults(activeRunId);

    const handleRunEvaluation = () => {
        startRunMutation.mutate(
            { dataset_version: "amof_eval_v1", run_baselines: true, run_ablations: true },
            {
                onSuccess: (data) => {
                    setSelectedRunId(data.run_id);
                    refetchRuns();
                },
            }
        );
    };

    const handleExportCSV = async () => {
        if (!activeRunId) return;
        try {
            await evaluationService.downloadCsv(activeRunId);
        } catch (e) {
            console.error("Export CSV failed", e);
        }
    };

    const handleExportJSON = async () => {
        if (!activeRunId) return;
        try {
            await evaluationService.downloadJson(activeRunId);
        } catch (e) {
            console.error("Export JSON failed", e);
        }
    };

    const metricMap = new Map<string, number>();
    if (activeRun?.metrics) {
        activeRun.metrics.forEach((m) => metricMap.set(m.metric_name, m.metric_value));
    }

    const hasRuns = runs && runs.length > 0;

    return (
        <div className="space-y-8 max-w-7xl mx-auto pb-12">
            <PageHeader
                title="AMOF Research Evaluation & Benchmarking"
                description="Project 10 empirical evaluation framework measuring routing accuracy, latency, token efficiency, cost, privacy-leak risk, and component ablations."
                breadcrumbs={[{ label: "Workspace" }, { label: "Research & Evaluation" }]}
                actions={
                    <div className="flex flex-wrap items-center gap-2">
                        <button
                            onClick={() => {
                                refetchHealth();
                                refetchRuns();
                            }}
                            className="flex items-center gap-1.5 rounded-xl border border-border bg-surface px-3 py-2 text-xs font-semibold text-foreground hover:bg-muted transition-all"
                        >
                            <RefreshCw className="h-3.5 w-3.5" />
                            <span>Refresh</span>
                        </button>

                        {activeRunId && (
                            <>
                                <button
                                    onClick={handleExportCSV}
                                    className="flex items-center gap-1.5 rounded-xl border border-border bg-surface px-3 py-2 text-xs font-semibold text-foreground hover:bg-muted transition-all"
                                >
                                    <FileSpreadsheet className="h-3.5 w-3.5 text-success" />
                                    <span>Export CSV</span>
                                </button>
                                <button
                                    onClick={handleExportJSON}
                                    className="flex items-center gap-1.5 rounded-xl border border-border bg-surface px-3 py-2 text-xs font-semibold text-foreground hover:bg-muted transition-all"
                                >
                                    <FileCode className="h-3.5 w-3.5 text-info" />
                                    <span>Export JSON</span>
                                </button>
                            </>
                        )}

                        <button
                            disabled={startRunMutation.isPending}
                            onClick={handleRunEvaluation}
                            className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-xs font-bold text-primary-foreground shadow-md transition-all disabled:opacity-50 cursor-pointer"
                        >
                            {startRunMutation.isPending ? (
                                <RefreshCw className="h-4 w-4 animate-spin" />
                            ) : (
                                <Play className="h-4 w-4 fill-current" />
                            )}
                            <span>{startRunMutation.isPending ? "Executing Evaluation..." : "Run Evaluation"}</span>
                        </button>
                    </div>
                }
            />

            {/* Dataset Metadata & System Health Bar */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Dataset Card */}
                <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-3">
                    <div className="flex items-center justify-between border-b border-border pb-2.5">
                        <div className="flex items-center gap-2">
                            <Database className="h-4.5 w-4.5 text-cyan-400" />
                            <h3 className="text-xs font-bold text-foreground">Evaluation Dataset Metadata</h3>
                        </div>
                        <span className="font-mono text-xs font-bold text-cyan-400">
                            {health?.dataset_version || "amof_eval_v1"}
                        </span>
                    </div>

                    {health?.dataset_configured ? (
                        <div className="space-y-1.5 text-xs">
                            <div className="flex justify-between">
                                <span className="text-muted-foreground">Version:</span>
                                <span className="font-mono font-bold text-foreground">{health.dataset_version}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-muted-foreground">Total Tasks:</span>
                                <span className="font-mono font-bold text-foreground">{health.total_tasks_in_dataset} Benchmark Tasks</span>
                            </div>
                            <div className="flex flex-col gap-0.5 pt-1">
                                <span className="text-muted-foreground text-xs">SHA-256 Hash:</span>
                                <span className="font-mono text-xs text-primary truncate">{health.dataset_hash || "Calculated on run"}</span>
                            </div>
                        </div>
                    ) : (
                        <div className="text-xs text-orange-400 flex items-center gap-2">
                            <AlertTriangle className="h-4 w-4 shrink-0" />
                            <span>No evaluation dataset configured.</span>
                        </div>
                    )}
                </div>

                {/* System Operational Telemetry */}
                <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-3">
                    <div className="flex items-center justify-between border-b border-border pb-2.5">
                        <div className="flex items-center gap-2">
                            <Shield className="h-4.5 w-4.5 text-success" />
                            <h3 className="text-xs font-bold text-foreground">System Health Telemetry</h3>
                        </div>
                        <span className="font-mono text-xs font-bold text-success">GET /api/v1/evaluation/health</span>
                    </div>

                    <div className="space-y-2 text-xs">
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">Engine Status:</span>
                            <span className="font-mono font-bold text-success flex items-center gap-1">
                                <CheckCircle2 className="h-3.5 w-3.5" /> Operational
                            </span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">Persisted Runs:</span>
                            <span className="font-mono font-bold text-foreground">{health?.total_evaluation_runs || 0} Runs</span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">Zero Mock Policy:</span>
                            <span className="font-mono text-xs font-bold text-primary">Strict Empirical Observability</span>
                        </div>
                    </div>
                </div>

                {/* Run Selection Selector */}
                <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-3">
                    <div className="flex items-center justify-between border-b border-border pb-2.5">
                        <div className="flex items-center gap-2">
                            <BarChart3 className="h-4.5 w-4.5 text-info" />
                            <h3 className="text-xs font-bold text-foreground">Select Benchmark Run</h3>
                        </div>
                        <span className="font-mono text-xs font-bold text-info">
                            {runs?.length || 0} Available
                        </span>
                    </div>

                    {hasRuns ? (
                        <div className="space-y-2">
                            <select
                                value={activeRunId || ""}
                                onChange={(e) => setSelectedRunId(e.target.value)}
                                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground font-mono focus:border-primary focus:outline-none"
                            >
                                {runs.map((r) => (
                                    <option key={r.run_id} value={r.run_id}>
                                        {r.run_id} ({r.status.toUpperCase()}) • {r.created_at ? new Date(r.created_at).toLocaleTimeString() : ""}
                                    </option>
                                ))}
                            </select>
                            {activeRun && (
                                <div className="text-xs font-mono text-muted-foreground flex justify-between">
                                    <span>Tasks: {activeRun.task_count}</span>
                                    <span>Git: {activeRun.git_commit ? activeRun.git_commit.substring(0, 7) : "N/A"}</span>
                                </div>
                            )}
                        </div>
                    ) : (
                        <p className="text-xs text-muted-foreground">No evaluation runs available. Click 'Run Evaluation' above to execute a benchmark run.</p>
                    )}
                </div>
            </div>

            {/* Empty State Banner when no run exists */}
            {!hasRuns && !isRunsLoading && (
                <div className="rounded-md border border-border bg-surface p-12 text-center space-y-4">
                    <div className="flex justify-center">
                        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary border border-primary/20">
                            <BarChart3 className="h-8 w-8" />
                        </div>
                    </div>
                    <div className="space-y-2 max-w-md mx-auto">
                        <h2 className="text-xl font-bold text-foreground">No Evaluation Runs Available</h2>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                            The evaluation database currently contains 0 benchmarking runs.
                            Click the <strong>"Run Evaluation"</strong> button to execute all dataset tasks through the AMOF supervisor pipeline and measure real routing accuracy, latency, and costs.
                        </p>
                    </div>
                    <button
                        onClick={handleRunEvaluation}
                        disabled={startRunMutation.isPending}
                        className="inline-flex items-center gap-2 rounded-2xl bg-primary px-6 py-3 text-xs font-bold text-primary-foreground shadow-md transition-all cursor-pointer"
                    >
                        <Play className="h-4 w-4 fill-current" />
                        <span>Run Benchmark Evaluation</span>
                    </button>
                </div>
            )}

            {/* Run Metrics Grid */}
            {activeRun && (
                <>
                    {/* Key Metrics Cards */}
                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
                                <Zap className="h-5 w-5 text-primary" />
                                Benchmark Metrics Overview (Run: <span className="font-mono text-primary">{activeRun.run_id}</span>)
                            </h2>
                            <span className="font-mono text-xs font-bold text-success uppercase">
                                Status: {activeRun.status}
                            </span>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                            {/* Routing Accuracy */}
                            <div className="rounded-2xl border border-border bg-surface p-4 space-y-1 hover:border-primary/40 transition-all">
                                <span className="text-xs font-bold text-muted-foreground uppercase">Routing Accuracy</span>
                                <div className="text-2xl font-semibold text-foreground">
                                    {metricMap.has("routing_accuracy")
                                        ? `${(metricMap.get("routing_accuracy")! * 100).toFixed(1)}%`
                                        : "N/A — measurement unavailable"}
                                </div>
                                <span className="text-xs font-mono text-success">AMOF Adaptive Decision</span>
                            </div>

                            {/* Task Completion Rate */}
                            <div className="rounded-2xl border border-border bg-surface p-4 space-y-1 hover:border-primary/40 transition-all">
                                <span className="text-xs font-bold text-muted-foreground uppercase">Completion Rate</span>
                                <div className="text-2xl font-semibold text-foreground">
                                    {metricMap.has("completion_rate")
                                        ? `${(metricMap.get("completion_rate")! * 100).toFixed(1)}%`
                                        : "N/A — measurement unavailable"}
                                </div>
                                <span className="text-xs font-mono text-primary">
                                    {activeRun.completed_count}/{activeRun.task_count} Tasks Completed
                                </span>
                            </div>

                            {/* Average Latency */}
                            <div className="rounded-2xl border border-border bg-surface p-4 space-y-1 hover:border-primary/40 transition-all">
                                <span className="text-xs font-bold text-muted-foreground uppercase">Average Latency</span>
                                <div className="text-2xl font-semibold text-foreground">
                                    {metricMap.has("avg_latency_ms")
                                        ? `${metricMap.get("avg_latency_ms")} ms`
                                        : "N/A — measurement unavailable"}
                                </div>
                                <span className="text-xs font-mono text-info">
                                    P95: {metricMap.get("p95_latency_ms") || 0} ms
                                </span>
                            </div>

                            {/* Privacy Leakage */}
                            <div className="rounded-2xl border border-border bg-surface p-4 space-y-1 hover:border-primary/40 transition-all">
                                <span className="text-xs font-bold text-muted-foreground uppercase">Privacy Leak Rate</span>
                                <div className="text-2xl font-semibold text-foreground">
                                    {metricMap.has("privacy_leak_rate")
                                        ? `${(metricMap.get("privacy_leak_rate")! * 100).toFixed(1)}%`
                                        : "N/A — measurement unavailable"}
                                </div>
                                <span className="text-xs font-mono text-cyan-400">Sensitive Tasks Cloud Exposure</span>
                            </div>
                        </div>
                    </div>

                    {/* Baseline Comparison Matrix */}
                    {activeRun.baselines && activeRun.baselines.length > 0 && (
                        <div className="space-y-4">
                            <div className="flex items-center gap-2">
                                <Layers className="h-5 w-5 text-primary" />
                                <h3 className="text-sm font-bold text-foreground">Controlled Baseline Comparison</h3>
                            </div>

                            <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
                                <table className="w-full text-left border-collapse text-xs">
                                    <thead>
                                        <tr className="border-b border-border bg-muted/40 font-mono text-xs text-muted-foreground uppercase">
                                            <th className="p-3.5">Baseline Strategy</th>
                                            <th className="p-3.5">Routing Accuracy</th>
                                            <th className="p-3.5">Completion Rate</th>
                                            <th className="p-3.5">Avg Latency</th>
                                            <th className="p-3.5">P95 Latency</th>
                                            <th className="p-3.5">Total Cost</th>
                                            <th className="p-3.5">Tokens</th>
                                            <th className="p-3.5">Privacy Leakage</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border/60">
                                        {activeRun.baselines.map((b, idx) => (
                                            <tr key={idx} className={b.baseline_name === "AMOF" ? "bg-primary/10 font-bold" : "hover:bg-muted/30"}>
                                                <td className="p-3.5 font-mono font-bold text-foreground flex items-center gap-2">
                                                    {b.baseline_name === "AMOF" && <Sparkles className="h-4 w-4 text-primary" />}
                                                    <span>{b.baseline_name}</span>
                                                </td>
                                                <td className="p-3.5 font-mono font-bold text-foreground">{(b.routing_accuracy * 100).toFixed(1)}%</td>
                                                <td className="p-3.5 font-mono text-foreground">{(b.completion_rate * 100).toFixed(1)}%</td>
                                                <td className="p-3.5 font-mono text-foreground">{b.avg_latency_ms} ms</td>
                                                <td className="p-3.5 font-mono text-foreground">{b.p95_latency_ms} ms</td>
                                                <td className="p-3.5 font-mono text-success">${b.total_cost.toFixed(4)}</td>
                                                <td className="p-3.5 font-mono text-foreground">{b.total_tokens}</td>
                                                <td className="p-3.5 font-mono text-cyan-400">{(b.privacy_leak_rate * 100).toFixed(1)}%</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* Ablation Study Table */}
                    {activeRun.ablations && activeRun.ablations.length > 0 && (
                        <div className="space-y-4">
                            <div className="flex items-center gap-2">
                                <Cpu className="h-5 w-5 text-cyan-400" />
                                <h3 className="text-sm font-bold text-foreground">Component Ablation Analysis</h3>
                            </div>

                            <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
                                <table className="w-full text-left border-collapse text-xs">
                                    <thead>
                                        <tr className="border-b border-border bg-muted/40 font-mono text-xs text-muted-foreground uppercase">
                                            <th className="p-3.5">Configuration</th>
                                            <th className="p-3.5">Enabled Components</th>
                                            <th className="p-3.5">Routing Accuracy</th>
                                            <th className="p-3.5">Completion Rate</th>
                                            <th className="p-3.5">Avg Latency</th>
                                            <th className="p-3.5">Cache Hit Rate</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border/60">
                                        {activeRun.ablations.map((a, idx) => (
                                            <tr key={idx} className="hover:bg-muted/30">
                                                <td className="p-3.5 font-mono font-bold text-foreground">{a.configuration_name}</td>
                                                <td className="p-3.5 text-xs text-muted-foreground">
                                                    {a.enabled_components.join(", ")}
                                                </td>
                                                <td className="p-3.5 font-mono font-bold text-foreground">{(a.routing_accuracy * 100).toFixed(1)}%</td>
                                                <td className="p-3.5 font-mono text-foreground">{(a.completion_rate * 100).toFixed(1)}%</td>
                                                <td className="p-3.5 font-mono text-foreground">{a.avg_latency_ms} ms</td>
                                                <td className="p-3.5 font-mono text-success">{(a.cache_hit_rate * 100).toFixed(1)}%</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* Task Execution Breakdown Table */}
                    {activeResults && activeResults.length > 0 && (
                        <div className="space-y-4">
                            <div className="flex items-center gap-2">
                                <Clock className="h-5 w-5 text-info" />
                                <h3 className="text-sm font-bold text-foreground">Empirical Task Execution Breakdown</h3>
                            </div>

                            <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
                                <table className="w-full text-left border-collapse text-xs">
                                    <thead>
                                        <tr className="border-b border-border bg-muted/40 font-mono text-xs text-muted-foreground uppercase">
                                            <th className="p-3">Task ID</th>
                                            <th className="p-3">Task Prompt</th>
                                            <th className="p-3">Category</th>
                                            <th className="p-3">Privacy</th>
                                            <th className="p-3">Expected Mode</th>
                                            <th className="p-3">Actual Mode</th>
                                            <th className="p-3">Latency</th>
                                            <th className="p-3">Result</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border/60">
                                        {activeResults.map((t) => (
                                            <tr key={t.task_id} className="hover:bg-muted/30">
                                                <td className="p-3 font-mono font-bold text-primary">{t.task_id}</td>
                                                <td className="p-3 text-foreground font-medium truncate max-w-xs">{t.task_text}</td>
                                                <td className="p-3 font-mono text-muted-foreground">{t.category}</td>
                                                <td className="p-3 font-mono uppercase text-xs">
                                                    <span className={`px-2 py-0.5 rounded-full font-bold ${
                                                        t.privacy_level === "confidential" ? "bg-destructive/20 text-destructive" :
                                                        t.privacy_level === "internal" ? "bg-orange-500/20 text-orange-400" : "bg-success/20 text-success"
                                                    }`}>
                                                        {t.privacy_level}
                                                    </span>
                                                </td>
                                                <td className="p-3 font-mono uppercase text-muted-foreground">{t.expected_execution_mode}</td>
                                                <td className="p-3 font-mono uppercase font-bold text-foreground">{t.actual_execution_mode}</td>
                                                <td className="p-3 font-mono text-foreground">{t.latency_ms} ms</td>
                                                <td className="p-3">
                                                    {t.completion_success ? (
                                                        <span className="inline-flex items-center gap-1 font-mono text-success font-bold text-xs">
                                                            <CheckCircle2 className="h-3.5 w-3.5" /> PASSED
                                                        </span>
                                                    ) : (
                                                        <span className="inline-flex items-center gap-1 font-mono text-destructive font-bold text-xs">
                                                            <XCircle className="h-3.5 w-3.5" /> FAILED
                                                        </span>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
