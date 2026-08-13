import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./constellation.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "xnchSystems — Agent Constellation",
  description:
    "Nexi, the orchestrator, and the specialist subsystems around it. A decision pipeline with a human gate.",
};

export default function ConstellationLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className={`${inter.variable}`}>
      {children}
    </div>
  );
}
