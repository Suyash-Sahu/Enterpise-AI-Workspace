"use client";

import { useMemo } from "react";
import ReactFlow, { Background, Controls, Node, Edge } from "reactflow";
import "reactflow/dist/style.css";

const initialNodes: Node[] = [
    { id: "1", position: { x: 250, y: 0 }, data: { label: "AMOF Core Orchestrator" }, style: { background: "#4F46E5", color: "#fff", border: "none", borderRadius: "12px", fontWeight: "bold", padding: "10px 16px" } },
    { id: "2", position: { x: 100, y: 120 }, data: { label: "Document Agent (RAG)" }, style: { background: "#0EA5E9", color: "#fff", border: "none", borderRadius: "12px", fontWeight: "bold", padding: "10px 16px" } },
    { id: "3", position: { x: 400, y: 120 }, data: { label: "Database Agent (SQL)" }, style: { background: "#10B981", color: "#fff", border: "none", borderRadius: "12px", fontWeight: "bold", padding: "10px 16px" } },
    { id: "4", position: { x: 100, y: 240 }, data: { label: "Qdrant Vector DB" }, style: { background: "#8B5CF6", color: "#fff", border: "none", borderRadius: "12px", fontWeight: "bold", padding: "10px 16px" } },
    { id: "5", position: { x: 400, y: 240 }, data: { label: "PostgreSQL Data Store" }, style: { background: "#F59E0B", color: "#fff", border: "none", borderRadius: "12px", fontWeight: "bold", padding: "10px 16px" } },
];

const initialEdges: Edge[] = [
    { id: "e1-2", source: "1", target: "2", animated: true, style: { stroke: "#6366F1" } },
    { id: "e1-3", source: "1", target: "3", animated: true, style: { stroke: "#6366F1" } },
    { id: "e2-4", source: "2", target: "4", animated: true, style: { stroke: "#38BDF8" } },
    { id: "e3-5", source: "3", target: "5", animated: true, style: { stroke: "#34D399" } },
];

export default function KnowledgeGraph() {
    return (
        <div className="h-80 w-full rounded-2xl border border-border bg-surface/50 overflow-hidden">
            <ReactFlow nodes={initialNodes} edges={initialEdges} fitView>
                <Background color="#4F46E5" gap={16} size={1} />
                <Controls />
            </ReactFlow>
        </div>
    );
}
