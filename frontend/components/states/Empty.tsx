"use client";
import React from "react";

interface EmptyStateProps {
  message?: string;
  chips?: Array<{ label: string; value: string }>;
  onChipClick?: (value: string) => void;
}

export function EmptyState({
  message = "No sailings match those dates.",
  chips,
  onChipClick,
}: EmptyStateProps) {
  return (
    <div
      className="mt-3 rounded-2xl p-6 text-center"
      style={{
        background: "rgba(12,35,64,.04)",
        border: "1px dashed rgba(12,35,64,.15)",
      }}
    >
      <div style={{ fontSize: 32, marginBottom: 8 }}>🧭</div>
      <p className="font-display text-base font-medium mb-1" style={{ color: "#0C2340" }}>
        {message}
      </p>
      {chips && chips.length > 0 && (
        <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap", marginTop: 12 }}>
          {chips.map((chip) => (
            <button
              key={chip.value}
              onClick={() => onChipClick?.(chip.value)}
              style={{
                padding: "6px 16px",
                borderRadius: 999,
                border: "1px solid #C8A45C",
                background: "rgba(200,164,92,.10)",
                color: "#0C2340",
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {chip.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
