import {
    Server,
    ShieldCheck,
} from "lucide-react";

export default function SystemStatusCard() {
    return (
        <div className="rounded-xl border bg-background p-4">

            <h4 className="mb-4 font-medium">

                Workspace Status

            </h4>

            <div className="space-y-3 text-sm">

                <div className="flex justify-between">

                    <span>Agents</span>

                    <span className="text-success">
                        4 Online
                    </span>

                </div>

                <div className="flex justify-between">

                    <span>Execution</span>

                    <span className="text-info">
                        Local + Cloud
                    </span>

                </div>

                <div className="flex justify-between">

                    <span>Security</span>

                    <span className="text-success">
                        Encrypted
                    </span>

                </div>

            </div>

            <div className="mt-5 flex items-center gap-3 text-xs text-muted-foreground">

                <Server size={14} />

                <ShieldCheck size={14} />

                Enterprise Mode Enabled

            </div>

        </div>
    );
}