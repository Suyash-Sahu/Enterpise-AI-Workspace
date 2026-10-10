import { ShieldCheck, UserCheck, Lock, ArrowRight } from "lucide-react";

export default function SecurityDiagram() {
    return (
        <div className="mt-16 rounded-2xl border border-primary/20 bg-surface/60 p-6 backdrop-blur-md shadow-md text-center">
            <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-mono font-semibold text-primary">
                Human-in-the-Loop Governance
            </span>
            <h3 className="mt-2 text-base font-bold text-foreground">Zero Unauthorized External Side-Effects</h3>

            <div className="mt-6 flex flex-col md:flex-row items-center justify-around gap-4 font-mono text-xs">
                <div className="rounded-xl border border-border bg-background/80 p-4 w-full md:w-1/3">
                    <div className="text-muted-foreground">01. Agent Action Drafted</div>
                    <div className="mt-1 font-bold text-foreground">Writing Agent drafts email reply</div>
                </div>

                <ArrowRight className="h-5 w-5 text-muted-foreground rotate-90 md:rotate-0" />

                <div className="rounded-xl border border-warning/40 bg-warning/10 p-4 w-full md:w-1/3">
                    <div className="text-warning font-bold">02. Mandatory Approval Gate</div>
                    <div className="mt-1 text-foreground font-semibold">User receives modal review prompt</div>
                </div>

                <ArrowRight className="h-5 w-5 text-muted-foreground rotate-90 md:rotate-0" />

                <div className="rounded-xl border border-success/40 bg-success/10 p-4 w-full md:w-1/3">
                    <div className="text-success font-bold">03. Verified Dispatch</div>
                    <div className="mt-1 text-foreground font-semibold">Gmail API `gmail.send` triggered</div>
                </div>
            </div>
        </div>
    );
}
