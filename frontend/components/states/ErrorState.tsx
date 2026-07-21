"use client";
import React from "react";

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({
  message = "That didn't go through.",
  onRetry,
}: ErrorStateProps) {
  return (
    <div
      className="mt-3 rounded-2xl p-5"
      style={{
        background: "rgba(217,232,232,0.35)",
        border: "1px solid rgba(12,35,64,.12)",
      }}
    >
      <p className="font-sans text-sm mb-3" style={{ color: "#5A6B7E" }}>
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            padding: "7px 20px",
            borderRadius: 999,
            background: "#0C2340",
            color: "#fff",
            fontSize: 13,
            fontWeight: 600,
            border: "none",
            cursor: "pointer",
          }}
        >
          Try again
        </button>
      )}
    </div>
  );
}
