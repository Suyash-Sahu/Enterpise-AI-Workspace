import StepCard from "./StepCard";
import { STEPS } from "./steps";

export default function ProcessFlow() {
    return (
        <div className="mt-16 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {STEPS.map((step) => (
                <StepCard key={step.id} step={step} />
            ))}
        </div>
    );
}