import {
    BadgeCheck,
    BrainCircuit,
    Cpu,
    MessageSquare,
} from "lucide-react";

export const STEP_ICONS = {
    message: MessageSquare,
    brain: BrainCircuit,
    cpu: Cpu,
    verified: BadgeCheck,
} as const;