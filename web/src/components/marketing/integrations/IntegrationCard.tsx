import { IntegrationItem } from "./integrationsData";
import { Check } from "lucide-react";

interface Props {
    integration: IntegrationItem;
}

export default function IntegrationCard({ integration }: Props) {
    const Icon = integration.icon;

    return (
        <div className="group relative flex flex-col justify-between rounded-2xl border border-border bg-background/80 p-5 backdrop-blur-sm transition-all duration-300 hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5">
            <div>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-muted/30 border border-border ${integration.color}`}>
                            <Icon className="h-5 w-5" />
                        </div>
                        <div>
                            <h3 className="text-base font-bold text-foreground group-hover:text-primary transition-colors">
                                {integration.name}
                            </h3>
                            {integration.isLive && (
                                <span className="inline-flex items-center gap-1 text-xs font-semibold text-success">
                                    <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
                                    Active v1
                                </span>
                            )}
                        </div>
                    </div>
                    <span className="rounded-full border border-border bg-muted/20 px-2.5 py-0.5 text-xs font-mono font-medium text-muted-foreground">
                        {integration.badge}
                    </span>
                </div>

                <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                    {integration.description}
                </p>
            </div>

            <div className="mt-4 border-t border-border pt-3">
                <ul className="space-y-1">
                    {integration.capabilities.map((cap, idx) => (
                        <li key={idx} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <Check className="h-3 w-3 text-primary shrink-0" />
                            <span>{cap}</span>
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
}
