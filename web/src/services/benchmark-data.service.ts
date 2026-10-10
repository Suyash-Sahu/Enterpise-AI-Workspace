import prototypeData from "@/data/research/amof_prototype_results_v1.json";
import { evaluationService, EvaluationRunData } from "./evaluation.service";

export interface BenchmarkDataSet {
  dataset_type: string;
  version: string;
  warning: string;
  disclaimer: string;
  has_measured_data: boolean;
  active_run_id?: string;
  active_dataset_hash?: string;
  executive_summary: Record<string, { value: number; label: string; status: "MEASURED" | "ILLUSTRATIVE"; subtitle: string }>;
  baseline_comparison: Array<{
    baseline_name: string;
    routing_accuracy: number;
    avg_latency_ms: number;
    cost_per_1k_usd: number;
    tokens_per_task: number;
    completion_rate: number;
    privacy_leak_rate: number;
    status: "MEASURED" | "ILLUSTRATIVE";
  }>;
  cost_efficiency: {
    cost_per_1k_tasks: Array<{ strategy: string; cost_usd: number }>;
    potential_savings_vs_cloud_pct: number;
    status: "MEASURED" | "ILLUSTRATIVE";
  };
  token_efficiency: {
    by_complexity: Array<{ complexity: string; always_cloud: number; always_local: number; static_rule: number; amof: number }>;
    status: "MEASURED" | "ILLUSTRATIVE";
  };
  latency_analysis: {
    scenarios: Array<{ category: string; always_cloud: number; always_local: number; static_rule: number; amof: number }>;
    routing_overhead_ms: string;
    status: "MEASURED" | "ILLUSTRATIVE";
  };
  privacy_analysis: {
    confidential_tasks_sent_to_cloud: Array<{ strategy: string; leak_pct: number }>;
    status: "MEASURED" | "ILLUSTRATIVE";
  };
  execution_distribution: {
    local_pct: number;
    cloud_pct: number;
    breakdown: Array<{ complexity: string; local_pct: number; cloud_pct: number }>;
    status: "MEASURED" | "ILLUSTRATIVE";
  };
  task_automation: Array<{ category: string; completion_rate_pct: number }>;
  // No backend source exists for a per-category completion breakdown --
  // always ILLUSTRATIVE (Phase 14: every section must carry an explicit
  // status; this one previously had none at all).
  task_automation_status?: "ILLUSTRATIVE";
  rag_benchmark: Array<{ strategy: string; precision_1: number; precision_3: number; precision_5: number; context_relevance: number }>;
  // No RAG precision/recall benchmark exists in the backend -- always ILLUSTRATIVE.
  rag_benchmark_status?: "ILLUSTRATIVE";
  ablation_study: Array<{ configuration: string; completion: number; cost: number; privacy: number; verification: number; status: "MEASURED" | "ILLUSTRATIVE" }>;
  feature_comparison: Array<{ feature: string; chatbot: string; rag: string; generic_multi_agent: string; amof: string }>;
  // A design/capability comparison table, not an empirical claim execution
  // traces could ever measure -- QUALITATIVE, not MEASURED/ILLUSTRATIVE.
  feature_comparison_status?: "QUALITATIVE";
  efficiency_summary: {
    metrics: Array<{ metric: string; baseline: number; amof: number }>;
    status: "MEASURED" | "ILLUSTRATIVE";
  };
}

export class BenchmarkDataService {
  public static async getBenchmarkData(): Promise<BenchmarkDataSet> {
    const data: BenchmarkDataSet = JSON.parse(JSON.stringify(prototypeData));
    data.has_measured_data = false;

    // task_automation, rag_benchmark, and feature_comparison have no
    // real-data source anywhere in the backend (no per-category completion
    // breakdown, no RAG precision benchmark, and feature_comparison is a
    // qualitative design table, not something execution traces measure) --
    // and the prototype JSON never tagged them at all, so the page rendered
    // them with no disclaimer whatsoever. Phase 14: every section must
    // carry an explicit status, so these are always ILLUSTRATIVE.
    data.task_automation_status = "ILLUSTRATIVE";
    data.rag_benchmark_status = "ILLUSTRATIVE";
    data.feature_comparison_status = "QUALITATIVE";

    try {
      const runs = await evaluationService.listRuns();
      const completedRun = runs.find((r) => r.status === "completed");

      if (completedRun) {
        const details = await evaluationService.getRunDetails(completedRun.run_id);
        data.has_measured_data = true;
        data.active_run_id = completedRun.run_id;
        data.active_dataset_hash = completedRun.dataset_hash;
        const subtitle = `Run: ${completedRun.run_id.slice(0, 10)}`;

        if (details.metrics && details.metrics.length > 0) {
          const metricsMap = new Map<string, number>();
          details.metrics.forEach((m) => {
            if (m.metric_value !== null && m.metric_value !== undefined) {
              metricsMap.set(m.metric_name, m.metric_value);
            }
          });

          const overlayPct = (key: keyof BenchmarkDataSet["executive_summary"], metricName: string) => {
            if (!metricsMap.has(metricName)) return;
            const val = metricsMap.get(metricName)!;
            data.executive_summary[key] = {
              ...data.executive_summary[key],
              value: val,
              label: `${Math.round(val * 100)}%`,
              status: "MEASURED",
              subtitle,
            };
          };
          overlayPct("routing_accuracy", "routing_accuracy");
          overlayPct("completion_rate", "completion_rate");
          overlayPct("privacy_leak_rate", "privacy_leak_rate");
        }

        // Bug fixed here (Phase 14): baseline_comparison and ablation_study
        // are both structurally real-data-capable (BaselineRunner/
        // AblationRunner produce exactly these fields), but were never
        // overlaid -- every row stayed hardcoded ILLUSTRATIVE regardless of
        // whether details.baselines/ablations existed. That silent
        // permanent-fallback is the core integrity gap this phase fixes.
        if (details.baselines && details.baselines.length > 0) {
          data.baseline_comparison = details.baselines.map((b) => ({
            baseline_name: b.baseline_name,
            routing_accuracy: b.routing_accuracy,
            avg_latency_ms: b.avg_latency_ms,
            cost_per_1k_usd: b.total_cost,
            tokens_per_task: b.total_tokens,
            completion_rate: b.completion_rate,
            privacy_leak_rate: b.privacy_leak_rate,
            status: "MEASURED" as const,
          }));
        }

        if (details.ablations && details.ablations.length > 0) {
          data.ablation_study = details.ablations.map((a) => ({
            configuration: a.configuration_name,
            completion: Math.round(a.completion_rate * 100),
            cost: a.total_cost,
            privacy: Math.round((1 - a.privacy_leak_rate) * 100),
            verification: Math.round(a.verification_pass_rate * 100),
            status: "MEASURED" as const,
          }));
        }
      }
    } catch {
      // Fallback cleanly to prototype data if backend API is unreachable or no run exists.
      // Sections not overlaid above keep their existing ILLUSTRATIVE status
      // from amof_prototype_results_v1.json -- never silently promoted.
    }

    return data;
  }
}
