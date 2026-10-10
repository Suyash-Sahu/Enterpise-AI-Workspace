"use client";

import React from "react";
import { StepTrace, RoutingDecisionTrace, ExecutionTrace } from "@/services/traces.service";

interface RightSideInspectorProps {
  step?: StepTrace | null;
  routing?: RoutingDecisionTrace | null;
  execution?: ExecutionTrace | null;
  isOpen: boolean;
  onClose: () => void;
}

export const RightSideInspector: React.FC<RightSideInspectorProps> = ({
  step,
  routing,
  execution,
  isOpen,
  onClose,
}) => {
  if (!isOpen || !step) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-zinc-950/95 border-l border-zinc-800 shadow-2xl z-50 p-6 flex flex-col justify-between backdrop-blur-md">
      <div className="space-y-6 overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
          <div>
            <span className="text-xs font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded">
              {step.step_id}
            </span>
            <h3 className="text-lg font-semibold text-zinc-100 mt-1">{step.capability}</h3>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-200 p-1 rounded-md hover:bg-zinc-800 transition"
          >
            ✕
          </button>
        </div>

        {/* Step Status & Details */}
        <div className="space-y-3">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Step Telemetry</h4>
          <div className="bg-zinc-900/60 p-3 rounded-lg border border-zinc-800 text-sm space-y-2">
            <div className="flex justify-between">
              <span className="text-zinc-400">Status</span>
              <span className="font-mono text-emerald-400">{step.status}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-400">Execution Time</span>
              <span className="font-mono text-zinc-200">{(step.execution_time * 1000).toFixed(1)} ms</span>
            </div>
            {step.execution_id && (
              <div className="flex justify-between">
                <span className="text-zinc-400">Execution ID</span>
                <span className="font-mono text-zinc-300 text-xs truncate max-w-[160px]">
                  {step.execution_id}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Privacy & Routing Decision */}
        {routing && (
          <div className="space-y-3">
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Privacy & Routing Decision
            </h4>
            <div className="bg-zinc-900/60 p-3 rounded-lg border border-zinc-800 text-sm space-y-2">
              <div className="flex justify-between">
                <span className="text-zinc-400">Placement</span>
                <span className="font-mono text-indigo-300 bg-indigo-500/10 px-2 py-0.5 rounded text-xs">
                  {routing.placement}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Target Model</span>
                <span className="font-mono text-zinc-200 text-xs">{routing.model}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Privacy Label</span>
                <span className="font-mono text-amber-300 text-xs">{routing.privacy_label}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Routing Confidence</span>
                <span className="font-mono text-zinc-200">{(routing.routing_confidence * 100).toFixed(0)}%</span>
              </div>
              {routing.reason && (
                <div className="mt-2 pt-2 border-t border-zinc-800 text-xs text-zinc-400">
                  <span className="font-semibold text-zinc-300">Decision Rationale:</span>
                  <p className="mt-1 text-zinc-400">{routing.reason}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Execution Metadata */}
        {execution && (
          <div className="space-y-3">
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Execution Runtime
            </h4>
            <div className="bg-zinc-900/60 p-3 rounded-lg border border-zinc-800 text-sm space-y-2">
              <div className="flex justify-between">
                <span className="text-zinc-400">Provider</span>
                <span className="font-mono text-zinc-200">{execution.provider || "N/A"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Retries</span>
                <span className="font-mono text-zinc-200">{execution.retry_count}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="pt-4 border-t border-zinc-800 text-center">
        <button
          onClick={onClose}
          className="w-full py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm rounded-lg transition font-medium"
        >
          Close Inspector
        </button>
      </div>
    </div>
  );
};
