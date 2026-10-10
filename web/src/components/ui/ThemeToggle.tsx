"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";

export default function ThemeToggle() {
    const { resolvedTheme, setTheme } = useTheme();

    return (
        <Button
            variant="outline"
            size="icon"
            aria-label="Toggle color theme"
            title="Toggle color theme"
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
        >
            {/* Both icons render; CSS shows the right one for the active theme,
                so there is no server/client mismatch and no mount gate. */}
            <Sun className="hidden dark:block" aria-hidden />
            <Moon className="block dark:hidden" aria-hidden />
        </Button>
    );
}
