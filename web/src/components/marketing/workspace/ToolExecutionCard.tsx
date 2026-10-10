import {
    Mail,
    FolderOpen,
    MessageSquare,
    ClipboardCheck,
    LucideIcon,
} from "lucide-react";


const TOOLS: {
    name: string;
    icon: LucideIcon;
}[] = [
        { name: "Gmail", icon: Mail },
        { name: "Google Drive", icon: FolderOpen },
        { name: "Slack", icon: MessageSquare },
        { name: "Jira", icon: ClipboardCheck },
    ];
export default function ToolExecutionCard() {
    return (
        <div className="rounded-xl border bg-background p-4">

            <h4 className="mb-4 font-medium">

                Connected Tools

            </h4>

            <div className="space-y-3">

                {TOOLS.map(({ name, icon: Icon }) => (
                    <div
                        key={name}
                        className="flex items-center justify-between"
                    >
                        <div className="flex items-center gap-3">
                            <Icon
                                size={18}
                                className="text-primary"
                            />

                            <span className="text-sm">
                                {name}
                            </span>
                        </div>

                        <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs text-emerald-700 dark:bg-success/20 dark:text-emerald-300">
                            Active
                        </span>
                    </div>
                ))}

            </div>

        </div>
    );
}