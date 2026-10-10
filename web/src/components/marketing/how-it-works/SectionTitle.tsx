import { Sparkles } from "lucide-react";

export default function SectionTitle() {
    return (
        <div className="mx-auto max-w-3xl text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-1.5 text-xs font-semibold text-primary backdrop-blur-md">
                <Sparkles className="h-3.5 w-3.5" />
                <span>AMOF Engine Architecture</span>
            </div>

            <h2 className="mt-6 text-3xl font-semibold tracking-tight sm:text-4xl md:text-5xl">
                One Conversation.{" "}
                <span className="bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 bg-clip-text text-transparent">
                    Autonomous Multi-Agent Execution.
                </span>
            </h2>

            <p className="mt-4 text-base text-muted-foreground sm:text-lg">
                Enterprise AI Workspace transforms a single prompt into coordinated parallel actions performed by specialized AI agents, backed by on-device local execution and human-in-the-loop verification.
            </p>
        </div>
    );
}