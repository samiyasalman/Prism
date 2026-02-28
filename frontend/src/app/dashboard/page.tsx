"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppLayout from "@/components/AppLayout";
import TrustScoreGauge from "@/components/TrustScoreGauge";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

interface Claim {
  id: string;
  claim_type: string;
  claim_text: string;
  claim_data: any;
  confidence: number;
}

interface Profile {
  score: number;
  level: string;
  breakdown: Record<string, { raw_score: number; weight: number; weighted: number }>;
  claims: Claim[];
}

const CLAIM_LABELS: Record<string, string> = {
  rent_history: "Rent History",
  income_stability: "Income Stability",
  utility_payment: "Utility Payments",
  bank_health: "Bank Health",
};

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);

  useEffect(() => {
    if (user) {
      api.getProfile().then(setProfile).catch(console.error).finally(() => setLoading(false));
    }
  }, [user]);

  const handleRecalculate = async () => {
    setRecalculating(true);
    try {
      const p = await api.recalculate();
      setProfile(p);
    } catch (err) {
      console.error(err);
    } finally {
      setRecalculating(false);
    }
  };

  if (authLoading || loading) {
    return (
      <AppLayout title="Dashboard">
        <p className="text-sm text-slate-400">Loading...</p>
      </AppLayout>
    );
  }

  return (
    <AppLayout
      title="Dashboard"
      action={
        <div className="flex gap-2">
          <button
            onClick={handleRecalculate}
            disabled={recalculating}
            className="px-3 py-1.5 text-sm border border-slate-300 rounded-md hover:bg-slate-50 disabled:opacity-50 transition"
          >
            {recalculating ? "Recalculating..." : "Recalculate"}
          </button>
          <Link
            href="/documents"
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition"
          >
            Upload Documents
          </Link>
        </div>
      }
    >
      {/* Score + Breakdown */}
      <div className="flex gap-8 mb-10">
        {/* Score panel */}
        <div className="w-80 shrink-0 border border-slate-200 rounded-md p-5">
          <h2 className="text-sm font-medium text-slate-500 mb-4">Prism Score</h2>
          <TrustScoreGauge
            score={profile?.score ?? 0}
            level={profile?.level ?? "No Data"}
          />
        </div>

        {/* Breakdown */}
        <div className="flex-1 border border-slate-200 rounded-md p-5">
          <h2 className="text-sm font-medium text-slate-500 mb-4">Score Breakdown</h2>
          {profile?.breakdown && Object.keys(profile.breakdown).length > 0 ? (
            <div className="space-y-4">
              {Object.entries(profile.breakdown).map(([key, val]) => (
                <div key={key}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-700">
                      {CLAIM_LABELS[key] || key}
                      <span className="text-slate-400 ml-1">({(val.weight * 100).toFixed(0)}%)</span>
                    </span>
                    <span className="text-slate-500 tabular-nums">{val.raw_score.toFixed(0)}</span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-1.5">
                    <div
                      className="bg-indigo-500 h-1.5 rounded-full transition-all duration-500"
                      style={{ width: `${val.raw_score}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">
              No data yet. Upload financial documents to build your score.
            </p>
          )}
        </div>
      </div>

      {/* Claims */}
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-3">Verified Claims</h2>
        {profile?.claims && profile.claims.length > 0 ? (
          <div className="border border-slate-200 rounded-md divide-y divide-slate-200">
            {profile.claims.map((claim) => (
              <div key={claim.id} className="flex items-center justify-between px-4 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-800">
                    {CLAIM_LABELS[claim.claim_type] || claim.claim_type}
                  </p>
                  <p className="text-sm text-slate-500 truncate">{claim.claim_text}</p>
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-6">
                  <div className="w-24 bg-slate-100 rounded-full h-1.5">
                    <div
                      className="h-1.5 bg-emerald-500 rounded-full"
                      style={{ width: `${claim.confidence * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-slate-400 tabular-nums w-8">
                    {(claim.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="border border-slate-200 rounded-md p-6 text-center">
            <p className="text-sm text-slate-400">No claims yet.</p>
            <Link href="/documents" className="text-sm text-indigo-600 hover:underline mt-1 inline-block">
              Upload documents to generate claims
            </Link>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
