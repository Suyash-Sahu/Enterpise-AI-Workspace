"use client";

import { useState } from "react";
import { FAQS } from "./faqData";
import { ChevronDown, HelpCircle } from "lucide-react";

export default function FAQAccordion() {
    const [openId, setOpenId] = useState<string | null>("amof-explain");

    const toggle = (id: string) => {
        setOpenId(openId === id ? null : id);
    };

    return (
        <div className="mt-12 mx-auto max-w-3xl space-y-4">
            {FAQS.map((faq) => {
                const isOpen = openId === faq.id;
                return (
                    <div
                        key={faq.id}
                        className={`rounded-2xl border transition-all duration-200 ${
                            isOpen
                                ? "border-primary/40 bg-primary/5 shadow-md"
                                : "border-border bg-background/80 hover:border-border"
                        }`}
                    >
                        <button
                            onClick={() => toggle(faq.id)}
                            className="flex w-full items-center justify-between p-6 text-left"
                        >
                            <span className="text-base font-bold text-foreground flex items-center gap-2">
                                <HelpCircle className="h-4 w-4 text-primary shrink-0" />
                                {faq.question}
                            </span>
                            <ChevronDown
                                className={`h-5 w-5 text-muted-foreground transition-transform duration-200 ${
                                    isOpen ? "rotate-180 text-primary" : ""
                                }`}
                            />
                        </button>

                        {isOpen && (
                            <div className="border-t border-border px-6 pb-6 pt-4 text-sm leading-relaxed text-muted-foreground">
                                {faq.answer}
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
