import MarketingLayout from "@/components/layout/MarketingLayout";
import Hero from "@/components/marketing/Hero";
import HeroTrust from "@/components/marketing/HeroTrust";
import HowItWorks from "@/components/marketing/how-it-works/HowItWorks";
import Features from "@/components/marketing/features";
import Integrations from "@/components/marketing/integrations";
import Security from "@/components/marketing/security";
import Pricing from "@/components/marketing/pricing";
import FAQ from "@/components/marketing/faq";
import CTA from "@/components/marketing/cta";

export default function Home() {
  return (
    <MarketingLayout>
      <Hero />
      <HeroTrust />
      <HowItWorks />
      <Features surface />
      <Integrations />
      <Security surface />
      <Pricing />
      <FAQ surface />
      <CTA />
    </MarketingLayout>
  );
}
