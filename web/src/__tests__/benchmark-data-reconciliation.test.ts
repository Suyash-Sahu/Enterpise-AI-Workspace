/**
 * Phase 14: benchmark data reconciliation.
 *
 * Asserts the property the phase exists to enforce: a section shows real
 * measured data when real data exists for it, and stays explicitly tagged
 * (never silently promoted, never untagged) when it doesn't.
 *
 * These are service-level rather than component-render tests: this project
 * has vitest but no jsdom/@testing-library setup, and the reconciliation
 * logic being verified lives entirely in BenchmarkDataService -- the page
 * only renders whatever status the service puts on each section.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

const listRuns = vi.fn();
const getRunDetails = vi.fn();

vi.mock("@/services/evaluation.service", () => ({
  evaluationService: {
    listRuns: (...args: unknown[]) => listRuns(...args),
    getRunDetails: (...args: unknown[]) => getRunDetails(...args),
  },
}));

import { BenchmarkDataService } from "@/services/benchmark-data.service";

const COMPLETED_RUN = {
  run_id: "run_abcdef123456",
  status: "completed",
  dataset_version: "amof_eval_v2",
  dataset_hash: "a".repeat(64),
  task_count: 20,
  completed_count: 20,
  failed_count: 0,
  created_at: "2026-09-20T00:00:00Z",
};

const MEASURED_BASELINES = [
  {
    baseline_name: "ALWAYS_CLOUD",
    routing_accuracy: 0.5,
    completion_rate: 0.8,
    avg_latency_ms: 1000,
    p95_latency_ms: 1500,
    total_cost: 1.25,
    total_tokens: 5000,
    privacy_leak_rate: 1.0,
  },
  {
    baseline_name: "AMOF",
    routing_accuracy: 0.85,
    completion_rate: 0.9,
    avg_latency_ms: 900,
    p95_latency_ms: 1300,
    total_cost: 0.4,
    total_tokens: 3000,
    privacy_leak_rate: 0.0,
  },
];

const MEASURED_ABLATIONS = [
  {
    configuration_name: "FULL AMOF",
    enabled_components: ["adaptive_routing"],
    disabled_components: [],
    routing_accuracy: 0.85,
    completion_rate: 0.9,
    avg_latency_ms: 900,
    p95_latency_ms: 1300,
    total_cost: 0.4,
    total_tokens: 3000,
    cache_hit_rate: 0.2,
    privacy_leak_rate: 0.0,
    verification_pass_rate: 0.95,
  },
];

describe("BenchmarkDataService reconciliation (Phase 14)", () => {
  beforeEach(() => {
    listRuns.mockReset();
    getRunDetails.mockReset();
  });

  it("keeps every section explicitly tagged when no completed run exists", async () => {
    listRuns.mockResolvedValue([]);

    const data = await BenchmarkDataService.getBenchmarkData();

    expect(data.has_measured_data).toBe(false);
    // Nothing may claim MEASURED without a run behind it.
    expect(data.baseline_comparison.every((b) => b.status === "ILLUSTRATIVE")).toBe(true);
    expect(data.ablation_study.every((a) => a.status === "ILLUSTRATIVE")).toBe(true);
    expect(data.executive_summary.routing_accuracy.status).toBe("ILLUSTRATIVE");
  });

  it("tags the sections that have no backend source at all, which previously rendered untagged", async () => {
    listRuns.mockResolvedValue([]);

    const data = await BenchmarkDataService.getBenchmarkData();

    expect(data.task_automation_status).toBe("ILLUSTRATIVE");
    expect(data.rag_benchmark_status).toBe("ILLUSTRATIVE");
    expect(data.feature_comparison_status).toBe("QUALITATIVE");
  });

  it("serves real measured baseline rows when a completed run has them", async () => {
    listRuns.mockResolvedValue([COMPLETED_RUN]);
    getRunDetails.mockResolvedValue({
      ...COMPLETED_RUN,
      metrics: [{ metric_name: "routing_accuracy", metric_value: 0.85 }],
      baselines: MEASURED_BASELINES,
      ablations: [],
    });

    const data = await BenchmarkDataService.getBenchmarkData();

    expect(data.has_measured_data).toBe(true);
    expect(data.active_run_id).toBe(COMPLETED_RUN.run_id);
    expect(data.baseline_comparison).toHaveLength(2);
    expect(data.baseline_comparison.every((b) => b.status === "MEASURED")).toBe(true);
    // Real values, not the prototype's 0.50/0.92 placeholders.
    expect(data.baseline_comparison.map((b) => b.baseline_name)).toEqual(["ALWAYS_CLOUD", "AMOF"]);
    expect(data.baseline_comparison[1].routing_accuracy).toBe(0.85);
    expect(data.executive_summary.routing_accuracy.status).toBe("MEASURED");
    expect(data.executive_summary.routing_accuracy.value).toBe(0.85);
  });

  it("serves real measured ablation rows, including privacy and verification, when present", async () => {
    listRuns.mockResolvedValue([COMPLETED_RUN]);
    getRunDetails.mockResolvedValue({
      ...COMPLETED_RUN,
      metrics: [],
      baselines: [],
      ablations: MEASURED_ABLATIONS,
    });

    const data = await BenchmarkDataService.getBenchmarkData();

    expect(data.ablation_study).toHaveLength(1);
    const row = data.ablation_study[0];
    expect(row.status).toBe("MEASURED");
    expect(row.configuration).toBe("FULL AMOF");
    expect(row.completion).toBe(90); // 0.90 -> 90%
    expect(row.privacy).toBe(100); // 1 - 0.0 leak -> 100
    expect(row.verification).toBe(95); // 0.95 -> 95%
  });

  it("does not promote a section to MEASURED when the run carries no data for it", async () => {
    listRuns.mockResolvedValue([COMPLETED_RUN]);
    getRunDetails.mockResolvedValue({
      ...COMPLETED_RUN,
      metrics: [],
      baselines: [],
      ablations: [],
    });

    const data = await BenchmarkDataService.getBenchmarkData();

    // A completed run exists, but it produced no baselines/ablations --
    // those sections must stay illustrative rather than inheriting the
    // run's "measured" standing.
    expect(data.has_measured_data).toBe(true);
    expect(data.baseline_comparison.every((b) => b.status === "ILLUSTRATIVE")).toBe(true);
    expect(data.ablation_study.every((a) => a.status === "ILLUSTRATIVE")).toBe(true);
  });

  it("falls back to explicitly-tagged illustrative data when the backend is unreachable", async () => {
    listRuns.mockRejectedValue(new Error("backend unreachable"));

    const data = await BenchmarkDataService.getBenchmarkData();

    expect(data.has_measured_data).toBe(false);
    expect(data.baseline_comparison.every((b) => b.status === "ILLUSTRATIVE")).toBe(true);
  });
});
