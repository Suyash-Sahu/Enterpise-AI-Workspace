import ChatBubble from "./ChatBubble";
import TypingIndicator from "./TypingIndicator";

export default function ChatArea() {
    return (
        <div className="space-y-5">

            <ChatBubble
                role="user"
                message="Summarize our Q3 roadmap, generate Jira tasks, and identify blockers."
            />

            <ChatBubble
                role="assistant"
                message="Analyzing Gmail, Slack, Drive, Jira and internal documentation."
            />

            <TypingIndicator />

        </div>
    );
}