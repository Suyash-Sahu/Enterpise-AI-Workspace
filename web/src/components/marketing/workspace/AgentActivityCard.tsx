const AGENTS = ["Planner", "Retriever", "Knowledge", "Reasoning"];

export default function AgentActivityCard() {
    return (
        <div className="rounded-md border border-border bg-background p-4">
            <h4 className="mb-4 text-sm font-semibold text-foreground">Agent activity</h4>

            <div className="space-y-3">
                {AGENTS.map((agent) => (
                    <div key={agent} className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">{agent}</span>
                        <span className="h-2 w-2 rounded-full bg-success" />
                    </div>
                ))}
            </div>
        </div>
    );
}
