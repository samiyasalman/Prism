"use client";

import { useEffect, useRef, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

interface Document {
  id: string;
  filename: string;
  content_type: string;
  file_size: number;
  status: string;
  document_type: string | null;
  error_message: string | null;
  created_at: string;
}

interface Transaction {
  id: string;
  category: string;
  amount: number;
  currency: string;
  transaction_date: string | null;
  payee: string | null;
  description: string | null;
  is_on_time: boolean | null;
  confidence: number;
}

const STATUS_COLORS: Record<string, string> = {
  uploaded: "bg-slate-100 text-slate-600",
  extracting: "bg-blue-50 text-blue-600",
  analyzing: "bg-amber-50 text-amber-600",
  completed: "bg-emerald-50 text-emerald-600",
  failed: "bg-red-50 text-red-600",
};

const DOC_TYPE_LABELS: Record<string, string> = {
  bank_statement: "Bank Statement",
  rent_receipt: "Rent Receipt",
  utility_bill: "Utility Bill",
  pay_stub: "Pay Stub",
};

export default function DocumentsPage() {
  const { user } = useAuth();
  const fileRef = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState("");
  const [selectedDoc, setSelectedDoc] = useState<(Document & { transactions?: Transaction[] }) | null>(null);
  const pollRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    if (user) loadDocuments();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [user]);

  const loadDocuments = async () => {
    try {
      setError("");
      const docs = await api.getDocuments();
      setDocuments(docs);
    } catch (err: any) {
      console.error("Failed to load documents:", err);
      setError(err.message || "Failed to load documents");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const processing = documents.filter((d) => ["uploaded", "extracting", "analyzing"].includes(d.status));
    if (processing.length === 0) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    pollRef.current = setInterval(async () => {
      let changed = false;
      for (const doc of processing) {
        try {
          const status = await api.getDocumentStatus(doc.id);
          if (status.status !== doc.status) changed = true;
        } catch {}
      }
      if (changed) loadDocuments();
    }, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [documents]);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      for (let i = 0; i < files.length; i++) {
        await api.uploadDocument(files[i]);
      }
      await loadDocuments();
    } catch (err: any) {
      alert(err.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    handleUpload(e.dataTransfer.files);
  };

  const viewDetails = async (doc: Document) => {
    try {
      const detail = await api.getDocument(doc.id);
      setSelectedDoc(detail);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <AppLayout
      title="Documents"
      action={
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 transition"
        >
          {uploading ? "Uploading..." : "Upload"}
        </button>
      }
    >
      {error && (
        <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 text-red-600 rounded-md text-sm">
          {error}
        </div>
      )}

      {/* Upload zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        className={`border border-dashed rounded-md px-6 py-6 text-center transition mb-6 ${
          dragActive ? "border-indigo-400 bg-indigo-50/50" : "border-slate-300"
        }`}
      >
        <p className="text-sm text-slate-500">
          Drag & drop files here, or{" "}
          <button
            onClick={() => fileRef.current?.click()}
            className="text-indigo-600 hover:underline"
          >
            browse
          </button>
        </p>
        <p className="text-xs text-slate-400 mt-1">PDF, PNG, JPEG, TIFF</p>
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.tiff"
          onChange={(e) => handleUpload(e.target.files)}
          className="hidden"
        />
      </div>

      {/* Documents table */}
      {loading ? (
        <p className="text-sm text-slate-400">Loading...</p>
      ) : documents.length > 0 ? (
        <div className="border border-slate-200 rounded-md overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left px-4 py-2 font-medium text-slate-500 text-xs uppercase tracking-wide">File</th>
                <th className="text-left px-4 py-2 font-medium text-slate-500 text-xs uppercase tracking-wide">Type</th>
                <th className="text-left px-4 py-2 font-medium text-slate-500 text-xs uppercase tracking-wide">Status</th>
                <th className="text-left px-4 py-2 font-medium text-slate-500 text-xs uppercase tracking-wide">Date</th>
                <th className="text-right px-4 py-2 font-medium text-slate-500 text-xs uppercase tracking-wide"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {documents.map((doc) => (
                <tr key={doc.id} className="hover:bg-slate-50/50">
                  <td className="px-4 py-2.5 text-slate-800">{doc.filename}</td>
                  <td className="px-4 py-2.5 text-slate-500">
                    {doc.document_type ? DOC_TYPE_LABELS[doc.document_type] || doc.document_type : "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[doc.status] || ""}`}>
                      {doc.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-400 tabular-nums">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {doc.status === "completed" && (
                      <button
                        onClick={() => viewDetails(doc)}
                        className="text-indigo-600 hover:underline text-sm"
                      >
                        View
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-slate-400">No documents uploaded yet.</p>
      )}

      {/* Detail modal */}
      {selectedDoc && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-md border border-slate-200 max-w-3xl w-full max-h-[80vh] overflow-auto">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">{selectedDoc.filename}</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  {DOC_TYPE_LABELS[selectedDoc.document_type || ""] || selectedDoc.document_type || "Unknown"} · {selectedDoc.status}
                </p>
              </div>
              <button
                onClick={() => setSelectedDoc(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="px-5 py-4">
              {selectedDoc.transactions && selectedDoc.transactions.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200">
                      <th className="text-left py-2 font-medium text-slate-500 text-xs uppercase tracking-wide">Date</th>
                      <th className="text-left py-2 font-medium text-slate-500 text-xs uppercase tracking-wide">Payee</th>
                      <th className="text-left py-2 font-medium text-slate-500 text-xs uppercase tracking-wide">Category</th>
                      <th className="text-right py-2 font-medium text-slate-500 text-xs uppercase tracking-wide">Amount</th>
                      <th className="text-center py-2 font-medium text-slate-500 text-xs uppercase tracking-wide">On Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {selectedDoc.transactions.map((txn: Transaction) => (
                      <tr key={txn.id}>
                        <td className="py-2 text-slate-500 tabular-nums">
                          {txn.transaction_date ? new Date(txn.transaction_date).toLocaleDateString() : "—"}
                        </td>
                        <td className="py-2 text-slate-700">{txn.payee || "—"}</td>
                        <td className="py-2 text-slate-500">{txn.category}</td>
                        <td className={`py-2 text-right font-mono tabular-nums ${txn.amount >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                          {txn.amount >= 0 ? "+" : ""}${Math.abs(txn.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-2 text-center text-slate-400">
                          {txn.is_on_time === true ? "✓" : txn.is_on_time === false ? "✗" : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-sm text-slate-400">No transactions extracted.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
