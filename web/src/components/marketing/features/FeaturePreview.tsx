import { Terminal, ShieldAlert, Cpu } from "lucide-react";

export default function FeaturePreview() {
    return (
        <div className="mt-16 rounded-2xl border border-border bg-surface/60 p-6 backdrop-blur-md shadow-md">
            <div className="flex items-center justify-between border-b border-border pb-4">
                <div className="flex items-center gap-2">
                    <Terminal className="h-4 w-4 text-primary" />
                    <span className="text-xs font-mono font-semibold text-foreground">AMOF Runtime Monitor</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="flex items-center gap-1.5 rounded-full bg-success/10 px-2.5 py-0.5 text-xs font-mono font-medium text-success border border-success/20">
                        <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
                        8/8 Agents Active
                    </span>
                    <span className="flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-mono font-medium text-primary border border-primary/20">
                        <Cpu className="h-3 w-3" />
                        Hybrid Routing
                    </span>
                </div>
            </div>

            <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
                <div className="rounded-xl border border-border bg-background/60 p-4">
                    <div className="text-muted-foreground">Local Model Node</div>
                    <div className="mt-1 text-sm font-bold text-success">Ollama Qwen2.5-32B</div>
                    <div className="mt-2 text-xs text-muted-foreground">RAM: 14.2 GB • Latency: 18ms</div>
                </div>
                <div className="rounded-xl border border-border bg-background/60 p-4">
                    <div className="text-muted-foreground">Cloud Reasoning Node</div>
                    <div className="mt-1 text-sm font-bold text-info">Claude 3.5 Sonnet</div>
                    <div className="mt-2 text-xs text-muted-foreground">Tokens: 1,420 • Cost: $0.0042</div>
                </div>
                <div className="rounded-xl border border-border bg-background/60 p-4">
                    <div className="text-muted-foreground">Governance Gate</div>
                    <div className="mt-1 text-sm font-bold text-warning">Human Approval Pending</div>
                    <div className="mt-2 text-xs text-muted-foreground">Action: Gmail Send (2 recipients)</div>
                </div>
            </div>
        </div>
    );
}
