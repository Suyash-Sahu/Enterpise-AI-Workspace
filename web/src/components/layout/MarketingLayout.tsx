import { ReactNode } from "react";

import { Navbar, Footer } from "@/components/navigation";

interface Props {
  children: ReactNode;
}

export default function MarketingLayout({
  children,
}: Props) {
  return (
    <>
      <Navbar />

      <main className="min-h-screen">
        {children}
      </main>

      <Footer />
    </>
  );
}