export default function SecurityStats() {
    return (
        <div className="mt-12 rounded-xl border border-border bg-background/60 p-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center font-mono">
                <div>
                    <div className="text-xl font-bold text-success">0 Passwords</div>
                    <div className="mt-1 text-xs text-muted-foreground">Stored on cloud servers</div>
                </div>
                <div>
                    <div className="text-xl font-bold text-primary">OAuth 2.0</div>
                    <div className="mt-1 text-xs text-muted-foreground">Scoped user tokens</div>
                </div>
                <div>
                    <div className="text-xl font-bold text-primary">100% Audit</div>
                    <div className="mt-1 text-xs text-muted-foreground">Logged actions & decisions</div>
                </div>
                <div>
                    <div className="text-xl font-bold text-warning">RBAC Gated</div>
                    <div className="mt-1 text-xs text-muted-foreground">Enterprise policy enforcement</div>
                </div>
            </div>
        </div>
    );
}
