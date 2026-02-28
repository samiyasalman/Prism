"use client";

import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

interface Claim {
  id: string;
  claim_type: string;
  claim_text: string;
  confidence: number;
}

interface Credential {
  id: string;
  token: string;
  share_url: string;
  claim_ids: string[];
  expires_at: string;
  view_count: number;
  is_revoked: boolean;
  created_at: string;
}

const CLAIM_LABELS: Record<string, string> = {
  rent_history: "Rent History",
  income_stability: "Income Stability",
  utility_payment: "Utility Payments",
  bank_health: "Bank Health",
};

export default function CredentialsPage() {
  const { user } = useAuth();
  const [claims, setClaims] = useState<Claim[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [selectedClaims, setSelectedClaims] = useState<Set<string>>(new Set());
  const [expiresHours, setExpiresHours] = useState(168);
  const [, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    if (user) loadData();
  }, [user]);

  const loadData = async () => {
    try {
      const [c, cr] = await Promise.all([api.getClaims(), api.getCredentials()]);
      setClaims(c);
      setCredentials(cr);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const toggleClaim = (id: string) => {
    const next = new Set(selectedClaims);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedClaims(next);
  };

  const handleGenerate = async () => {
    if (selectedClaims.size === 0) return;
    setGenerating(true);
    try {
      await api.generateCredential({
        claim_ids: Array.from(selectedClaims),
        expires_hours: expiresHours,
      });
      setSelectedClaims(new Set());
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to generate credential");
    } finally {
      setGenerating(false);
    }
  };

  const handleRevoke = async (id: string) => {
    if (!confirm("Revoke this credential? The link will no longer be valid.")) return;
    try {
      await api.revokeCredential(id);
      await loadData();
    } catch (err) {
      console.error(err);
    }
  };

  const copyLink = (cred: Credential) => {
    try {
      const textarea = document.createElement("textarea");
      textarea.value = cred.share_url;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopiedId(cred.id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      window.prompt("Copy this link:", cred.share_url);
    }
  };

  return (
    <AppLayout
      title="Credentials"
      action={
        claims.length > 0 ? (
          <button
            onClick={handleGenerate}
            disabled={generating || selectedClaims.size === 0}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 transition"
          >
            {generating ? "Generating..." : "Generate Link"}
          </button>
        ) : undefined
      }
    >
      {/* Generate section */}
      <div className="mb-10">
        <h2 className="text-lg font-semibold text-slate-900 mb-1">Generate Credential</h2>
        <p className="text-sm text-slate-500 mb-4">Select claims to include in a shareable link.</p>

        {claims.length > 0 ? (
          <>
            <div className="border border-slate-200 rounded-md divide-y divide-slate-200 mb-4">
              {claims.map((claim) => (
                <label
                  key={claim.id}
                  className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition ${
                    selectedClaims.has(claim.id) ? "bg-indigo-50/50" : "hover:bg-slate-50"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedClaims.has(claim.id)}
                    onChange={() => toggleClaim(claim.id)}
                    className="accent-indigo-600"
                  />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-slate-800">
                      {CLAIM_LABELS[claim.claim_type] || claim.claim_type}
                    </span>
                    <p className="text-xs text-slate-400 truncate">{claim.claim_text}</p>
                  </div>
                  <span className="text-xs text-slate-400 tabular-nums">
                    {(claim.confidence * 100).toFixed(0)}%
                  </span>
                </label>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <label className="text-sm text-slate-500">Expires in:</label>
              <select
                value={expiresHours}
                onChange={(e) => setExpiresHours(Number(e.target.value))}
                className="border border-slate-300 rounded-md px-2.5 py-1 text-sm"
              >
                <option value={24}>24 hours</option>
                <option value={72}>3 days</option>
                <option value={168}>7 days</option>
                <option value={720}>30 days</option>
              </select>
            </div>
          </>
        ) : (
          <p className="text-sm text-slate-400">
            No claims available. Upload documents and build your reputation first.
          </p>
        )}
      </div>

      {/* Credentials list */}
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-3">Your Credentials</h2>
        {credentials.length > 0 ? (
          <div className="border border-slate-200 rounded-md divide-y divide-slate-200">
            {credentials.map((cred) => {
              const expired = new Date(cred.expires_at) < new Date();
              return (
                <div
                  key={cred.id}
                  className={`flex items-center justify-between px-4 py-3 ${
                    cred.is_revoked || expired ? "opacity-50" : ""
                  }`}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono text-slate-600 truncate">
                        {cred.share_url}
                      </span>
                      {cred.is_revoked && (
                        <span className="px-1.5 py-0.5 bg-red-50 text-red-600 text-xs rounded">Revoked</span>
                      )}
                      {expired && !cred.is_revoked && (
                        <span className="px-1.5 py-0.5 bg-amber-50 text-amber-600 text-xs rounded">Expired</span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Created {new Date(cred.created_at).toLocaleDateString()} · {cred.view_count} view(s) · Expires {new Date(cred.expires_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex gap-2 shrink-0 ml-4">
                    <button
                      onClick={() => copyLink(cred)}
                      className="px-2.5 py-1 text-xs border border-slate-300 rounded-md hover:bg-slate-50 transition"
                    >
                      {copiedId === cred.id ? "Copied!" : "Copy"}
                    </button>
                    {!cred.is_revoked && (
                      <button
                        onClick={() => handleRevoke(cred.id)}
                        className="px-2.5 py-1 text-xs text-red-600 border border-red-200 rounded-md hover:bg-red-50 transition"
                      >
                        Revoke
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-slate-400">No credentials generated yet.</p>
        )}
      </div>
    </AppLayout>
  );
}
