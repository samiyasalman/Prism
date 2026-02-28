"use client";

import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export default function Home() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b bg-white">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-indigo-600">Prism</h1>
          <div className="flex gap-3">
            {user ? (
              <Link
                href="/dashboard"
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
              >
                Dashboard
              </Link>
            ) : (
              <>
                <Link href="/login" className="px-4 py-2 text-indigo-600 hover:underline">
                  Log in
                </Link>
                <Link
                  href="/signup"
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                  Sign up
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-6">
        <div className="max-w-2xl text-center">
          <h2 className="text-5xl font-bold tracking-tight text-slate-900 mb-6">
            Your Financial Reputation,{" "}
            <span className="text-indigo-600">Portable & Verified</span>
          </h2>
          <p className="text-xl text-slate-600 mb-8">
            Upload financial documents — rent receipts, bank statements, pay stubs — and
            Prism builds a verifiable reputation score you can share with landlords,
            banks, and employers anywhere in the world.
          </p>
          <div className="flex gap-4 justify-center">
            <Link
              href="/signup"
              className="px-6 py-3 bg-indigo-600 text-white text-lg rounded-lg hover:bg-indigo-700 transition"
            >
              Get Started Free
            </Link>
            <Link
              href="/login"
              className="px-6 py-3 border border-slate-300 text-slate-700 text-lg rounded-lg hover:bg-slate-50 transition"
            >
              Log in
            </Link>
          </div>

          <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8 text-left">
            <div className="bg-white p-6 rounded-xl shadow-sm border">
              <div className="text-3xl mb-3">📄</div>
              <h3 className="font-semibold text-lg mb-2">Upload Documents</h3>
              <p className="text-slate-600 text-sm">
                Bank statements, rent receipts, utility bills, pay stubs — any proof of financial responsibility.
              </p>
            </div>
            <div className="bg-white p-6 rounded-xl shadow-sm border">
              <div className="text-3xl mb-3">🤖</div>
              <h3 className="font-semibold text-lg mb-2">AI-Powered Analysis</h3>
              <p className="text-slate-600 text-sm">
                IBM watsonx.ai extracts and verifies transaction data, building claims about your financial behavior.
              </p>
            </div>
            <div className="bg-white p-6 rounded-xl shadow-sm border">
              <div className="text-3xl mb-3">🔗</div>
              <h3 className="font-semibold text-lg mb-2">Share Securely</h3>
              <p className="text-slate-600 text-sm">
                Generate cryptographically signed, time-limited links with selective disclosure controls.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
