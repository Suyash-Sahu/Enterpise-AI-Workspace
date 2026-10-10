import ConfidenceCard from "./ConfidenceCard";
import RoutingCard from "./RoutingCard";
import AgentActivityCard from "./AgentActivityCard";
import TokenUsageCard from "./TokenUsageCard";
import ExecutionLog from "./ExecutionLog";
import ToolExecutionCard from "./ToolExecutionCard";
import SourceCitationCard from "./SourceCitationCard";
import SystemStatusCard from "./SystemStatusCard";

export default function RightSidebar() {
    return (
        <div className="space-y-5">
            <ConfidenceCard />
            <RoutingCard />
            <AgentActivityCard />
            <ExecutionLog />
            <TokenUsageCard />
            <ToolExecutionCard />
            <SourceCitationCard />
            <SystemStatusCard />
        </div>
    );
}