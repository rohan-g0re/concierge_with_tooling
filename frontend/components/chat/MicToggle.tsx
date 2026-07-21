/**
 * Compass — MicToggle
 * Visual-only microphone button placeholder.
 * Voice input wired in a later phase.
 */
"use client";

import React from "react";

export function MicToggle() {
  return (
    <button
      type="button"
      aria-label="Voice input (coming soon)"
      disabled
      className="flex-none w-8 h-8 rounded-full flex items-center justify-center"
      style={{
        background: "rgba(12,35,64,0.06)",
        cursor: "not-allowed",
      }}
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 14 14"
        fill="none"
        aria-hidden
      >
        <rect x="4" y="1" width="6" height="8" rx="3" stroke="#8A97A6" strokeWidth="1.5" />
        <path
          d="M2 7c0 2.761 2.239 5 5 5s5-2.239 5-5"
          stroke="#8A97A6"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <line x1="7" y1="12" x2="7" y2="14" stroke="#8A97A6" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </button>
  );
}
