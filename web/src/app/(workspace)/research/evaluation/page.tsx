"use client";

// Screenshot-only research figure gallery for the AMOF-X paper. Frontend-local
// mock data (src/data/researchEvaluationMock.ts) — no API calls, no writes,
// no relation to the real /research evaluation route. Forces a fixed light
// palette regardless of the app's dark-mode class, since every tab here is
// meant to be captured as a paper figure.

import { useState, type ReactNode } from "react";
import {
    dagPerformance,
    failureResults,
    verificationResult,
    routingDecisions,
    routingSplit,
    approvalRecords,
    workflowResults,
    overviewMetrics,
    humanEffort,
} from "@/data/researchEvaluationMock";

const TABS = [
    "Overview",
    "Architecture",
    "Orchestration",
    "Routing",
    "Privacy",
    "Automation",
    "Verification",
    "Failure Containment",
    "Governance",
    "Human Effort",
] as const;
type Tab = (typeof TABS)[number];

function IllustrativeNote({ children = "Illustrative values — replace with measured experiment output." }: { children?: ReactNode }) {
    return <p className="mt-2 text-xs italic text-gray-500">{children}</p>;
}

function FigureLabel({ children }: { children: ReactNode }) {
    return <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">{children}</p>;
}

function SectionTitle({ children, subtitle }: { children: ReactNode; subtitle?: string }) {
    return (
        <div className="mb-4">
            <h2 className="text-lg font-semibold text-gray-900">{children}</h2>
            {subtitle && <p className="mt-1 text-sm text-gray-500">{subtitle}</p>}
        </div>
    );
}

function Box({ children, className = "" }: { children: ReactNode; className?: string }) {
    return (
        <div className={`rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 ${className}`}>
            {children}
        </div>
    );
}

function Arrow({ dir = "down" }: { dir?: "down" | "right" }) {
    return (
        <div className={`flex text-gray-300 ${dir === "down" ? "justify-center py-0.5" : "items-center px-1"}`} aria-hidden>
            {dir === "down" ? "↓" : "→"}
        </div>
    );
}

function FlowVertical({ steps }: { steps: { label: string; note?: string }[] }) {
    return (
        <div className="flex flex-col items-stretch">
            {steps.map((s, i) => (
                <div key={s.label}>
                    <Box>
                        <span className="font-medium">{s.label}</span>
                        {s.note && <span className="ml-2 text-gray-500">{s.note}</span>}
                    </Box>
                    {i < steps.length - 1 && <Arrow />}
                </div>
            ))}
        </div>
    );
}

function BarChart({
    data,
    series,
    unit = "ms",
}: {
    data: { label: string; values: { name: string; value: number; color: string }[] }[];
    series: { name: string; color: string }[];
    unit?: string;
}) {
    const max = Math.max(...data.flatMap((d) => d.values.map((v) => v.value)));
    return (
        <div className="space-y-3">
            <div className="flex gap-4 text-xs text-gray-500">
                {series.map((s) => (
                    <span key={s.name} className="flex items-center gap-1.5">
                        <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: s.color }} />
                        {s.name}
                    </span>
                ))}
            </div>
            <div className="space-y-2.5">
                {data.map((d) => (
                    <div key={d.label}>
                        <p className="mb-1 text-xs font-medium text-gray-600">{d.label}</p>
                        <div className="space-y-1">
                            {d.values.map((v) => (
                                <div key={v.name} className="flex items-center gap-2">
                                    <div className="h-4 flex-1 rounded-sm bg-gray-100">
                                        <div
                                            className="h-4 rounded-sm"
                                            style={{ width: `${(v.value / max) * 100}%`, backgroundColor: v.color }}
                                        />
                                    </div>
                                    <span className="w-16 shrink-0 text-right text-xs text-gray-500">
                                        {v.value} {unit}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

function Donut({ a, b, labelA, labelB }: { a: number; b: number; labelA: string; labelB: string }) {
    const pct = (a / (a + b)) * 100;
    return (
        <div className="flex items-center gap-6">
            <div
                className="size-28 shrink-0 rounded-full"
                style={{ background: `conic-gradient(#111827 0% ${pct}%, #d1d5db ${pct}% 100%)` }}
            />
            <div className="space-y-1.5 text-sm">
                <p className="flex items-center gap-2">
                    <span className="inline-block size-2.5 rounded-sm bg-gray-900" /> {labelA}: <b>{a}</b>
                </p>
                <p className="flex items-center gap-2">
                    <span className="inline-block size-2.5 rounded-sm bg-gray-300" /> {labelB}: <b>{b}</b>
                </p>
            </div>
        </div>
    );
}

function Table({ headers, rows }: { headers: string[]; rows: ReactNode[][] }) {
    return (
        <div className="overflow-x-auto rounded-md border border-gray-200">
            <table className="w-full border-collapse text-left text-sm">
                <thead>
                    <tr className="border-b border-gray-200 bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                        {headers.map((h) => (
                            <th key={h} className="px-3 py-2 font-medium">
                                {h}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                    {rows.map((r, i) => (
                        <tr key={i}>
                            {r.map((c, j) => (
                                <td key={j} className="px-3 py-2 text-gray-700">
                                    {c}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

function MetricCard({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-md border border-gray-200 bg-white p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
            <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
        </div>
    );
}

function Panel({ children }: { children: ReactNode }) {
    return <div className="rounded-lg border border-gray-200 bg-white p-5">{children}</div>;
}

const perfChartData = dagPerformance.map((d) => ({
    label: d.shape,
    values: [
        { name: "Sequential", value: d.sequentialMs, color: "#d1d5db" },
        { name: "AMOF-X", value: d.amofMs, color: "#111827" },
    ],
}));

function OverviewTab() {
    return (
        <div className="space-y-6">
            <FigureLabel>FIG. 14 — COMPLETE RESEARCH EVALUATION DASHBOARD</FigureLabel>
            <SectionTitle subtitle="Summary of every demonstrated mechanism, for a single-screenshot overview.">
                Complete Research Dashboard
            </SectionTitle>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {overviewMetrics.map((m) => (
                    <MetricCard key={m.label} label={m.label} value={m.value} />
                ))}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
                <Panel>
                    <p className="mb-3 text-sm font-semibold text-gray-900">Orchestration</p>
                    <BarChart data={perfChartData.slice(0, 3)} series={[{ name: "Sequential", color: "#d1d5db" }, { name: "AMOF-X", color: "#111827" }]} />
                </Panel>
                <Panel>
                    <p className="mb-3 text-sm font-semibold text-gray-900">Routing distribution</p>
                    <Donut a={routingSplit.local} b={routingSplit.cloud} labelA="LOCAL" labelB="CLOUD" />
                </Panel>
                <Panel>
                    <p className="mb-3 text-sm font-semibold text-gray-900">Verification</p>
                    <p className="text-3xl font-semibold text-gray-900">72 / 72</p>
                    <p className="text-sm text-gray-500">Corrupted outputs blocked</p>
                </Panel>
                <Panel>
                    <p className="mb-3 text-sm font-semibold text-gray-900">Automation: meeting → tasks</p>
                    <p className="text-sm text-gray-700">3 action items extracted → 3 tasks created → 3 verified</p>
                </Panel>
            </div>

            <IllustrativeNote>All figures above are demonstration data. See individual tabs for detail and sourcing notes.</IllustrativeNote>

            <Table
                headers={["Capability", "Status"]}
                rows={[
                    ["Architecture", "Demonstrated"],
                    ["Orchestration", "Demonstrated"],
                    ["Verification", "Demonstrated"],
                    ["Failure Containment", "Demonstrated"],
                    ["Privacy Routing", "Demonstrated"],
                    ["Workflow Automation", "Demonstrated"],
                    ["Human Effort", "Illustrative"],
                    ["Third-party Comparison", "Not yet measured"],
                ]}
            />
        </div>
    );
}

function ArchitectureTab() {
    const layers = [
        ["User Request", "Entry point for a supervised multi-agent run"],
        ["Supervisor", "Plans and coordinates multi-agent execution"],
        ["Plan / DAG", "Represents dependencies between tasks"],
        ["Agent Layer", "Specialised, read-only agents"],
        ["Verification", "Validates agent outputs before downstream execution"],
        ["Governance", "Controls side-effecting actions and approvals"],
        ["Executor", "Performs authorized mutations"],
        ["External Systems", "Gmail, Calendar, WorkGraph, DB"],
    ];
    const supporting = ["Privacy Router", "Model Gateway", "Shared Blackboard", "Approval Gateway", "Audit / Trace", "WorkGraph"];
    return (
        <div className="space-y-6">
            <FigureLabel>FIG. 1 — AMOF-X SYSTEM ARCHITECTURE</FigureLabel>
            <SectionTitle subtitle="Top-to-bottom request path, with supporting components used across layers.">
                System Architecture
            </SectionTitle>
            <Panel>
                <div className="flex flex-col items-center">
                    {layers.map(([label, desc], i) => (
                        <div key={label} className="w-full max-w-md">
                            <Box className="text-center">
                                <span className="font-medium">{label}</span>
                                <p className="text-xs text-gray-500">{desc}</p>
                            </Box>
                            {i < layers.length - 1 && <Arrow />}
                        </div>
                    ))}
                </div>
                <p className="mt-6 mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">Supporting components</p>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {supporting.map((s) => (
                        <Box key={s} className="text-center">
                            {s}
                        </Box>
                    ))}
                </div>
            </Panel>
        </div>
    );
}

function OrchestrationTab() {
    return (
        <div className="space-y-6">
            <FigureLabel>FIG. 2 — MULTI-AGENT DAG EXECUTION</FigureLabel>
            <SectionTitle subtitle="A five-step dependency graph, executed in dependency-aware waves.">
                Multi-Agent DAG Execution
            </SectionTitle>
            <Panel>
                <div className="flex flex-col items-center gap-3 text-sm">
                    <Box>Task A</Box>
                    <Arrow />
                    <div className="flex gap-8">
                        <Box>Task B</Box>
                        <Box>Task C</Box>
                    </div>
                    <Arrow />
                    <Box>Task D</Box>
                    <Arrow />
                    <Box>Task E</Box>
                </div>
                <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
                    {[["Wave 1", "Task A"], ["Wave 2", "Task B, Task C"], ["Wave 3", "Task D"], ["Wave 4", "Task E"]].map(
                        ([w, t]) => (
                            <Box key={w} className="text-center">
                                <p className="font-semibold">{w}</p>
                                <p className="text-xs text-gray-500">{t}</p>
                            </Box>
                        )
                    )}
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                    <MetricCard label="Total Steps" value="5" />
                    <MetricCard label="Execution Waves" value="4" />
                    <MetricCard label="Parallelizable Steps" value="2" />
                    <MetricCard label="Execution Mode" value="Dependency-aware" />
                </div>
            </Panel>

            <FigureLabel>FIG. 9 — SEQUENTIAL VS PARALLEL DAG PERFORMANCE</FigureLabel>
            <Panel>
                <BarChart data={perfChartData} series={[{ name: "Sequential", color: "#d1d5db" }, { name: "AMOF-X", color: "#111827" }]} />
                <IllustrativeNote />
                <div className="mt-4">
                    <Table
                        headers={["Shape", "Sequential (ms)", "AMOF-X (ms)"]}
                        rows={dagPerformance.map((d) => [d.shape, d.sequentialMs, d.amofMs])}
                    />
                </div>
            </Panel>
        </div>
    );
}

function RoutingTab() {
    return (
        <div className="space-y-6">
            <FigureLabel>FIG. 3 — ADAPTIVE LOCAL VS CLOUD ROUTING</FigureLabel>
            <SectionTitle subtitle="Privacy is a hard feasibility filter, applied before latency/quality-driven placement.">
                Adaptive Routing
            </SectionTitle>
            <div className="grid gap-4 lg:grid-cols-2">
                <Panel>
                    <FlowVertical
                        steps={[
                            { label: "Task" },
                            { label: "Privacy Check" },
                            { label: "Allowed / Restricted", note: "feasibility filter" },
                            { label: "Latency / Quality Evaluation", note: "when both placements feasible" },
                            { label: "LOCAL or CLOUD" },
                        ]}
                    />
                </Panel>
                <Panel>
                    <p className="mb-3 text-sm font-semibold text-gray-900">Routing decision card</p>
                    <Table
                        headers={["Field", "Value"]}
                        rows={[
                            ["Task", "Analyze internal project document"],
                            ["Sensitivity", "RESTRICTED"],
                            ["Latency Budget", "2.0 sec"],
                            ["Quality Floor", "0.85"],
                            ["Eligible Placement", "LOCAL"],
                            ["Selected Model", "Ollama"],
                            ["Cloud", "BLOCKED"],
                        ]}
                    />
                </Panel>
            </div>

            <FigureLabel>FIG. 12 — ROUTING DISTRIBUTION</FigureLabel>
            <Panel>
                <div className="grid gap-6 lg:grid-cols-2">
                    <Donut a={routingSplit.local} b={routingSplit.cloud} labelA="LOCAL" labelB="CLOUD" />
                    <div>
                        <MetricCard label="Privacy Violations (AMOF-X)" value="0" />
                    </div>
                </div>
                <div className="mt-4">
                    <Table
                        headers={["Task", "Sensitivity", "Placement", "Reason"]}
                        rows={routingDecisions.map((r) => [r.task, r.sensitivity, r.placement, r.reason])}
                    />
                </div>
                <IllustrativeNote />
            </Panel>
        </div>
    );
}

function PrivacyTab() {
    return (
        <div className="space-y-6">
            <FigureLabel>FIG. 4 — PRIVACY CLASSIFICATION PIPELINE</FigureLabel>
            <SectionTitle subtitle="A three-stage classifier resolves a sensitivity level, which then constrains placement.">
                Privacy Classification
            </SectionTitle>
            <div className="grid gap-4 lg:grid-cols-2">
                <Panel>
                    <FlowVertical
                        steps={[
                            { label: "Input Content" },
                            { label: "Regex / Checksum Rules" },
                            { label: "k-NN Exemplar Classification" },
                            { label: "Local LLM Judge" },
                            { label: "Sensitivity Level" },
                            { label: "Placement Constraint" },
                        ]}
                    />
                </Panel>
                <Panel>
                    <p className="mb-3 text-sm font-semibold text-gray-900">Sensitivity levels</p>
                    <div className="grid grid-cols-2 gap-2">
                        {["PUBLIC", "INTERNAL", "RESTRICTED", "CONFIDENTIAL"].map((l) => (
                            <Box key={l} className="text-center font-medium">
                                {l}
                            </Box>
                        ))}
                    </div>
                    <p className="mt-4 mb-3 text-sm font-semibold text-gray-900">Example classification</p>
                    <Table
                        headers={["Field", "Value"]}
                        rows={[
                            ["Classification", "RESTRICTED"],
                            ["Placement", "LOCAL ONLY"],
                            ["Cloud", "NOT ELIGIBLE"],
                        ]}
                    />
                    <p className="mt-3 text-xs text-gray-500">Privacy is a hard routing constraint, not a weighted factor.</p>
                </Panel>
            </div>
        </div>
    );
}

function AutomationTab() {
    return (
        <div className="space-y-6">
            <FigureLabel>FIG. 5 — WORKFLOW AUTOMATION</FigureLabel>
            <SectionTitle subtitle="Meeting action items are extracted, verified, and tracked with a scheduled follow-up.">
                Meeting → Task Automation
            </SectionTitle>
            <div className="grid gap-4 lg:grid-cols-2">
                <Panel>
                    <FlowVertical
                        steps={[
                            { label: "Meeting" },
                            { label: "Meeting Agent" },
                            { label: "Action Item Extraction" },
                            { label: "Task Creation" },
                            { label: "Verification" },
                            { label: "WorkGraph" },
                            { label: "Scheduled Follow-up" },
                        ]}
                    />
                </Panel>
                <Panel>
                    <Table
                        headers={["Field", "Value"]}
                        rows={[
                            ["Meeting", "AMOF-X Research Discussion"],
                            ["Extracted Action Items", "3"],
                            ["Created Tasks", "3"],
                            ["Verified", "3 / 3"],
                            ["Scheduled Follow-up", "Tomorrow, 09:00"],
                        ]}
                    />
                </Panel>
            </div>
            <Panel>
                <p className="mb-3 text-sm font-semibold text-gray-900">Generated tasks</p>
                <Table
                    headers={["Task", "Owner", "Due Date", "Verified"]}
                    rows={workflowResults.map((w) => [w.task, w.owner, w.dueDate, w.verified ? "Yes" : "No"])}
                />
            </Panel>
        </div>
    );
}

function VerificationTab() {
    const amof = verificationResult[0];
    const baseline = verificationResult[1];
    return (
        <div className="space-y-6">
            <FigureLabel>FIG. 6 — VERIFICATION-GATED EXECUTION</FigureLabel>
            <SectionTitle subtitle="Agent outputs are validated before they can reach downstream steps or shared state.">
                Verification-Gated Execution
            </SectionTitle>
            <div className="grid gap-4 lg:grid-cols-2">
                <Panel>
                    <FlowVertical steps={[{ label: "Agent Output" }, { label: "Output Verifier" }, { label: "ACCEPT → Next Agent / REJECT → Block Downstream" }]} />
                    <div className="mt-4 space-y-1 text-sm">
                        {["Schema Validation", "Type Validation", "Provenance", "Trust Boundary", "Required Fields"].map((c) => (
                            <div key={c} className="flex items-center justify-between border-b border-gray-100 py-1 last:border-0">
                                <span className="text-gray-600">{c}</span>
                                <span className="font-medium text-gray-900">✓</span>
                            </div>
                        ))}
                    </div>
                </Panel>
                <Panel>
                    <p className="mb-3 text-sm font-semibold text-gray-900">Rejected example</p>
                    <Table
                        headers={["Field", "Value"]}
                        rows={[
                            ["Output Status", "REJECTED"],
                            ["Reason", "Schema validation failed"],
                            ["Downstream Execution", "BLOCKED"],
                        ]}
                    />
                </Panel>
            </div>

            <FigureLabel>FIG. 11 — VERIFICATION EFFECTIVENESS</FigureLabel>
            <Panel>
                <div className="grid gap-4 sm:grid-cols-2">
                    <Box className="text-center">
                        <p className="text-xs text-gray-500">Corrupted outputs blocked (AMOF-X)</p>
                        <div className="mt-2 h-3 w-full rounded-sm bg-gray-100">
                            <div className="h-3 w-full rounded-sm bg-gray-900" />
                        </div>
                        <p className="mt-1 text-sm font-semibold">
                            {amof.rejected} / {amof.corruptedOutputs} (100%)
                        </p>
                    </Box>
                    <Box className="text-center">
                        <p className="text-xs text-gray-500">Downstream propagation</p>
                        <p className="mt-2 text-sm">
                            AMOF-X: <b>{amof.downstreamPoisoned}</b> · Final-Only Verification: <b>{baseline.downstreamPoisoned}</b>
                        </p>
                    </Box>
                </div>
                <div className="mt-4">
                    <Table
                        headers={["Configuration", "Corrupted Outputs", "Rejected", "Accepted", "Downstream Poisoned"]}
                        rows={verificationResult.map((v) => [v.label, v.corruptedOutputs, v.rejected, v.accepted, v.downstreamPoisoned])}
                    />
                </div>
                <IllustrativeNote />
            </Panel>
        </div>
    );
}

function FailureContainmentTab() {
    const amof = failureResults[0];
    return (
        <div className="space-y-6">
            <FigureLabel>FIG. 7 — FAILURE CONTAINMENT</FigureLabel>
            <SectionTitle subtitle="A single node failure blocks only its dependents; independent work is salvaged.">
                Failure Containment
            </SectionTitle>
            <div className="grid gap-4 lg:grid-cols-2">
                <Panel>
                    <div className="flex flex-col items-center gap-3 text-sm">
                        <Box>Task A</Box>
                        <Arrow />
                        <div className="flex gap-8">
                            <Box className="border-gray-900 bg-gray-50">Task B — Completed</Box>
                            <Box className="border-red-300 bg-red-50 text-red-700">Task C — FAILED</Box>
                        </div>
                        <Arrow />
                        <Box className="border-amber-300 bg-amber-50 text-amber-700">Dependent Tasks — BLOCKED</Box>
                    </div>
                </Panel>
                <Panel>
                    <div className="grid grid-cols-2 gap-3">
                        <MetricCard label="Failed Nodes" value="1" />
                        <MetricCard label="Dependent Nodes Blocked" value="3" />
                        <MetricCard label="Invalid Downstream Executions" value="0" />
                        <MetricCard label="Salvaged Independent Work" value={`${amof.salvagePct}%`} />
                    </div>
                </Panel>
            </div>

            <FigureLabel>FIG. 10 — FAILURE RECOVERY / SALVAGE COMPARISON</FigureLabel>
            <Panel>
                <BarChart
                    data={failureResults.map((f) => ({
                        label: f.strategy,
                        values: [{ name: "Salvage %", value: f.salvagePct, color: "#111827" }],
                    }))}
                    series={[{ name: "Salvage %", color: "#111827" }]}
                    unit="%"
                />
                <div className="mt-4">
                    <Table
                        headers={["Strategy", "Salvaged Work", "Blocked Dependents", "Invalid Downstream Executions"]}
                        rows={failureResults.map((f) => [f.strategy, `${f.salvagePct}%`, f.blockedDependents, f.invalidDownstream])}
                    />
                </div>
                <IllustrativeNote />
            </Panel>
        </div>
    );
}

function GovernanceTab() {
    const record = approvalRecords[0];
    return (
        <div className="space-y-6">
            <FigureLabel>FIG. 8 — GOVERNANCE / HUMAN APPROVAL</FigureLabel>
            <SectionTitle subtitle="Side-effecting AI proposals route through risk classification and an approval gateway.">
                Governance & Human Approval
            </SectionTitle>
            <div className="grid gap-4 lg:grid-cols-2">
                <Panel>
                    <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">AI Proposed Action</p>
                    <Table
                        headers={["Field", "Value"]}
                        rows={[
                            ["Action", "Create project tasks"],
                            ["Risk Level", "L3"],
                            ["Affected Items", "15"],
                            ["Reason", "Bulk mutation requires approval"],
                            ["Status", "PENDING APPROVAL"],
                        ]}
                    />
                    <div className="mt-4 flex gap-2">
                        <button type="button" disabled className="rounded-md border border-gray-900 bg-gray-900 px-3 py-1.5 text-sm font-medium text-white opacity-60">
                            Approve
                        </button>
                        <button type="button" disabled className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 opacity-60">
                            Reject
                        </button>
                    </div>
                </Panel>
                <Panel>
                    <FlowVertical
                        steps={[
                            { label: "AI Proposal" },
                            { label: "Risk Classification" },
                            { label: "Approval Gateway" },
                            { label: "Ownership Check" },
                            { label: "Kill-Switch Check" },
                            { label: "Blast-Radius Check" },
                            { label: "Authorized Executor" },
                        ]}
                    />
                </Panel>
            </div>
            <Panel>
                <p className="mb-3 text-sm font-semibold text-gray-900">Audit record</p>
                <Table
                    headers={["Approval ID", "Timestamp", "Action", "Decision", "Actor"]}
                    rows={[[record.approvalId, record.timestamp, record.action, record.decision, record.actor]]}
                />
            </Panel>
        </div>
    );
}

function HumanEffortTab() {
    const reduction = (((humanEffort.manualSeconds - humanEffort.amofSeconds) / humanEffort.manualSeconds) * 100).toFixed(1);
    return (
        <div className="space-y-6">
            <FigureLabel>FIG. 13 — HUMAN EFFORT</FigureLabel>
            <SectionTitle subtitle="Illustrative scenario comparing manual coordination to AMOF-X-assisted coordination.">
                Human Effort Comparison
            </SectionTitle>
            <div className="grid gap-4 lg:grid-cols-2">
                <Panel>
                    <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">Manual Coordination</p>
                    <FlowVertical
                        steps={[
                            { label: "Read Meeting" },
                            { label: "Identify Actions" },
                            { label: "Write Tasks" },
                            { label: "Assign Tasks" },
                            { label: "Set Due Dates" },
                            { label: "Schedule Follow-up" },
                        ]}
                    />
                </Panel>
                <Panel>
                    <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">AMOF-X</p>
                    <FlowVertical
                        steps={[
                            { label: "Meeting" },
                            { label: "AI Extraction" },
                            { label: "Verification" },
                            { label: "WorkGraph" },
                            { label: "Scheduled Follow-up" },
                        ]}
                    />
                </Panel>
            </div>
            <Panel>
                <div className="grid grid-cols-3 gap-3">
                    <MetricCard label="Manual workflow" value={`${humanEffort.manualSeconds} sec`} />
                    <MetricCard label="AMOF-X workflow" value={`${humanEffort.amofSeconds} sec`} />
                    <MetricCard label="Illustrative reduction" value={`${reduction}%`} />
                </div>
                <IllustrativeNote>Illustrative scenario — human-effort measurement not yet performed. This is not a user study.</IllustrativeNote>
            </Panel>
        </div>
    );
}

const TAB_CONTENT: Record<Tab, () => ReactNode> = {
    Overview: OverviewTab,
    Architecture: ArchitectureTab,
    Orchestration: OrchestrationTab,
    Routing: RoutingTab,
    Privacy: PrivacyTab,
    Automation: AutomationTab,
    Verification: VerificationTab,
    "Failure Containment": FailureContainmentTab,
    Governance: GovernanceTab,
    "Human Effort": HumanEffortTab,
};

export default function ResearchEvaluationScreenshotPage() {
    const [tab, setTab] = useState<Tab>("Overview");
    const Content = TAB_CONTENT[tab];

    return (
        <div className="min-h-screen bg-white text-gray-900">
            <div className="mx-auto w-full max-w-[1360px] px-6 py-8">
                <header className="mb-6">
                    <div className="flex flex-wrap items-center gap-3">
                        <h1 className="text-2xl font-semibold text-gray-900">AMOF-X · Research Evaluation</h1>
                        <span className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-amber-700">
                            Demonstration / Illustrative Data
                        </span>
                    </div>
                    <p className="mt-2 max-w-3xl text-sm text-gray-500">
                        Research evaluation interface for AMOF-X multi-agent orchestration, privacy-aware routing,
                        verification, governance, and workflow automation.
                    </p>
                </header>

                <nav className="mb-6 flex flex-wrap gap-1 border-b border-gray-200 pb-px">
                    {TABS.map((t) => (
                        <button
                            key={t}
                            type="button"
                            onClick={() => setTab(t)}
                            className={`rounded-t-md px-3 py-2 text-sm font-medium transition-colors ${
                                tab === t
                                    ? "border border-b-white border-gray-200 bg-white text-gray-900"
                                    : "border border-transparent text-gray-500 hover:text-gray-800"
                            }`}
                        >
                            {t}
                        </button>
                    ))}
                </nav>

                <Content />
            </div>
        </div>
    );
}
