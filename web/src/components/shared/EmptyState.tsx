import { ReactNode } from "react";
import { Inbox } from "lucide-react";

interface Props {
    icon?: ReactNode;
    title: string;
    description: string;
    action?: ReactNode;
}

export default function EmptyState({ icon, title, description, action }: Props) {
    return (
        <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-border bg-muted/30 p-8 text-center sm:p-12">
            <div className="flex h-12 w-12 items-center justify-center rounded-md border border-primary/20 bg-primary/10 text-primary [&_svg]:h-5 [&_svg]:w-5">
                {icon ?? <Inbox aria-hidden />}
            </div>
            <h3 className="mt-4 text-sm font-semibold text-foreground">{title}</h3>
            <p className="mt-1 max-w-sm text-sm leading-relaxed text-muted-foreground">
                {description}
            </p>
            {action && <div className="mt-6">{action}</div>}
        </div>
    );
}
