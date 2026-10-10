import {
    Cpu,
    Database,
} from "lucide-react";

export default function TokenUsageCard() {
    return (
        <div className="rounded-xl border bg-background p-4">

            <div className="flex items-center gap-3">

                <Cpu className="text-primary" />

                <div>

                    <h4 className="font-medium">

                        Token Usage

                    </h4>

                    <p className="text-xs text-muted-foreground">

                        Current Session

                    </p>

                </div>

            </div>

            <div className="mt-5 grid grid-cols-2 gap-4">

                <div>

                    <p className="text-2xl font-bold">

                        5.8K

                    </p>

                    <p className="text-xs text-muted-foreground">

                        Input

                    </p>

                </div>

                <div>

                    <p className="text-2xl font-bold">

                        1.3K

                    </p>

                    <p className="text-xs text-muted-foreground">

                        Output

                    </p>

                </div>

            </div>

            <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">

                <Database size={14} />

                Cached Context Enabled

            </div>

        </div>
    );
}