/**
 * ComparisonView — side-by-side draft comparison (P12).
 *
 * Renders aligned rows from compare_drafts descriptor.
 * Differing rows tinted gold. Per-column "Continue with this" CTA.
 * Cap 3 drafts — polite refusal on compare_cap error.
 */
"use client";

import React, { useState } from "react";
import type { ComponentDescriptor } from "@/lib/api";
import type { RegistryHandlers } from "@/lib/componentRegistry";

interface ComparisonViewProps {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}

export function ComparisonView({ descriptor, handlers }: ComparisonViewProps) {
  const [loadingIdx, setLoadingIdx] = useState<number | null>(null);

  // Error / cap states
  if (descriptor.error === "compare_cap") {
    return (
      <div
        className="mt-3 rounded-xl p-4 border"
        style={{ background: "#fff", borderColor: "rgba(12,35,64,0.12)" }}
      >
        <p className="font-sans text-sm" style={{ color: "#5A6B7E" }}>
          Comparison supports up to three drafts at a time. Please select up to 3 drafts to compare.
        </p>
      </div>
    );
  }

  if (descriptor.error) {
    return (
      <div
        className="mt-3 rounded-xl p-4 border"
        style={{ background: "#fff5f5", borderColor: "rgba(200,50,50,0.2)" }}
      >
        <p className="font-sans text-sm" style={{ color: "#c0392b" }}>
          {(descriptor.message as string) ?? "Could not load comparison."}
        </p>
      </div>
    );
  }

  const rows = (descriptor.rows as Array<{ label: string; values: string[]; differ: boolean }>) ?? [];
  const headers = (descriptor.headers as Array<{ draft_id: string; label: string; ship: string; photo: string }>) ?? [];
  const checkoutUrls = (descriptor.checkout_urls as string[]) ?? [];

  if (rows.length === 0 || headers.length === 0) {
    return (
      <div
        className="mt-3 rounded-xl p-4 border"
        style={{ background: "#fff", borderColor: "rgba(12,35,64,0.12)" }}
      >
        <p className="font-sans text-sm" style={{ color: "#5A6B7E" }}>
          Add a second sailing to compare your options side by side.
        </p>
      </div>
    );
  }

  const colCount = headers.length;

  async function handleContinue(idx: number) {
    const header = headers[idx];
    const url = checkoutUrls[idx] ?? `/checkout/${header.draft_id}`;
    setLoadingIdx(idx);
    try {
      await handlers?.onSetActiveDraft?.(header.draft_id);
    } finally {
      setLoadingIdx(null);
    }
    window.open(url, "_blank");
  }

  return (
    <div
      className="mt-3 rounded-xl overflow-hidden border"
      style={{ background: "#fff", borderColor: "rgba(12,35,64,0.12)" }}
    >
      {/* Title bar */}
      <div
        className="px-4 pt-4 pb-2 flex items-center justify-between"
        style={{ borderBottom: "1px solid rgba(12,35,64,0.08)" }}
      >
        <p
          className="font-display font-semibold text-sm"
          style={{ color: "#0C2340" }}
        >
          Comparing {colCount} drafts
        </p>
        <span className="font-sans text-xs" style={{ color: "#8A97A6" }}>
          Differences highlighted
        </span>
      </div>

      {/* Header row — per-draft labels */}
      <div
        className="grid"
        style={{
          gridTemplateColumns: `170px repeat(${colCount}, 1fr)`,
          borderBottom: "2px solid rgba(12,35,64,0.10)",
          background: "rgba(12,35,64,0.02)",
        }}
      >
        {/* Empty label cell */}
        <div style={{ width: "170px" }} />
        {headers.map((h) => (
          <div
            key={h.draft_id}
            className="py-3 px-3"
          >
            <div
              className="font-display font-semibold text-sm leading-tight"
              style={{ color: "#0C2340" }}
            >
              {h.label}
            </div>
            {h.ship && (
              <div className="font-sans text-xs mt-0.5" style={{ color: "#8A97A6" }}>
                {h.ship}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Data rows */}
      {rows.map((row, i) => (
        <div
          key={i}
          className="grid"
          style={{
            gridTemplateColumns: `170px repeat(${colCount}, 1fr)`,
            background: row.differ ? "rgba(200,164,92,0.08)" : "transparent",
            borderTop: "1px solid rgba(12,35,64,0.06)",
          }}
        >
          {/* Label cell */}
          <div
            className="px-4 py-2.5 flex items-center"
            style={{ width: "170px" }}
          >
            <span
              className="font-sans text-xs font-semibold"
              style={{ color: row.differ ? "#C8A45C" : "#5A6B7E" }}
            >
              {row.label}
            </span>
            {row.differ && (
              <span
                className="ml-1.5 inline-block w-1.5 h-1.5 rounded-full flex-none"
                style={{ background: "#C8A45C" }}
                aria-label="differs"
              />
            )}
          </div>
          {/* Value cells */}
          {(row.values ?? []).map((val, j) => (
            <div
              key={j}
              className="px-3 py-2.5 font-sans text-xs"
              style={{ color: "#22344B" }}
            >
              {String(val ?? "—")}
            </div>
          ))}
        </div>
      ))}

      {/* CTA row — per-column "Continue with this" */}
      <div
        className="grid"
        style={{
          gridTemplateColumns: `170px repeat(${colCount}, 1fr)`,
          borderTop: "2px solid rgba(12,35,64,0.10)",
          background: "rgba(12,35,64,0.02)",
        }}
      >
        <div style={{ width: "170px" }} />
        {headers.map((h, idx) => (
          <div key={h.draft_id} className="px-3 py-3">
            <button
              onClick={() => handleContinue(idx)}
              disabled={loadingIdx !== null}
              className="w-full py-2 rounded-full font-sans font-semibold text-xs transition-opacity"
              style={{
                background: "#0C2340",
                color: "#fff",
                opacity: loadingIdx !== null ? 0.6 : 1,
                cursor: loadingIdx !== null ? "not-allowed" : "pointer",
              }}
              aria-label={`Continue with ${h.label}`}
            >
              {loadingIdx === idx ? "Setting…" : "Continue with this"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
