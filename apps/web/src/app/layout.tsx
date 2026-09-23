import "./globals.css";
import React from "react";
import { SnapshotProvider } from "@/lib/snapshot-context";
import CommandShell from "@/components/CommandShell";

export const metadata = {
  title: "PRISM — Predictive Relocation & Infrastructure Safety Matrix",
  description: "Disaster Decision-Support & Relocation Optimization Command Platform (SIH 26191)",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#070b12] text-slate-100 min-h-screen font-sans selection:bg-blue-600 selection:text-white antialiased">
        <SnapshotProvider>
          <CommandShell>{children}</CommandShell>
        </SnapshotProvider>
      </body>
    </html>
  );
}
