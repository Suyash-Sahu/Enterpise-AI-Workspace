import { Cloud, Laptop } from "lucide-react";

interface Props {
    mode: "local" | "cloud";
}

export default function ExecutionModeBadge({
    mode,
}: Props) {
    if (mode === "local") {
        return (
            <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-success dark:bg-success/20 dark:text-success">
                <Laptop size={14} />
                Local
            </div>
        );
    }

    return (
        <div className="inline-flex items-center gap-2 rounded-full bg-sky-100 px-3 py-1 text-xs font-medium text-info dark:bg-info/20 dark:text-info">
            <Cloud size={14} />
            Cloud
        </div>
    );
}