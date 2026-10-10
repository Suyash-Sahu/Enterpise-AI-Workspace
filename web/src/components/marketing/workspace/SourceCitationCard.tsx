import {
    FileText,
    MessageSquare,
    FolderOpen,
    CheckCircle2,
} from "lucide-react";

const SOURCES = [
    {
        name: "HR Handbook.pdf",
        type: "PDF",
        icon: FileText,
        confidence: "98%",
    },
    {
        name: "#engineering",
        type: "Slack",
        icon: MessageSquare,
        confidence: "95%",
    },
    {
        name: "Sprint 28 Planning",
        type: "Jira",
        icon: CheckCircle2,
        confidence: "97%",
    },
    {
        name: "Company Policies",
        type: "Drive",
        icon: FolderOpen,
        confidence: "94%",
    },
];

export default function SourceCitationCard() {
    return (
        <div className="rounded-xl border bg-background p-4">
            <div className="mb-4 flex items-center justify-between">
                <h4 className="font-semibold">Source Citations</h4>

                <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700 dark:bg-success/20 dark:text-emerald-300">
                    Verified
                </span>
            </div>

            <div className="space-y-3">
                {SOURCES.map((source) => {
                    const Icon = source.icon;

                    return (
                        <div
                            key={source.name}
                            className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-muted/40"
                        >
                            <div className="flex items-center gap-3">
                                <div className="rounded-md bg-indigo-100 p-2 dark:bg-primary/20">
                                    <Icon
                                        size={16}
                                        className="text-primary dark:text-indigo-300"
                                    />
                                </div>

                                <div>
                                    <p className="text-sm font-medium">
                                        {source.name}
                                    </p>

                                    <p className="text-xs text-muted-foreground">
                                        {source.type}
                                    </p>
                                </div>
                            </div>

                            <span className="text-xs font-semibold text-success dark:text-success">
                                {source.confidence}
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}