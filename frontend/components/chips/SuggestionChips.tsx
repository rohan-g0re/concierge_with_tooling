/**
 * Compass — SuggestionChips
 * 2-3 tappable chips under assistant turns; tap → sends as user message.
 * Matches frame 1m design: pill chips with navy border, white bg, hover gold.
 */
"use client";

import React from "react";

interface SuggestionChipsProps {
  chips: string[];
  onChipClick: (chip: string) => void;
}

export function SuggestionChips({ chips, onChipClick }: SuggestionChipsProps) {
  if (chips.length === 0) return null;

  return (
    <div className="px-4 pb-2">
      <div className="flex items-center gap-1.5 mb-2">
        <span style={{ color: "#C8A45C", fontSize: "10px" }}>✦</span>
        <span className="font-sans text-xs" style={{ color: "#8A97A6" }}>
          You can also try
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {chips.slice(0, 3).map((chip, i) => (
          <button
            key={i}
            onClick={() => onChipClick(chip)}
            className="font-sans transition-colors"
            style={{
              border: "1px solid rgba(12,35,64,0.25)",
              borderRadius: "999px",
              padding: "8px 18px",
              fontSize: "13.5px",
              color: "#0C2340",
              background: "#fff",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "#C8A45C";
              e.currentTarget.style.background = "rgba(200,164,92,0.06)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "rgba(12,35,64,0.25)";
              e.currentTarget.style.background = "#fff";
            }}
          >
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}
