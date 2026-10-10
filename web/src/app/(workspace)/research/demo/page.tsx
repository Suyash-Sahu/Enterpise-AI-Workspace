import type { ReactNode } from "react";
import {
    AlertTriangle,
    ArrowDown,
    CheckCircle2,
    FlaskConical,
    ScrollText,
    ShieldCheck,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// Deterministic, hard-coded illustration of AMOF-X mechanisms. This page makes
// no API calls, reads no database and writes nothing: it cannot touch
// production data and none of the values below is a measurement.
// Order follows the paper's own emphasis: decomposition -> verification ->
// automation -> governance -> case study -> supporting placement mechanism.
// Mechanism references: app/supervisor/supervisor.py (scheduler, verifier gate,
// preset_plan automation entrypoint), app/execution/executor.py (approval gate),
// app/services/work_ai/{guard,automations}.py (autonomy, blast-radius, kill switch),
// app/api/meetings.py (meeting -> task case study), app/privacy/router.py.

export const metadata = { title: "Research Demonstration" };

const DEMO_VALUE = "Demonstration value — not an experimental measurement";

function Flow({ steps }: { steps: { label: string; note?: string; tone?: "ok" | "block" }[] }) {
    return (
        <ol className="flex flex-col items-stretch gap-1">
            {steps.map((s, i) => (
                <li key={s.label} className="flex flex-col items-center gap-1">
                    <div
                        className={`w-full rounded-lg border px-3 py-2 text-sm ${
                            s.tone === "block"
                                ? "border-destructive/40 bg-destructive/10"
                                : "border-border bg-muted/40"
                        }`}
                    >
                        <span className="font-medium">{s.label}</span>
                        {s.note && <span className="ml-2 text-muted-foreground">{s.note}</span>}
                    </div>
                    {i < steps.length - 1 && <ArrowDown className="size-4 text-muted-foreground" aria-hidden />}
                </li>
            ))}
        </ol>
    );
}

function Scenario({ n, title, desc, children }: { n: number; title: string; desc: string; children: ReactNode }) {
    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between gap-2">
                    <CardTitle>
                        Scenario {n} — {title}
                    </CardTitle>
                    <Badge variant="warning">Synthetic</Badge>
                </div>
                <CardDescription>{desc}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">{children}</CardContent>
        </Card>
    );
}

function Row({ k, v, badge }: { k: string; v: string; badge?: "success" | "destructive" | "info" }) {
    return (
        <div className="flex items-center justify-between gap-3 border-b border-border/60 py-1.5 text-sm last:border-0">
            <span className="text-muted-foreground">{k}</span>
            {badge ? <Badge variant={badge}>{v}</Badge> : <span className="font-medium">{v}</span>}
        </div>
    );
}

export default function ResearchDemoPage() {
    return (
        <div className="mx-auto max-w-6xl space-y-6 p-6">
            <div
                role="note"
                className="flex items-start gap-3 rounded-xl border border-warning/50 bg-warning/10 p-4"
            >
                <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warning" aria-hidden />
                <div>
                    <p className="font-semibold">Research Demonstration — Synthetic / Mock Evaluation Data</p>
                    <p className="text-sm text-muted-foreground">
                        Demonstration is not experiment: every scenario is a deterministic, hard-coded illustration
                        of an implemented mechanism. Nothing here is read from the live system, and nothing is a
                        measured result. Measured results appear only in the paper (Section IX), from stored
                        artifacts.
                    </p>
                </div>
            </div>

            <header className="space-y-1">
                <h1 className="flex items-center gap-2 text-2xl font-semibold">
                    <FlaskConical className="size-6" aria-hidden /> AMOF-X System Demonstration
                </h1>
                <p className="text-sm text-muted-foreground">
                    Multi-agent orchestration, verification-gated fault containment, governed AI workflow
                    automation, and one traced workflow case study. Local/cloud model placement is one supporting
                    mechanism, shown last.
                </p>
            </header>

            <Card>
                <CardHeader>
                    <CardTitle>Architecture summary</CardTitle>
                    <CardDescription>Eight layers; verification and governance sit on the dataflow between agents and state.</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                        {[
                            "1 · Workspace UI",
                            "2 · API + authentication",
                            "3 · Supervisor / orchestration",
                            "4 · Specialised agents (read-only)",
                            "5 · Verification + governance",
                            "6 · Celery automation (same governed path)",
                            "7 · Gmail · Drive · Calendar · RAG · DB · WorkGraph",
                            "8 · Local / cloud inference (supporting)",
                        ].map((l) => (
                            <div key={l} className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
                                {l}
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>

            <div className="grid gap-6 lg:grid-cols-2">
                <Scenario
                    n={1}
                    title="Multi-agent decomposition and wave scheduling"
                    desc="The supervisor validates a dependency graph; independent steps run in the same wave."
                >
                    <Flow
                        steps={[
                            { label: "User request" },
                            { label: "Supervisor", note: "plan + validate_dag_plan" },
                            { label: "Wave 1: Document Agent · Data Agent", note: "independent, run together" },
                            { label: "Wave 2: Meeting Agent", note: "depends on wave 1" },
                            { label: "Aggregate + verify + respond" },
                        ]}
                    />
                </Scenario>

                <Scenario
                    n={2}
                    title="Verification-gated fault containment"
                    desc="A step whose output fails its verifier is FAILED; only its dependents are blocked."
                >
                    <Row k="Step A (Document Agent)" v="COMPLETED" badge="success" />
                    <Row k="Step B (Data Agent) — output fails verifier" v="FAILED" badge="destructive" />
                    <Row k="Step C (independent of B)" v="COMPLETED" badge="success" />
                    <Row k="Step D (depends on B)" v="BLOCKED" badge="info" />
                    <Row k="Run status" v="PARTIAL" />
                    <p className="text-xs text-muted-foreground">
                        B&apos;s output never reaches shared state or D. The answer is synthesised from A and C and the
                        blocked branch is reported.
                    </p>
                </Scenario>

                <Scenario
                    n={3}
                    title="AI workflow automation, governed the same way"
                    desc="A scheduled or triggered automation re-enters the identical supervisor/executor/approval path."
                >
                    <Flow
                        steps={[
                            { label: "Automation trigger", note: "digest · NL-recurring · DB report · WorkGraph rule" },
                            { label: "Rule validation", note: "previewed definition only" },
                            { label: "Blast-radius check", note: "per-run / per-hour caps" },
                            { label: "Kill-switch check", note: "re-checked per item" },
                            { label: "Execution / Block", tone: "block" },
                        ]}
                    />
                </Scenario>

                <Scenario n={4} title="Human approval and autonomy" desc="A side-effecting proposal cannot execute without a matching approval or an eligible autonomy grant.">
                    <Flow
                        steps={[
                            { label: "AI proposal (agents are read-only)" },
                            { label: "Approval required", note: "server-side gate" },
                            { label: "Human approval", tone: "ok" },
                            { label: "WorkGraph mutation", note: "approval consumed once" },
                            { label: "Audit event" },
                        ]}
                    />
                </Scenario>

                <Scenario
                    n={5}
                    title="Case study: meeting transcript → tracked tasks"
                    desc="Traced end to end in the paper (Section V); illustrated here, not re-executed."
                >
                    <Flow
                        steps={[
                            { label: "Transcript submitted", note: "meeting.extract (read-only)" },
                            { label: "Action items extracted and persisted" },
                            { label: "Human reviews list" },
                            { label: "Bulk create-task request", note: "workgraph.create_task, idempotent" },
                            { label: "Tasks created — re-run skips already-linked items" },
                        ]}
                    />
                </Scenario>

                <Scenario
                    n={6}
                    title="Local/cloud model placement (supporting mechanism)"
                    desc={'Input: "Summarize a confidential internal document" — privacy is a feasibility filter, applied before cost.'}
                >
                    <Row k="Privacy tier" v="RESTRICTED" badge="destructive" />
                    <Row k="Local placement" v="Eligible" badge="success" />
                    <Row k="Cloud placement" v="Not feasible" badge="destructive" />
                    <Row k="Routing decision" v="LOCAL (only feasible option)" badge="info" />
                    <p className="text-xs text-muted-foreground">
                        For a PUBLIC-tier request both placements would be feasible and cost is minimised among
                        them. Cloud inference is disabled by default in this deployment.
                    </p>
                </Scenario>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <ScrollText className="size-4" aria-hidden /> Example audit event
                        </CardTitle>
                        <CardDescription>Synthetic record; field names illustrative.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <pre className="overflow-x-auto rounded-lg bg-muted/50 p-3 text-xs">
{`{
  "action": "work.create_item",
  "owner": "user_demo",
  "approval": "approved (single use)",
  "outcome": "success",
  "synthetic": true
}`}
                        </pre>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <ShieldCheck className="size-4" aria-hidden /> Governance state
                        </CardTitle>
                        <CardDescription>Autonomy defaults, as configured in code.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Row k="Default autonomy" v="L1 · suggest" badge="info" />
                        <Row k="L3" v="per (project, action) grant only" />
                        <Row k="Destructive / external send" v="never L3-eligible" badge="destructive" />
                        <Row k="Kill switch" v="Off (demo)" badge="success" />
                    </CardContent>
                </Card>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Demonstration metrics panel</CardTitle>
                    <CardDescription>{DEMO_VALUE}</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-3">
                    {[
                        ["Steps blocked by a failed step (S2)", "1 of 4"],
                        ["Automation checks passed (S3)", "3 of 4"],
                        ["Approval gates passed (S4)", "1 of 1"],
                    ].map(([k, v]) => (
                        <div key={k} className="rounded-lg border border-border p-3">
                            <p className="text-xs text-muted-foreground">{k}</p>
                            <p className="flex items-center gap-1 text-xl font-semibold">
                                <CheckCircle2 className="size-4 text-success" aria-hidden /> {v}
                            </p>
                            <p className="text-[11px] text-muted-foreground">Synthetic Demonstration Data</p>
                        </div>
                    ))}
                </CardContent>
            </Card>

            <p className="text-xs text-muted-foreground">
                Human-effort and time-saved claims are never shown here as numbers: the paper (Section VI) labels
                every such claim RESULT NOT YET MEASURED rather than illustrating it as if it were data.
            </p>
        </div>
    );
}
