"use client";
import React, { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface FeedbackProps {
  messageId: string;
  stateSnapshot?: Record<string, unknown>;
}

export function Feedback({ messageId, stateSnapshot = {} }: FeedbackProps) {
  const [voted, setVoted] = useState<"up" | "down" | null>(null);

  const handleVote = async (vote: "up" | "down") => {
    if (voted) return; // already voted
    setVoted(vote);
    try {
      await fetch(`${API_BASE}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message_id: messageId, vote, state_snapshot: stateSnapshot }),
      });
    } catch {
      // fire and forget — don't surface network errors for feedback
    }
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        marginTop: 4,
      }}
      aria-label="Rate this response"
    >
      <button
        onClick={() => handleVote("up")}
        aria-label="Thumbs up"
        title="Helpful"
        style={{
          background: "none",
          border: "none",
          cursor: voted ? "default" : "pointer",
          fontSize: 14,
          opacity: voted === "down" ? 0.35 : voted === "up" ? 1 : 0.6,
          transition: "opacity .15s",
          padding: "2px 4px",
        }}
      >
        👍
      </button>
      <button
        onClick={() => handleVote("down")}
        aria-label="Thumbs down"
        title="Not helpful"
        style={{
          background: "none",
          border: "none",
          cursor: voted ? "default" : "pointer",
          fontSize: 14,
          opacity: voted === "up" ? 0.35 : voted === "down" ? 1 : 0.6,
          transition: "opacity .15s",
          padding: "2px 4px",
        }}
      >
        👎
      </button>
      {voted && (
        <span style={{ fontSize: 11, color: "#8A97A6", marginLeft: 2 }}>
          Thanks for the feedback
        </span>
      )}
    </div>
  );
}
