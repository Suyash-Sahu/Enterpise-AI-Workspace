import { StepItem } from "./steps";
import { Check } from "lucide-react";

interface Props {
    step: StepItem;
}

export default function StepCard({ step }: Props) {
    const Icon = step.icon;

    return (
        <div className="group relative flex flex-col justify-between rounded-2xl border border-border bg-background/80 p-6 shadow-sm transition-all duration-300 hover:border-primary/40 hover:shadow-md hover:shadow-primary/5">
            <div>
                <div className="flex items-center justify-between">
                    <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${step.lightBg} ${step.color} transition-transform duration-300 group-hover:scale-110`}>
                        <Icon className="h-6 w-6" />
                    </div>
                    <span className="rounded-full border border-border bg-muted/30 px-3 py-1 text-xs font-mono font-semibold text-muted-foreground">
                        {step.badge}
                    </span>
                </div>

                <h3 className="mt-5 text-xl font-bold tracking-tight text-foreground group-hover:text-primary transition-colors">
                    {step.title}
                </h3>

                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {step.description}
                </p>
            </div>

            <div className="mt-6 border-t border-border pt-4">
                <ul className="space-y-2">
                    {step.details.map((detail, idx) => (
                        <li key={idx} className="flex items-center gap-2 text-xs font-medium text-foreground/80">
                            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-primary/10 text-primary">
                                <Check className="h-2.5 w-2.5" />
                            </span>
                            <span>{detail}</span>
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
}