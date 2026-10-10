import {
    CheckCircle2,
    Clock3,
} from "lucide-react";

const LOGS = [
    ["Planner Agent", "Completed"],
    ["Retriever Agent", "Completed"],
    ["Knowledge Agent", "Completed"],
    ["Response Generator", "Running"],
];

export default function ExecutionLog() {
    return (
        <div className="rounded-xl border bg-background p-4">
            <h4 className="mb-4 font-medium">
                Execution Log
            </h4>

            <div className="space-y-3">
                {LOGS.map(([agent, status]) => (
                    <div
                        key={agent}
                        className="flex items-center justify-between"
                    >
                        <span className="text-sm">
                            {agent}
                        </span>

                        {status === "Completed" ? (
                            <CheckCircle2
                                size={16}
                                className="text-success"
                            />
                        ) : (
                            <Clock3
                                size={16}
                                className="animate-pulse text-info"
                            />
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}