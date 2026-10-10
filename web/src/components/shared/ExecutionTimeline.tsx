"use client";

import React from "react";
import { StepTrace, RoutingDecisionTrace, ReplanningEventTrace } from "@/services/traces.service";

interface ExecutionTimelineProps {
  steps: StepTrace[];
  routingDecisions?: RoutingDecisionTrace[];
  replanningEvents?: ReplanningEventTrace[];
  onSelectStep?: (step: StepTrace, routing?: RoutingDecisionTrace) => void;
  selectedStepId?: string;
}

export const ExecutionTimeline: React.FC<ExecutionTimelineProps> = ({
  steps,
  routingDecisions = [],
  replanningEvents = [],
  onSelectStep,
  selectedStepId,
}) => {
  const getRoutingForStep = (stepId: string) => {
    return routingDecisions.find((r) => r.workflow_step_id === stepId);
  };

  const getReplanningForStep = (stepId: string) => {
    return replanningEvents.find((rp) => rp.original_step_id === stepId || rp.new_step_id === stepId);
  };

  if (!steps || steps.length === 0) {
    return (
      <div className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-800 text-zinc-400 text-sm text-center">
        No workflow steps recorded for this execution.
      </div>
    );
  }

  return (
    <div className="space-y-3 my-4">
      <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
        Workflow DAG Execution Flow
      </div>

      <div className="relative pl-6 border-l-2 border-indigo-500/30 space-y-4">
        {steps.map((step, idx) => {
          const routing = getRoutingForStep(step.step_id);
          const replan = getReplanningForStep(step.step_id);
          const isSelected = selectedStepId === step.step_id;

          const statusColor =
            step.status === "COMPLETED"
              ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
              : step.status === "FAILED"
              ? "bg-rose-500/20 text-rose-400 border-rose-500/30"
              : "bg-amber-500/20 text-amber-400 border-amber-500/30";

          return (
            <div
              key={step.step_id || idx}
              onClick={() => onSelectStep && onSelectStep(step, routing)}
              className={`relative cursor-pointer p-4 rounded-xl border transition-all duration-200 ${
                isSelected
                  ? "bg-zinc-800/90 border-indigo-500 shadow-lg shadow-indigo-500/10"
                  : "bg-zinc-900/60 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900"
              }`}
            >
              {/* Node Bullet */}
              <div
                className={`absolute -left-[31px] top-4 w-3.5 h-3.5 rounded-full border-2 bg-zinc-950 ${
                  step.status === "COMPLETED" ? "border-emerald-400" : "border-indigo-400"
                }`}
              />

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded">
                    {step.step_id}
                  </span>
                  <span className="font-medium text-zinc-200 text-sm">{step.capability}</span>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusColor}`}>
                    {step.status}
                  </span>
                  {step.execution_time > 0 && (
                    <span className="text-xs text-zinc-400 font-mono">
                      {(step.execution_time * 1000).toFixed(0)}ms
                    </span>
                  )}
                </div>
              </div>

              {/* Dependencies badge */}
              {step.depends_on && step.depends_on.length > 0 && (
                <div className="mt-2 text-xs text-zinc-400 flex items-center gap-1">
                  <span>Prerequisites:</span>
                  {step.depends_on.map((dep) => (
                    <span key={dep} className="font-mono bg-zinc-800 text-zinc-300 px-1.5 py-0.5 rounded text-[11px]">
                      {dep}
                    </span>
                  ))}
                </div>
              )}

              {/* Routing decision preview */}
              {routing && (
                <div className="mt-2.5 pt-2 border-t border-zinc-800/60 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 text-zinc-300">
                    <span className="font-mono bg-zinc-800 text-indigo-300 px-1.5 py-0.5 rounded text-[11px]">
                      {routing.placement}
                    </span>
                    <span className="text-zinc-400 truncate max-w-[200px]">{routing.model}</span>
                  </div>
                  <span className="text-zinc-400 bg-zinc-800/80 px-2 py-0.5 rounded font-mono text-[11px]">
                    Privacy: {routing.privacy_label}
                  </span>
                </div>
              )}

              {/* Replanning alert badge */}
              {replan && (
                <div className="mt-2 bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs px-2.5 py-1 rounded-md flex items-center gap-2">
                  <span className="font-semibold">CDRP Replan:</span>
                  <span>{replan.reason}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
