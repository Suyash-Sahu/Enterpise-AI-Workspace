import { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";

interface Breadcrumb {
    label: string;
    href?: string;
}

interface Props {
    title: string;
    description?: string;
    breadcrumbs?: Breadcrumb[];
    actions?: ReactNode;
}

/**
 * The one page-title component. Theme-aware: title is `text-foreground`,
 * description is `text-muted-foreground`. (It previously hard-coded
 * `text-white` / `text-slate-200`, which was invisible on the light
 * workspace background.)
 */
export default function PageHeader({ title, description, breadcrumbs, actions }: Props) {
    return (
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
                {breadcrumbs && breadcrumbs.length > 0 && (
                    <nav
                        aria-label="Breadcrumb"
                        className="mb-2 flex items-center gap-1.5 text-xs text-muted-foreground"
                    >
                        {breadcrumbs.map((crumb, idx) => (
                            <div key={idx} className="flex items-center gap-1.5">
                                {idx > 0 && (
                                    <ChevronRight className="h-3 w-3 shrink-0" aria-hidden />
                                )}
                                {crumb.href ? (
                                    <Link
                                        href={crumb.href}
                                        className="rounded-sm transition-colors hover:text-foreground"
                                    >
                                        {crumb.label}
                                    </Link>
                                ) : (
                                    <span className="font-medium text-foreground" aria-current="page">
                                        {crumb.label}
                                    </span>
                                )}
                            </div>
                        ))}
                    </nav>
                )}
                <h1 className="truncate text-2xl font-semibold tracking-tight text-foreground">
                    {title}
                </h1>
                {description && (
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                        {description}
                    </p>
                )}
            </div>
            {actions && (
                <div className="flex shrink-0 items-center gap-2">{actions}</div>
            )}
        </div>
    );
}
