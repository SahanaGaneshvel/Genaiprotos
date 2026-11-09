import type { Metadata } from "next";

import { AboutView } from "@/components/about/about-view";

export const metadata: Metadata = {
  title: "About",
  description: "What the Multi-Agent AI Research Assistant does, what each agent is responsible for, and why its reports can be checked.",
};

export default function AboutPage() {
  return <AboutView />;
}
