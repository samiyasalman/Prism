"use client";

import { useRef, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { api } from "@/lib/api";

interface MoneyValue {
  amount: number;
  currency: string;
  converted_amount: number;
  converted_currency: string;
}

interface AnalysisResult {
  summary: {
    text: string;
    country_context: string;
    currency_context: string;
  };
  financial_signals: {
    monthly_income: MoneyValue | null;
    annual_income: MoneyValue | null;
    outstanding_loan_balances: MoneyValue | null;
    credit_card_balances: MoneyValue | null;
    recurring_obligations: Record<string, MoneyValue> | null;
  };
  missing_signals: string[];
  processing_metadata: {
    date_processed: string;
    tools_used: string[];
    notes: string;
  };
}

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "fr", label: "French" },
  { value: "es", label: "Spanish" },
  { value: "de", label: "German" },
];

const CURRENCIES = [
  { value: "USD", label: "USD" },
  { value: "EUR", label: "EUR" },
  { value: "GBP", label: "GBP" },
  { value: "CHF", label: "CHF" },
];

function formatMoney(val: MoneyValue | null): string {
  if (!val) return "—";
  const converted = `${val.converted_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} ${val.converted_currency}`;
  if (val.currency === val.converted_currency) return converted;
  return `${converted} (orig ${val.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} ${val.currency})`;
}

export default function FinancialAgentPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [language, setLanguage] = useState("en");
  const [currency, setCurrency] = useState("USD");
  const [processing, setProcessing] = useState(false);
  const [step, setStep] = useState("");
  const [error, setError] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setSelectedFiles(Array.from(e.target.files));
  };

  const handleAnalyze = async () => {
    if (selectedFiles.length === 0) return;
    setProcessing(true);
    setError("");
    setResult(null);

    try {
      setStep("Uploading documents...");
      const formData = new FormData();
      for (const f of selectedFiles) formData.append("files", f);

      const token = api.getToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const uploadRes = await fetch("/api/agent/upload", { method: "POST", headers, body: formData });
      if (!uploadRes.ok) {
        const body = await uploadRes.json().catch(() => ({ detail: uploadRes.statusText }));
        throw new Error(body.detail || `Upload failed: ${uploadRes.status}`);
      }
      const { file_ids } = await uploadRes.json();

      setStep("Analyzing documents...");
      const analyzeRes = await fetch("/api/agent/analyze", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ file_ids, target_language: language, target_currency: currency }),
      });
      if (!analyzeRes.ok) {
        const body = await analyzeRes.json().catch(() => ({ detail: analyzeRes.statusText }));
        throw new Error(body.detail || `Analysis failed: ${analyzeRes.status}`);
      }
      setResult(await analyzeRes.json());
    } catch (err: any) {
      setError(err.message || "Something went wrong");
    } finally {
      setProcessing(false);
      setStep("");
    }
  };

  return (
    <AppLayout
      title="Analyzer"
      action={
        <button
          onClick={handleAnalyze}
          disabled={processing || selectedFiles.length === 0}
          className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 transition"
        >
          {processing ? step || "Processing..." : "Analyze"}
        </button>
      }
    >
      {/* Config panel */}
      <div className="border border-slate-200 rounded-md p-5 mb-6">
        <div className="flex items-end gap-4 flex-wrap">
          <div>
            <label className="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Files</label>
            <div className="flex items-center gap-2">
              <button
                onClick={() => fileRef.current?.click()}
                className="px-3 py-1.5 text-sm border border-slate-300 rounded-md hover:bg-slate-50 transition"
              >
                Choose Files
              </button>
              <span className="text-sm text-slate-400">
                {selectedFiles.length === 0 ? "None" : `${selectedFiles.length} file(s)`}
              </span>
              <input ref={fileRef} type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.tiff" onChange={handleFileChange} className="hidden" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Language</label>
            <select value={language} onChange={(e) => setLanguage(e.target.value)} className="border border-slate-300 rounded-md px-2.5 py-1.5 text-sm">
              {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Currency</label>
            <select value={currency} onChange={(e) => setCurrency(e.target.value)} className="border border-slate-300 rounded-md px-2.5 py-1.5 text-sm">
              {CURRENCIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 text-red-600 rounded-md text-sm">{error}</div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Summary */}
          <div className="border border-slate-200 rounded-md p-5">
            <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wide mb-2">Summary</h2>
            <p className="text-sm text-slate-700 mb-4">{result.summary.text}</p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-slate-400 uppercase tracking-wide">Country Context</p>
                <p className="text-sm text-slate-600 mt-0.5">{result.summary.country_context}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400 uppercase tracking-wide">Currency Context</p>
                <p className="text-sm text-slate-600 mt-0.5">{result.summary.currency_context}</p>
              </div>
            </div>
          </div>

          {/* Financial Signals */}
          <div className="border border-slate-200 rounded-md">
            <div className="px-5 py-3 border-b border-slate-200">
              <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wide">Financial Signals</h2>
            </div>
            <div className="divide-y divide-slate-100">
              {[
                { label: "Monthly Income", value: result.financial_signals.monthly_income },
                { label: "Annual Income", value: result.financial_signals.annual_income },
                { label: "Outstanding Loans", value: result.financial_signals.outstanding_loan_balances },
                { label: "Credit Card Balances", value: result.financial_signals.credit_card_balances },
              ].map((item) => (
                <div key={item.label} className="flex justify-between px-5 py-2.5">
                  <span className="text-sm text-slate-500">{item.label}</span>
                  <span className="text-sm font-mono text-slate-800 tabular-nums">{formatMoney(item.value)}</span>
                </div>
              ))}
              {result.financial_signals.recurring_obligations &&
                Object.entries(result.financial_signals.recurring_obligations).map(([key, val]) => (
                  <div key={key} className="flex justify-between px-5 py-2.5">
                    <span className="text-sm text-slate-500 capitalize">{key}</span>
                    <span className="text-sm font-mono text-slate-800 tabular-nums">{formatMoney(val)}</span>
                  </div>
                ))}
            </div>
          </div>

          {/* Missing Signals */}
          {result.missing_signals.length > 0 && (
            <div className="px-4 py-3 bg-amber-50 border border-amber-200 rounded-md">
              <p className="text-xs font-medium text-amber-700 uppercase tracking-wide mb-0.5">Missing Signals</p>
              <p className="text-sm text-amber-600">{result.missing_signals.join(", ")}</p>
            </div>
          )}

          {/* Metadata */}
          <div className="text-xs text-slate-400">
            Processed {new Date(result.processing_metadata.date_processed).toLocaleString()} · Tools: {result.processing_metadata.tools_used.join(", ")}
            {result.processing_metadata.notes && <span> · {result.processing_metadata.notes}</span>}
          </div>

          {/* Raw JSON */}
          <div>
            <button onClick={() => setShowRaw(!showRaw)} className="text-xs text-indigo-600 hover:underline">
              {showRaw ? "Hide" : "Show"} raw JSON
            </button>
            {showRaw && (
              <pre className="mt-2 bg-slate-900 text-slate-300 p-4 rounded-md text-xs overflow-auto max-h-80 font-mono">
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}
    </AppLayout>
  );
}
