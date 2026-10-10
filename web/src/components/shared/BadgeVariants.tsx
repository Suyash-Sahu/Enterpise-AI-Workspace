import { cn } from "@/lib/utils";

interface PriorityProps {
    priority: "Critical" | "High" | "Medium" | "Low" | string;
}

export function PriorityBadge({ priority }: PriorityProps) {
    const map: Record<string, string> = {
        Critical: "border-destructive/30 bg-destructive/10 text-destructive",
        High: "border-warning/30 bg-warning/10 text-warning",
        Medium: "border-info/30 bg-info/10 text-info",
        Low: "border-success/30 bg-success/10 text-success",
    };

    const cls = map[priority] || "border-border bg-muted text-muted-foreground";

    return (
        <span className={cn("inline-flex items-center rounded-md border px-2 py-0.5 font-mono text-xs font-bold uppercase", cls)}>
            {priority}
        </span>
    );
}

interface StatusProps {
    status: "Connected" | "Syncing" | "Error" | "Disconnected" | string;
}

export function StatusBadge({ status }: StatusProps) {
    const map: Record<string, string> = {
        Connected: "bg-success/10 text-success border-success/30",
        Syncing: "bg-info/10 text-info border-info/30 animate-pulse",
        Error: "bg-destructive/10 text-destructive border-destructive/30",
        Disconnected: "bg-muted/80 text-muted-foreground border-border",
    };

    const cls = map[status] || "bg-muted text-muted-foreground border-border";

    return (
        <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-xs font-bold", cls)}>
            <span className="h-1.5 w-1.5 rounded-full bg-current" />
            <span>{status}</span>
        </span>
    );
}

interface ExecutionModeProps {
    mode: "Local" | "Cloud" | "Hybrid" | string;
}

export function ExecutionModeBadge({ mode }: ExecutionModeProps) {
    const map: Record<string, string> = {
        Local: "bg-success/15 text-success border-success/30",
        Cloud: "bg-info/15 text-info border-info/30",
        Hybrid: "bg-primary/15 text-primary border-primary/30",
    };

    const cls = map[mode] || "bg-muted text-muted-foreground border-border";

    return (
        <span className={cn("inline-flex items-center rounded-lg border px-2 py-0.5 font-mono text-xs font-semibold uppercase tracking-wider", cls)}>
            {mode} Mode
        </span>
    );
}
