import { FeatureItem } from "./featuresData";
import FeatureCard from "./FeatureCard";

interface Props {
    features: FeatureItem[];
}

export default function FeatureGrid({ features }: Props) {
    return (
        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
                <FeatureCard key={feature.id} feature={feature} />
            ))}
        </div>
    );
}
