export interface AIModel {
    id: string;
    name: string;
    provider: string;
    badge?: string;
    speed: string;
    reasoning: string;
    description: string;
}

export const AI_MODELS: AIModel[] = [
    {
        id: "openai/gpt-4o",
        name: "GPT-4o Enterprise",
        provider: "OpenRouter / OpenAI",
        badge: "Most Popular",
        speed: "Fast",
        reasoning: "Deep Reasoning",
        description: "Flagship model for complex multi-agent reasoning, strategy, and code execution.",
    },
    {
        id: "deepseek/deepseek-r1:free",
        name: "DeepSeek R1",
        provider: "OpenRouter / DeepSeek",
        badge: "Free Reasoning",
        speed: "Fast",
        reasoning: "Chain of Thought",
        description: "Open-weights reasoning model with chain-of-thought step traces.",
    },
    {
        id: "anthropic/claude-3.5-sonnet",
        name: "Claude 3.5 Sonnet",
        provider: "OpenRouter / Anthropic",
        badge: "Recommended",
        speed: "Ultra-Fast",
        reasoning: "High Precision",
        description: "Exceptional technical writing, document synthesis, and code generation.",
    },
    {
        id: "google/gemini-2.0-flash-001",
        name: "Gemini 2.0 Flash",
        provider: "OpenRouter / Google",
        badge: "2M Context",
        speed: "Instant",
        reasoning: "Multimodal",
        description: "Massive context window ideal for indexing large document vaults.",
    },
    {
        id: "meta-llama/llama-3.3-70b-instruct",
        name: "Llama 3.3 70B",
        provider: "OpenRouter / Meta",
        badge: "Open Weights",
        speed: "Fast",
        reasoning: "High",
        description: "High-performance open weights model running via OpenRouter.",
    },
    {
        id: "ollama/llama3.1:8b",
        name: "Llama 3.1 8B (Local)",
        provider: "Local Ollama",
        badge: "Zero-Cost Local",
        speed: "Instant",
        reasoning: "Standard",
        description: "Executes 100% on local hardware with zero data leaving your machine.",
    },
];
