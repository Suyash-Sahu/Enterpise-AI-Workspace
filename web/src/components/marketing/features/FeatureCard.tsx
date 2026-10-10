import { FeatureItem } from "./featuresData";
import FeatureIcon from "./FeatureIcon";
import { Check } from "lucide-react";

interface Props {
    feature: FeatureItem;
}

export default function FeatureCard({ feature }: Props) {
    return (
        <div className="group relative flex flex-col justify-between rounded-2xl border border-border bg-background/80 p-6 shadow-sm backdrop-blur-sm transition-all duration-300 hover:border-primary/40 hover:shadow-md hover:shadow-primary/5">
            <div>
                <div className="flex items-center justify-between">
                    <FeatureIcon icon={feature.icon} />
                    <span className="rounded-full border border-primary/20 bg-primary/5 px-2.5 py-1 text-xs font-mono font-medium text-primary">
                        {feature.badge}
                    </span>
                </div>

                <h3 className="mt-4 text-lg font-bold tracking-tight text-foreground group-hover:text-primary transition-colors">
                    {feature.title}
                </h3>
                
                <p className="mt-1 text-xs font-semibold text-primary/80">
                    {feature.subtitle}
                </p>

                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    {feature.description}
                </p>
            </div>

            <div className="mt-6 border-t border-border pt-4">
                <ul className="space-y-1.5">
                    {feature.highlights.map((item, idx) => (
                        <li key={idx} className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                            <Check className="h-3.5 w-3.5 text-primary shrink-0" />
                            <span>{item}</span>
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
}
