import "./globals.css";
import React from "react";

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
      <body className="bg-[#080c14] text-slate-100 min-h-screen flex flex-col font-sans selection:bg-blue-600 selection:text-white">
        {/* Top Operational Header */}
        <header className="h-16 border-b border-slate-800 bg-[#0d131f]/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-50">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center font-black tracking-wider text-white shadow-lg shadow-blue-500/20">
                P
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="font-bold text-lg tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-indigo-300 to-cyan-300">
                    PRISM
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-950 text-blue-300 border border-blue-800/60 font-mono font-medium">
                    SIH 26191
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono tracking-tight hidden sm:block">
                  Predictive Relocation & Infrastructure Safety Matrix
                </div>
              </div>
            </div>

            {/* National Scalability Context Breadcrumbs */}
            <div className="hidden lg:flex items-center pl-6 border-l border-slate-800 text-xs text-slate-400 space-x-1 font-mono">
              <span className="text-slate-500">IND</span>
              <span>/</span>
              <span className="text-slate-500">Uttarakhand</span>
              <span>/</span>
              <span className="text-slate-500">Dehradun Dist</span>
              <span>/</span>
              <span className="text-cyan-400 font-semibold px-1.5 py-0.5 rounded bg-cyan-950/60 border border-cyan-800/40">
                Vayu River Basin
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Decision Support Badge */}
            <div className="hidden md:flex items-center space-x-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-xs">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="text-slate-300 font-mono text-[11px]">DECISION SUPPORT MODE</span>
            </div>

            {/* Human in the loop Authority indicator */}
            <div className="flex items-center space-x-2 text-right">
              <div className="text-xs">
                <div className="font-semibold text-slate-200">Col. Rajesh Verma</div>
                <div className="text-[10px] text-indigo-400 font-mono">EMERGENCY AUTHORITY</div>
              </div>
              <div className="w-8 h-8 rounded-full bg-indigo-950 border border-indigo-700/60 flex items-center justify-center font-bold text-xs text-indigo-300">
                RV
              </div>
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col p-4 gap-4 max-w-[1920px] w-full mx-auto">
          {children}
        </main>
      </body>
    </html>
  );
}
