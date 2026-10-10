"use client";

import { motion, useReducedMotion } from "framer-motion";

import HeroActions from "./HeroActions";

export default function HeroContent() {
    const reduce = useReducedMotion();
    const rise = reduce
        ? {}
        : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } };

    return (
        <div>
            <motion.p
                {...rise}
                transition={{ duration: 0.3 }}
                className="inline-flex items-center rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-muted-foreground"
            >
                Enterprise AI Platform
            </motion.p>

            <motion.h1
                {...rise}
                transition={{ duration: 0.3, delay: 0.05 }}
                className="mt-6 max-w-xl text-4xl font-semibold tracking-tight text-balance text-foreground sm:text-5xl lg:text-6xl"
            >
                One workspace for every enterprise task
            </motion.h1>

            <motion.p
                {...rise}
                transition={{ duration: 0.3, delay: 0.1 }}
                className="mt-5 max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg"
            >
                Run email, files, tickets, and knowledge from one conversational
                AI — with a human approval gate on every action.
            </motion.p>

            <motion.div {...rise} transition={{ duration: 0.3, delay: 0.15 }}>
                <HeroActions />
            </motion.div>
        </div>
    );
}
