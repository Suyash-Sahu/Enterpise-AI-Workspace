"use client";

import { motion } from "framer-motion";

interface ChatBubbleProps {
    role: "user" | "assistant";
    message: string;
}

export default function ChatBubble({
    role,
    message,
}: ChatBubbleProps) {
    const isUser = role === "user";

    return (
        <motion.div
            initial={{
                opacity: 0,
                y: 15,
            }}
            animate={{
                opacity: 1,
                y: 0,
            }}
            transition={{
                duration: 0.4,
            }}
            className={`flex ${isUser ? "justify-end" : "justify-start"
                }`}
        >
            <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${isUser
                        ? "bg-primary text-white"
                        : "border bg-background"
                    }`}
            >
                {message}
            </div>
        </motion.div>
    );
}