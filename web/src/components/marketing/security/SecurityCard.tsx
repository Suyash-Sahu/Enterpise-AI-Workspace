import { ShieldCheck, Lock, Eye, Key, FileCode, CheckCircle2 } from "lucide-react";

interface Props {
    title: string;
    description: string;
    icon: typeof ShieldCheck;
    badge: string;
    points: string[];
}

export default function SecurityCard({ title, description, icon: Icon, badge, points }: Props) {
    return (
        <div className="group relative flex flex-col justify-between rounded-2xl border border-border bg-background/80 p-6 backdrop-blur-sm transition-all duration-300 hover:border-primary/40 hover:shadow-md hover:shadow-primary/5">
            <div>
                <div className="flex items-center justify-between">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20 transition-transform group-hover:scale-110">
                        <Icon className="h-6 w-6" />
                    </div>
                    <span className="rounded-full border border-primary/20 bg-primary/5 px-2.5 py-1 text-xs font-mono font-medium text-primary">
                        {badge}
                    </span>
                </div>

                <h3 className="mt-5 text-xl font-bold tracking-tight text-foreground group-hover:text-primary transition-colors">
                    {title}
                </h3>

                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {description}
                </p>
            </div>

            <div className="mt-6 border-t border-border pt-4">
                <ul className="space-y-2">
                    {points.map((pt, idx) => (
                        <li key={idx} className="flex items-center gap-2 text-xs font-medium text-foreground/80">
                            <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0" />
                            <span>{pt}</span>
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
}
