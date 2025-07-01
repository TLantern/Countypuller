"use client";
import React, { useEffect, useState } from "react";

interface SavedReport {
  canonical_address: string;
  attomid: string | null;
  owner_name: string | null;
  primary_phone: string | null;
  primary_email: string | null;
  processed_at: string;
}

export default function SavedQueriesReports() {
  const [reports, setReports] = useState<SavedReport[]>([]);

  useEffect(() => {
    const storageKey = "savedSkipTraces";
    try {
      const saved: SavedReport[] = JSON.parse(localStorage.getItem(storageKey) || "[]");
      setReports(saved.reverse()); // newest first
    } catch {
      setReports([]);
    }
  }, []);

  if (!reports.length) {
    return <div className="p-8 text-gray-600">No saved reports.</div>;
  }

  return (
    <div className="p-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {reports.map((r, idx) => (
        <div key={idx} className="bg-white rounded-lg shadow p-4 border">
          <div className="font-semibold text-lg mb-2">{r.canonical_address}</div>
          {r.owner_name && <div className="text-sm text-gray-700">Owner: {r.owner_name}</div>}
          {r.primary_phone && <div className="text-sm text-gray-700">📞 {r.primary_phone}</div>}
          {r.primary_email && <div className="text-sm text-gray-700">✉️ {r.primary_email}</div>}
          <div className="text-xs text-gray-500 mt-2">Saved {new Date(r.processed_at).toLocaleString()}</div>
        </div>
      ))}
    </div>
  );
} 