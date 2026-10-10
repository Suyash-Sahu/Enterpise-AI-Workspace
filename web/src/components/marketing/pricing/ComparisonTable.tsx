import { Check, Minus } from "lucide-react";

export default function ComparisonTable() {
    const featuresList = [
        { name: "AMOF Multi-Agent Swarm", starter: true, team: true, enterprise: true, selfHosted: true },
        { name: "Live Gmail & Google Drive OAuth", starter: true, team: true, enterprise: true, selfHosted: true },
        { name: "Local Execution Mode (Ollama/Qwen)", starter: "Basic", team: true, enterprise: true, selfHosted: "Unrestricted" },
        { name: "Text-to-SQL DB Connector", starter: false, team: true, enterprise: true, selfHosted: true },
        { name: "Human Approval Gate System", starter: true, team: true, enterprise: true, selfHosted: true },
        { name: "Enterprise SSO & RBAC", starter: false, team: false, enterprise: true, selfHosted: true },
        { name: "Custom On-Premises Model Hosting", starter: false, team: false, enterprise: "Optional", selfHosted: true },
        { name: "Dedicated Audit Log Export", starter: false, team: "30 Days", enterprise: "Unlimited", selfHosted: "Custom retention" },
    ];

    const renderCell = (val: boolean | string) => {
        if (val === true) return <Check className="h-4 w-4 text-success mx-auto" />;
        if (val === false) return <Minus className="h-4 w-4 text-muted-foreground mx-auto" />;
        return <span className="text-xs font-semibold text-primary">{val}</span>;
    };

    return (
        <div className="mt-16 overflow-x-auto rounded-2xl border border-border bg-background/80 p-6 backdrop-blur-sm">
            <h3 className="text-center text-lg font-bold text-foreground">Detailed Feature Matrix Comparison</h3>

            <table className="mt-6 w-full text-center text-xs font-mono">
                <thead>
                    <tr className="border-b border-border text-muted-foreground">
                        <th className="pb-3 text-left font-semibold">Capabilities</th>
                        <th className="pb-3 font-semibold">Starter</th>
                        <th className="pb-3 font-semibold text-primary">Team</th>
                        <th className="pb-3 font-semibold text-primary">Enterprise</th>
                        <th className="pb-3 font-semibold text-success">Self-Hosted</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                    {featuresList.map((f, idx) => (
                        <tr key={idx}>
                            <td className="py-3 text-left font-medium text-foreground">{f.name}</td>
                            <td className="py-3">{renderCell(f.starter)}</td>
                            <td className="py-3">{renderCell(f.team)}</td>
                            <td className="py-3">{renderCell(f.enterprise)}</td>
                            <td className="py-3">{renderCell(f.selfHosted)}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
