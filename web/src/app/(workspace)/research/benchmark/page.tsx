"use client";

import { useState, useEffect } from "react";
import PageHeader from "@/components/shared/PageHeader";
import { BenchmarkDataService, BenchmarkDataSet } from "@/services/benchmark-data.service";
import {
  BarChart3,
  AlertTriangle,
  Info,
  CheckCircle2,
  HelpCircle,
  FileSpreadsheet,
  FileCode,
  Shield,
  Zap,
  Cpu,
  DollarSign,
  Layers,
  Sparkles,
  Bot,
  Database,
  Search,
  Check,
  XCircle,
  Clock,
  ArrowRight,
  TrendingDown,
  TrendingUp,
  PieChart,
} from "lucide-react";

/**
 * Builds the copyable paper table from whatever baseline_comparison actually
 * holds, rather than the hardcoded literals this block used to contain.
 *
 * Phase 14: the previous version printed fixed numbers (1,420 ms / $18.40 /
 * 2,450 tokens ...) and a literal "ILLUSTRATIVE" for four of its seven rows,
 * regardless of whether a real measured run existed -- so a reader copying
 * this table into the paper would have pasted prototype estimates even when
 * the dashboard above it was showing measured data.
 */
function buildReportTable(data: BenchmarkDataSet): string {
  const rows = data.baseline_comparison;
  if (rows.length === 0) return "No baseline data available.";

  const header = `| Metric | ${rows.map((r) => r.baseline_name).join(" | ")} | Status |`;
  const divider = `| :--- | ${rows.map(() => ":---").join(" | ")} | :--- |`;
  // Per-row status comes from the baseline rows themselves: every value in a
  // given row is drawn from the same source, so the row's tag is accurate by
  // construction rather than asserted separately.
  const status = rows.every((r) => r.status === "MEASURED") ? "MEASURED" : "ILLUSTRATIVE";

  const line = (label: string, fmt: (r: BenchmarkDataSet["baseline_comparison"][number]) => string) =>
    `| ${label} | ${rows.map(fmt).join(" | ")} | ${status} |`;

  return [
    header,
    divider,
    line("Routing Accuracy", (r) => `${Math.round(r.routing_accuracy * 100)}%`),
    line("Task Completion Rate", (r) => `${Math.round(r.completion_rate * 100)}%`),
    line("Average Latency (ms)", (r) => `${Math.round(r.avg_latency_ms).toLocaleString()} ms`),
    line("Cost / 1K Tasks ($USD)", (r) => `$${r.cost_per_1k_usd.toFixed(2)}`),
    line("Tokens / Task", (r) => r.tokens_per_task.toLocaleString()),
    line("Privacy Leak Rate", (r) => `${Math.round(r.privacy_leak_rate * 100)}%`),
  ].join("\n");
}

export default function BenchmarkDemonstrationPage() {
  const [data, setData] = useState<BenchmarkDataSet | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<"overview" | "baselines" | "efficiency" | "privacy" | "rag" | "ablation" | "report">("overview");

  useEffect(() => {
    async function loadBenchmarkData() {
      setLoading(true);
      const res = await BenchmarkDataService.getBenchmarkData();
      setData(res);
      setLoading(false);
    }
    loadBenchmarkData();
  }, []);

  const handleExportJSON = () => {
    if (!data) return;
    const jsonStr = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "amof_prototype_results_v1.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const handleExportCSV = () => {
    if (!data) return;
    // Status is derived, not hardcoded: exporting a file stamped
    // "ILLUSTRATIVE" over real measured rows (or vice versa) is exactly the
    // mislabeling Phase 14 exists to remove.
    const exportStatus = data.baseline_comparison.every((b) => b.status === "MEASURED")
      ? "MEASURED"
      : "ILLUSTRATIVE";
    let csv = "Dataset Type,Version,Status,Warning\n";
    csv += `${data.dataset_type},${data.version},${exportStatus},"${data.warning}"\n\n`;
    csv += "Metric,Always Cloud,Always Local,Static Rule,AMOF,Status\n";
    data.baseline_comparison.forEach((b) => {
      csv += `"${b.baseline_name}",${b.cost_per_1k_usd},${b.tokens_per_task},${b.avg_latency_ms},${b.routing_accuracy},${b.status}\n`;
    });
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "amof_benchmark_comparison.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center min-h-[600px]">
        <div className="flex flex-col items-center space-y-4">
          <div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-slate-300 text-sm font-medium">Loading Benchmark Demonstration System...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-16 text-slate-100">
      {/* Custom Bright Visible Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800/80 pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-foreground">
            AMOF Research Evaluation &amp; Benchmark Demonstration
          </h1>
          <p className="mt-2 text-sm sm:text-base font-medium text-gray-700 leading-relaxed">
            Multi-Agent Orchestration, Adaptive Routing &amp; Enterprise AI Efficiency presentation layer for academic evaluation.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700 rounded-xl text-sm font-semibold transition shadow-sm"
          >
            <FileSpreadsheet className="w-4 h-4 text-success" />
            Export CSV
          </button>
          <button
            onClick={handleExportJSON}
            className="flex items-center gap-2 px-4 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-primary-foreground rounded-xl text-sm font-semibold transition shadow-md shadow-cyan-600/30"
          >
            <FileCode className="w-4 h-4 text-primary-foreground" />
            Export JSON Artifact
          </button>
        </div>
      </div>

      {/* Prominent Warning Banner (Cyan / Slate - Zero Yellow / Zero Purple) */}
      <div className="bg-slate-900/90 border border-cyan-500/40 rounded-2xl p-5 backdrop-blur-md flex items-start gap-4 shadow-md shadow-cyan-950/30">
        <div className="p-2.5 bg-cyan-500/20 rounded-xl text-cyan-400 mt-0.5 border border-cyan-500/30">
          <Info className="w-6 h-6" />
        </div>
        <div className="flex-1 space-y-1.5">
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 uppercase tracking-wider">
              {data.dataset_type}
            </span>
            <span className="text-xs text-slate-300 font-mono">Dataset Version: {data.version}</span>
          </div>
          <h4 className="text-base font-bold text-primary-foreground">{data.warning}</h4>
          <p className="text-sm text-slate-300 leading-relaxed">{data.disclaimer}</p>
        </div>
      </div>

      {/* Navigation Tabs (Cyan / Indigo / Slate Accent) */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2 overflow-x-auto">
        {[
          { id: "overview", label: "Executive Summary" },
          { id: "baselines", label: "Baseline Comparison" },
          { id: "efficiency", label: "Cost & Token Efficiency" },
          { id: "privacy", label: "Privacy & Routing" },
          { id: "rag", label: "RAG & Automation" },
          { id: "ablation", label: "Ablation & Capability" },
          { id: "report", label: "Report Table & Insights" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-4 py-2.5 rounded-xl text-sm font-semibold transition whitespace-nowrap ${activeTab === tab.id
              ? "bg-cyan-600 text-primary-foreground shadow-md shadow-cyan-600/30"
              : "text-gray-700 hover:text-primary-foreground hover:bg-slate-800/80"
              }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB 1: EXECUTIVE SUMMARY */}
      {activeTab === "overview" && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            {Object.entries(data.executive_summary).map(([key, item]) => (
              <div
                key={key}
                className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 backdrop-blur-md relative overflow-hidden group hover:border-slate-700 transition shadow-sm"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${item.status === "MEASURED"
                      ? "bg-success/20 text-success border border-success/40"
                      : "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                      }`}
                  >
                    {item.status}
                  </span>
                </div>
                <div className="text-3xl font-semibold text-primary-foreground tracking-tight">{item.label}</div>
                <p className="text-xs text-slate-400 mt-2 font-medium">{item.subtitle}</p>
              </div>
            ))}
          </div>

          {/* Multi-Agent Orchestration Visual Trace */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 backdrop-blur-md space-y-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-primary-foreground flex items-center gap-2">
                  <Bot className="w-5 h-5 text-cyan-400" />
                  Multi-Agent Orchestration Workflow Scenario
                </h3>
                <p className="text-sm text-slate-300 mt-1">
                  Illustrative execution trace demonstrating task decomposition, local/cloud routing, verification, and human approval.
                </p>
              </div>
              <span className="px-3 py-1 bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 rounded-full text-xs font-bold">
                Illustrative Execution Trace
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              {[
                { step: "1. Request", title: "User Query", detail: "Multi-agent contract analysis & email draft", mode: "INPUT" },
                { step: "2. Decomposition", title: "AMOF Supervisor", detail: "DAG task graph generation & intent classification", mode: "LOCAL" },
                { step: "3. Execution", title: "Domain Agents", detail: "RAG Doc (Local), DB Query (Local), Writing Agent (Cloud)", mode: "HYBRID" },
                { step: "4. Guard", title: "Verification & P8", detail: "Schema check (Passed), Side-effect approval gate triggered", mode: "APPROVAL" },
                { step: "5. Output", title: "Final Workspace Response", detail: "Verified synthesis & queued draft for user review", mode: "COMPLETED" },
              ].map((item, idx) => (
                <div key={idx} className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex flex-col justify-between hover:border-slate-700 transition">
                  <div>
                    <span className="text-xs font-semibold text-cyan-400 uppercase tracking-wider">{item.step}</span>
                    <h5 className="text-sm font-bold text-primary-foreground mt-1">{item.title}</h5>
                    <p className="text-xs text-slate-300 mt-2 leading-relaxed">{item.detail}</p>
                  </div>
                  <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                    <span className="text-slate-400 font-medium">Mode:</span>
                    <span className="font-bold text-success">{item.mode}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: BASELINE COMPARISON */}
      {activeTab === "baselines" && (
        <div className="space-y-6">
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 backdrop-blur-md space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-primary-foreground">Baseline Strategy Comparison Matrix</h3>
                <p className="text-sm text-slate-300">
                  {data.baseline_comparison.every((b) => b.status === "MEASURED")
                    ? "Measured comparative evaluation across Always Cloud, Always Local, Static Rule, and AMOF."
                    : "Illustrative comparative evaluation across Always Cloud, Always Local, Static Rule, and AMOF."}
                </p>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-xs font-bold border ${data.baseline_comparison.every((b) => b.status === "MEASURED")
                  ? "bg-success/10 text-success border-success/30"
                  : "bg-cyan-500/10 text-cyan-300 border-cyan-500/30"
                  }`}
              >
                {data.baseline_comparison.every((b) => b.status === "MEASURED") ? "Measured Run" : "Illustrative Scenario"}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-200">
                <thead className="bg-slate-950 text-xs font-bold uppercase tracking-wider text-slate-300 border-b border-slate-800">
                  <tr>
                    <th className="py-3.5 px-4">Evaluation Strategy</th>
                    <th className="py-3.5 px-4">Routing Accuracy</th>
                    <th className="py-3.5 px-4">Avg Latency (ms)</th>
                    <th className="py-3.5 px-4">Cost / 1K Tasks</th>
                    <th className="py-3.5 px-4">Tokens / Task</th>
                    <th className="py-3.5 px-4">Completion Rate</th>
                    <th className="py-3.5 px-4">Privacy Leak Rate</th>
                    <th className="py-3.5 px-4">Data Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {data.baseline_comparison.map((row, idx) => (
                    <tr
                      key={idx}
                      className={
                        row.baseline_name.includes("AMOF")
                          ? "bg-cyan-950/60 font-semibold text-primary-foreground border-l-4 border-l-cyan-400"
                          : "hover:bg-slate-800/50"
                      }
                    >
                      <td className="py-4 px-4 flex items-center gap-2 font-bold">
                        {row.baseline_name.includes("AMOF") && <Sparkles className="w-4 h-4 text-cyan-400" />}
                        {row.baseline_name}
                      </td>
                      <td className="py-4 px-4 font-semibold text-slate-100">{Math.round(row.routing_accuracy * 100)}%</td>
                      <td className="py-4 px-4 font-semibold text-slate-100">{row.avg_latency_ms} ms</td>
                      <td className="py-4 px-4 font-semibold text-slate-100">${row.cost_per_1k_usd.toFixed(2)}</td>
                      <td className="py-4 px-4 font-semibold text-slate-100">{row.tokens_per_task.toLocaleString()}</td>
                      <td className="py-4 px-4 font-semibold text-slate-100">{Math.round(row.completion_rate * 100)}%</td>
                      <td className="py-4 px-4 text-cyan-300 font-bold">{Math.round(row.privacy_leak_rate * 100)}%</td>
                      <td className="py-4 px-4">
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: COST & TOKEN EFFICIENCY */}
      {activeTab === "efficiency" && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Cost Chart */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 backdrop-blur-md space-y-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h4 className="text-base font-bold text-primary-foreground flex items-center gap-2">
                  <DollarSign className="w-5 h-5 text-success" />
                  Estimated Cost per 1,000 Tasks ($USD)
                </h4>
                <span className="text-xs text-cyan-300 font-bold">Illustrative</span>
              </div>
              <div className="space-y-4 pt-2">
                {data.cost_efficiency.cost_per_1k_tasks.map((item, idx) => (
                  <div key={idx} className="space-y-1.5">
                    <div className="flex justify-between text-xs font-semibold">
                      <span className="text-slate-200">{item.strategy}</span>
                      <span className="text-primary-foreground font-mono font-bold">${item.cost_usd.toFixed(2)}</span>
                    </div>
                    <div className="w-full bg-slate-950 rounded-full h-3.5 overflow-hidden p-0.5 border border-slate-800">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${item.strategy.includes("AMOF") ? "bg-success shadow-md" : "bg-slate-700"
                          }`}
                        style={{ width: `${(item.cost_usd / 20.0) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="p-3.5 bg-success/10 border border-success/30 rounded-xl text-xs text-emerald-200 font-medium">
                AMOF adaptive routing achieves an estimated <strong>~{data.cost_efficiency.potential_savings_vs_cloud_pct.toFixed(1)}% cost reduction</strong> vs Always Cloud strategy (Illustrative Calculation).
              </div>
            </div>

            {/* Token Usage Chart */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 backdrop-blur-md space-y-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h4 className="text-base font-bold text-primary-foreground flex items-center gap-2">
                  <Layers className="w-5 h-5 text-cyan-400" />
                  Average Tokens per Task by Complexity
                </h4>
                <span className="text-xs text-cyan-300 font-bold">Illustrative</span>
              </div>
              <div className="space-y-5 pt-2">
                {data.token_efficiency.by_complexity.map((row, idx) => (
                  <div key={idx} className="space-y-2">
                    <span className="text-xs font-bold text-slate-200">{row.complexity}</span>
                    <div className="grid grid-cols-4 gap-2 text-xs text-slate-300 text-center font-mono">
                      <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 font-medium">Cloud: {row.always_cloud}</div>
                      <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 font-medium">Local: {row.always_local}</div>
                      <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 font-medium">Static: {row.static_rule}</div>
                      <div className="bg-cyan-950 text-cyan-200 p-2.5 rounded-lg border border-cyan-500/40 font-bold">AMOF: {row.amof}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: PRIVACY & ROUTING */}
      {activeTab === "privacy" && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Privacy Leakage Chart */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 backdrop-blur-md space-y-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h4 className="text-base font-bold text-primary-foreground flex items-center gap-2">
                  <Shield className="w-5 h-5 text-cyan-400" />
                  Confidential Tasks Sent to Cloud (%)
                </h4>
                <span className="text-xs text-cyan-300 font-bold">Illustrative</span>
              </div>
              <div className="space-y-4 pt-2">
                {data.privacy_analysis.confidential_tasks_sent_to_cloud.map((item, idx) => (
                  <div key={idx} className="space-y-1.5">
                    <div className="flex justify-between text-xs font-semibold">
                      <span className="text-slate-200">{item.strategy}</span>
                      <span className={item.leak_pct > 20 ? "text-slate-300 font-bold" : "text-success font-bold"}>
                        {item.leak_pct}%
                      </span>
                    </div>
                    <div className="w-full bg-slate-950 rounded-full h-3.5 overflow-hidden p-0.5 border border-slate-800">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${item.leak_pct > 20 ? "bg-slate-600" : "bg-success"
                          }`}
                        style={{ width: `${item.leak_pct}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Execution Distribution */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 backdrop-blur-md space-y-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h4 className="text-base font-bold text-primary-foreground flex items-center gap-2">
                  <PieChart className="w-5 h-5 text-info" />
                  AMOF Execution Mode Distribution
                </h4>
                <span className="text-xs text-cyan-300 font-bold">Illustrative</span>
              </div>
              <div className="grid grid-cols-2 gap-4 p-4 bg-slate-950 rounded-xl border border-slate-800 text-center">
                <div>
                  <div className="text-2xl font-semibold text-success">{data.execution_distribution.local_pct}%</div>
                  <div className="text-xs text-slate-300 mt-1 font-semibold">Local Execution</div>
                </div>
                <div>
                  <div className="text-2xl font-semibold text-info">{data.execution_distribution.cloud_pct}%</div>
                  <div className="text-xs text-slate-300 mt-1 font-semibold">Cloud Execution</div>
                </div>
              </div>
              <div className="space-y-3 pt-2">
                <h5 className="text-xs font-bold text-slate-200">Complexity Breakdown:</h5>
                {data.execution_distribution.breakdown.map((b, idx) => (
                  <div key={idx} className="flex items-center justify-between text-xs text-slate-300 bg-slate-950 p-3 rounded-lg border border-slate-800/80 font-medium">
                    <span className="text-slate-100 font-semibold">{b.complexity}</span>
                    <span className="font-mono text-success font-bold">Local {b.local_pct}% / Cloud {b.cloud_pct}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: RAG & AUTOMATION */}
      {activeTab === "rag" && (
        <div className="space-y-8">
          {/* RAG Benchmark Table */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 backdrop-blur-md space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h4 className="text-base font-bold text-primary-foreground flex items-center gap-2">
                <Search className="w-5 h-5 text-cyan-400" />
                RAG Retrieval Precision & Context Relevance Comparison
              </h4>
              <span className="text-xs text-cyan-300 font-bold">
                {data.rag_benchmark_status ?? "ILLUSTRATIVE"} -- no RAG precision benchmark implemented
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-200">
                <thead className="bg-slate-950 text-xs font-bold uppercase tracking-wider text-slate-300 border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-4">Search Strategy</th>
                    <th className="py-3 px-4">Precision@1</th>
                    <th className="py-3 px-4">Precision@3</th>
                    <th className="py-3 px-4">Precision@5</th>
                    <th className="py-3 px-4">Context Relevance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {data.rag_benchmark.map((row, idx) => (
                    <tr key={idx} className={row.strategy.includes("Hybrid") ? "bg-cyan-950/60 font-bold text-primary-foreground border-l-4 border-l-cyan-400" : ""}>
                      <td className="py-3.5 px-4 font-semibold">{row.strategy}</td>
                      <td className="py-3.5 px-4 font-semibold">{row.precision_1}%</td>
                      <td className="py-3.5 px-4 font-semibold">{row.precision_3}%</td>
                      <td className="py-3.5 px-4 font-semibold">{row.precision_5}%</td>
                      <td className="py-3.5 px-4 text-success font-semibold">{row.context_relevance}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Task Automation Rates */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 backdrop-blur-md space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h4 className="text-base font-bold text-primary-foreground flex items-center gap-2">
                <Bot className="w-5 h-5 text-success" />
                Enterprise Task Unassisted Automation Rates (%)
              </h4>
              <span className="text-xs text-cyan-300 font-bold">
                {data.task_automation_status ?? "ILLUSTRATIVE"} -- no per-category completion breakdown implemented
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {data.task_automation.map((item, idx) => (
                <div key={idx} className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-1">
                  <div className="text-2xl font-semibold text-primary-foreground">{item.completion_rate_pct}%</div>
                  <div className="text-xs text-slate-300 font-semibold">{item.category}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 6: ABLATION & CAPABILITY */}
      {activeTab === "ablation" && (
        <div className="space-y-8">
          {/* Ablation Study Matrix */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 backdrop-blur-md space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h4 className="text-base font-bold text-primary-foreground">Component Ablation Study Matrix</h4>
              <span className={`text-xs font-bold ${data.ablation_study.every((a) => a.status === "MEASURED") ? "text-success" : "text-cyan-300"}`}>
                {data.ablation_study.every((a) => a.status === "MEASURED") ? "Measured Ablation" : "Illustrative Ablation"}
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-200">
                <thead className="bg-slate-950 text-xs font-bold uppercase tracking-wider text-slate-300 border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-4">Configuration</th>
                    <th className="py-3 px-4">Task Completion (%)</th>
                    <th className="py-3 px-4">Relative Cost Index</th>
                    <th className="py-3 px-4">Privacy Score</th>
                    <th className="py-3 px-4">Verification Score</th>
                    <th className="py-3 px-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {data.ablation_study.map((row, idx) => (
                    <tr key={idx} className={row.configuration.includes("Full") ? "bg-cyan-950/60 font-bold text-primary-foreground border-l-4 border-l-cyan-400" : ""}>
                      <td className="py-3.5 px-4 font-semibold">{row.configuration}</td>
                      <td className="py-3.5 px-4 font-semibold">{row.completion}%</td>
                      <td className="py-3.5 px-4 font-semibold">{row.cost}</td>
                      <td className="py-3.5 px-4 font-semibold">{row.privacy}%</td>
                      <td className="py-3.5 px-4 text-success font-semibold">{row.verification}%</td>
                      <td className="py-3.5 px-4">
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Qualitative Feature Matrix */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 backdrop-blur-md space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h4 className="text-base font-bold text-primary-foreground">System Capability Matrix</h4>
              <span className="text-xs text-cyan-300 font-bold">
                {data.feature_comparison_status ?? "QUALITATIVE"} -- design comparison, not an execution measurement
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-200">
                <thead className="bg-slate-950 uppercase font-bold tracking-wider text-slate-300 border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-4">Architectural Capability</th>
                    <th className="py-3 px-4">Traditional Chatbot</th>
                    <th className="py-3 px-4">Single-Model RAG</th>
                    <th className="py-3 px-4">Generic Multi-Agent</th>
                    <th className="py-3 px-4 text-cyan-400 font-semibold">AMOF Workspace</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {data.feature_comparison.map((row, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/40">
                      <td className="py-3 px-4 font-bold text-slate-100">{row.feature}</td>
                      <td className="py-3 px-4 text-slate-300 font-medium">{row.chatbot}</td>
                      <td className="py-3 px-4 text-slate-300 font-medium">{row.rag}</td>
                      <td className="py-3 px-4 text-slate-300 font-medium">{row.generic_multi_agent}</td>
                      <td className="py-3 px-4 text-success font-semibold">{row.amof}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 7: REPORT TABLE & INSIGHTS */}
      {activeTab === "report" && (
        <div className="space-y-8">
          {/* Copyable Paper Table */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 backdrop-blur-md space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-base font-bold text-primary-foreground">Project Report Evaluation Table</h4>
                <p className="text-xs text-slate-300 font-medium">Standard formatting suitable for academic project report insertion.</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 text-slate-200 font-mono text-xs font-bold rounded-lg border border-slate-700">Copyable Format</span>
            </div>

            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-xs text-slate-200 overflow-x-auto whitespace-pre leading-relaxed">
              {buildReportTable(data)}
            </div>
          </div>

          {/* Research Insights Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {[
              { title: "Adaptive Routing Hypothesis", text: "AMOF is designed to dynamically allocate tasks between local open-weight models and cloud LLMs based on task complexity, privacy requirements, and capability models." },
              { title: "Privacy Protection Architecture", text: "Confidential tasks are constrained to local execution runtimes to prevent sensitive enterprise data from leaving the local security perimeter." },
              { title: "Hybrid Retrieval Optimization", text: "Combining keyword BM25 and vector semantic embeddings aims to maximize precision@k across unstructured enterprise document repositories." },
              { title: "Human Approval Safety Guard (P8)", text: "External side-effect actions (such as sending emails or modifying calendar events) require explicit HITL approval to prevent unverified automated executions." },
            ].map((insight, idx) => (
              <div key={idx} className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 backdrop-blur-md space-y-2 shadow-sm">
                <h5 className="text-sm font-bold text-cyan-300 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-cyan-400" />
                  {insight.title}
                </h5>
                <p className="text-xs text-slate-300 leading-relaxed font-medium">{insight.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
