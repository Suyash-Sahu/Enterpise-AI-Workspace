import {
    ArrowRight,
    Laptop,
    Cloud,
} from "lucide-react";

export default function RoutingCard() {
    return (
        <div className="rounded-xl border bg-background p-4">

            <h4 className="mb-4 font-medium">

                Hybrid Execution

            </h4>

            <div className="flex items-center justify-between">

                <Laptop
                    className="text-success"
                    size={24}
                />

                <ArrowRight size={18} />

                <Cloud
                    className="text-info"
                    size={24}
                />

            </div>

            <p className="mt-4 text-xs text-muted-foreground">

                Planner routed locally.
                LLM executed securely in cloud.

            </p>

        </div>
    );
}