import type { Metadata } from "next";

import { ArchitectureView } from "@/components/architecture/architecture-view";

export const metadata: Metadata = {
  title: "Architecture",
  description: "The LangGraph pipeline step by step: which agent, which model and which code runs at every stage.",
};

export default function ArchitecturePage() {
  return <ArchitectureView />;
}
