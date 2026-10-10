import { FeatureItem } from "./featuresData";

interface Props {
    icon: FeatureItem["icon"];
    className?: string;
}

export default function FeatureIcon({ icon: Icon, className = "h-5 w-5" }: Props) {
    return (
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20">
            <Icon className={className} />
        </div>
    );
}
