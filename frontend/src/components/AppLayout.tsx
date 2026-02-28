"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import { useAuth } from "@/contexts/AuthContext";

interface Props {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}

export default function AppLayout({ title, action, children }: Props) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-sm text-slate-400">Loading...</p>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-white">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top utility bar */}
        <header className="h-14 shrink-0 flex items-center justify-between px-8 border-b border-slate-200 bg-white">
          <h1 className="text-lg font-semibold text-slate-900">{title}</h1>
          {action && <div>{action}</div>}
        </header>
        {/* Main content */}
        <main className="flex-1 overflow-auto">
          <div className="max-w-[1280px] px-8 py-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
