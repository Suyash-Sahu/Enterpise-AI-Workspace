"use client";

import { useState } from "react";
import { ArrowRight, Check } from "lucide-react";

export default function FooterNewsletter() {
    const [email, setEmail] = useState("");
    const [subscribed, setSubscribed] = useState(false);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (email) {
            setSubscribed(true);
        }
    };

    return (
        <div className="rounded-2xl border border-border bg-background/80 p-5 backdrop-blur-sm">
            <h4 className="text-sm font-bold text-foreground">Subscribe to Enterprise AI Updates</h4>
            <p className="mt-1 text-xs text-muted-foreground">
                Get monthly deep dives into AMOF multi-agent research, local LLM updates, and enterprise security releases.
            </p>

            {subscribed ? (
                <div className="mt-4 flex items-center gap-2 text-xs font-semibold text-success">
                    <Check className="h-4 w-4" />
                    <span>Subscribed! Check your inbox for updates.</span>
                </div>
            ) : (
                <form onSubmit={handleSubmit} className="mt-4 flex gap-2">
                    <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="Enter work email..."
                        className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
                    />
                    <button
                        type="submit"
                        className="flex items-center justify-center rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition-transform hover:scale-105 shrink-0"
                    >
                        <span>Join</span>
                        <ArrowRight className="ml-1 h-3.5 w-3.5" />
                    </button>
                </form>
            )}
        </div>
    );
}
