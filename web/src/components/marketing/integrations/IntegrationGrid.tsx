import { IntegrationItem } from "./integrationsData";
import IntegrationCard from "./IntegrationCard";

interface Props {
    integrations: IntegrationItem[];
}

export default function IntegrationGrid({ integrations }: Props) {
    return (
        <div className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {integrations.map((item) => (
                <IntegrationCard key={item.id} integration={item} />
            ))}
        </div>
    );
}
