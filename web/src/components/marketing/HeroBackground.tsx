/**
 * One quiet, static background treatment — a single soft glow plus a faint
 * grid. No motion (so nothing to gate on prefers-reduced-motion).
 */
export default function HeroBackground() {
    return (
        <div
            aria-hidden
            className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
        >
            <div className="absolute left-1/2 top-0 h-128 w-200 max-w-full -translate-x-1/2 rounded-full bg-primary/5 blur-3xl" />
            <div
                className="absolute inset-0 opacity-[0.035]"
                style={{
                    backgroundImage:
                        "linear-gradient(to right, currentColor 1px, transparent 1px), linear-gradient(to bottom, currentColor 1px, transparent 1px)",
                    backgroundSize: "48px 48px",
                }}
            />
        </div>
    );
}
