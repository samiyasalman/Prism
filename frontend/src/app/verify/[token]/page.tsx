"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

interface VerifiedClaim {
  claim_type: string;
  claim_text: string;
  claim_data: any;
  confidence: number;
}

interface VerifyData {
  valid: boolean;
  expired: boolean;
  revoked: boolean;
  issuer: string | null;
  issued_at: string | null;
  expires_at: string | null;
  holder_name: string | null;
  claims: VerifiedClaim[];
}

const CLAIM_LABELS: Record<string, string> = {
  rent_history: "Rent History",
  income_stability: "Income Stability",
  utility_payment: "Utility Payments",
  bank_health: "Bank Health",
};

export default function VerifyPage() {
  const params = useParams();
  const token = params.token as string;
  const [data, setData] = useState<VerifyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    api
      .verifyCredential(token)
      .then(setData)
      .catch((err) => setError(err.message || "Verification failed"))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-sm text-slate-400">Verifying credential...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="border border-slate-200 rounded-md p-6 max-w-md text-center bg-white">
          <h1 className="text-lg font-semibold text-slate-900 mb-1">Verification Failed</h1>
          <p className="text-sm text-slate-500">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-3xl mx-auto px-6 py-3">
          <span className="text-sm font-semibold text-slate-900">Prism Verification</span>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        {/* Status */}
        <div
          className={`px-4 py-3 rounded-md mb-6 flex items-center gap-3 border ${
            data.valid
              ? "bg-emerald-50 border-emerald-200"
              : "bg-red-50 border-red-200"
          }`}
        >
          <div>
            <h2 className={`text-sm font-semibold ${data.valid ? "text-emerald-800" : "text-red-800"}`}>
              {data.valid
                ? "Verified Credential"
                : data.expired ? "Credential Expired"
                : data.revoked ? "Credential Revoked"
                : "Invalid Credential"}
            </h2>
            <p className={`text-xs ${data.valid ? "text-emerald-600" : "text-red-600"}`}>
              {data.valid
                ? "This credential has been cryptographically verified and is currently valid."
                : data.expired ? "This credential has passed its expiration date."
                : data.revoked ? "This credential was revoked by the holder."
                : "The signature could not be verified."}
            </p>
          </div>
        </div>

        {/* Details */}
        <div className="border border-slate-200 rounded-md bg-white mb-6">
          <div className="px-4 py-3 border-b border-slate-200">
            <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wide">Credential Details</h3>
          </div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-3 px-4 py-3 text-sm">
            <div>
              <p className="text-xs text-slate-400">Holder</p>
              <p className="text-slate-700">{data.holder_name || "—"}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Issuer</p>
              <p className="text-slate-700">{data.issuer || "—"}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Issued</p>
              <p className="text-slate-700">{data.issued_at ? new Date(data.issued_at).toLocaleDateString() : "—"}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Expires</p>
              <p className="text-slate-700">{data.expires_at ? new Date(data.expires_at).toLocaleDateString() : "—"}</p>
            </div>
          </div>
        </div>

        {/* Claims */}
        <div className="border border-slate-200 rounded-md bg-white">
          <div className="px-4 py-3 border-b border-slate-200">
            <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wide">Verified Claims</h3>
          </div>
          {data.claims.length > 0 ? (
            <div className="divide-y divide-slate-100">
              {data.claims.map((claim, idx) => (
                <div key={idx} className="flex items-center justify-between px-4 py-3">
                  <div>
                    <p className="text-sm font-medium text-slate-700">
                      {CLAIM_LABELS[claim.claim_type] || claim.claim_type}
                    </p>
                    <p className="text-xs text-slate-400">{claim.claim_text}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-4">
                    <div className="w-16 bg-slate-100 rounded-full h-1.5">
                      <div className="h-1.5 bg-emerald-500 rounded-full" style={{ width: `${claim.confidence * 100}%` }} />
                    </div>
                    <span className="text-xs text-slate-400 tabular-nums">{(claim.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="px-4 py-4">
              <p className="text-sm text-slate-400">No claims available.</p>
            </div>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-slate-400">
          Verified by Prism — Portable Financial Reputation Platform
        </p>
      </main>
    </div>
  );
}
