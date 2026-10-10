import { ShieldCheck } from "lucide-react";

export default function ConfidenceCard() {
    return (
        <div className="rounded-xl border bg-background p-4">

            <div className="flex items-center gap-3">

                <ShieldCheck className="text-success" />

                <div>

                    <h4 className="font-medium">
                        Confidence
                    </h4>

                    <p className="text-xs text-muted-foreground">
                        Retrieval Confidence
                    </p>

                </div>

            </div>

            <div className="mt-5">

                <div className="h-2 overflow-hidden rounded-full bg-muted">

                    <div className="h-full w-[96%] rounded-full bg-success" />

                </div>

                <p className="mt-2 text-sm font-semibold">
                    96%
                </p>

            </div>

        </div>
    );
}