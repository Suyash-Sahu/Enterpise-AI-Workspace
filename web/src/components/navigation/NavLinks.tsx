import Link from "next/link";
import { MARKETING_NAV } from "@/constants/navigation";

export default function NavLinks() {
  return (
    <nav className="hidden items-center gap-8 md:flex">
      {MARKETING_NAV.map((item) => (
        <Link
          key={item.label}
          href={item.href}
          className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}