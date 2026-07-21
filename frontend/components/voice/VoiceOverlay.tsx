/**
 * Compass — VoiceOverlay
 *
 * Bottom-sheet voice UI shown when the mic toggle is active.
 * Renders: waveform animation, live transcript line, barge-in affordance,
 * "Switch to typing" link, stop control.
 *
 * Frame 1l pattern: waveform sheet + "Listening — tap to interrupt" + transcript.
 *
 * Degrades gracefully when voice is unavailable (shows polite message).
 */
"use client";

import React from "react";
import type { VoiceState } from "../../lib/voiceClient";

type Props = {
  state: VoiceState;
  transcript: string;
  unavailableMessage?: string;
  onInterrupt: () => void;
  onStop: () => void;
  onSwitchToTyping: () => void;
};

const STATE_LABELS: Record<VoiceState, string> = {
  idle: "Starting…",
  connecting: "Connecting…",
  listening: "Listening — tap to interrupt",
  speaking: "Speaking…",
  interrupted: "Interrupted",
  disconnected: "Disconnected",
};

/** Simple CSS waveform bars (pure CSS, no canvas needed). */
function Waveform({ active }: { active: boolean }) {
  const barCount = 5;
  return (
    <div
      aria-hidden
      style={{
        display: "flex",
        alignItems: "center",
        gap: 4,
        height: 32,
      }}
    >
      {Array.from({ length: barCount }).map((_, i) => (
        <div
          key={i}
          style={{
            width: 4,
            borderRadius: 2,
            background: active ? "#0C2340" : "#8A97A6",
            height: active ? undefined : 8,
            animation: active ? `wave-${i % 3} 0.8s ease-in-out infinite` : "none",
            animationDelay: `${i * 0.1}s`,
          }}
        />
      ))}
      <style>{`
        @keyframes wave-0 { 0%,100%{height:8px} 50%{height:28px} }
        @keyframes wave-1 { 0%,100%{height:14px} 50%{height:20px} }
        @keyframes wave-2 { 0%,100%{height:20px} 50%{height:8px} }
      `}</style>
    </div>
  );
}

export function VoiceOverlay({
  state,
  transcript,
  unavailableMessage,
  onInterrupt,
  onStop,
  onSwitchToTyping,
}: Props) {
  const isListening = state === "listening";
  const isSpeaking = state === "speaking";
  const isActive = isListening || isSpeaking || state === "interrupted";

  if (state === "disconnected" && unavailableMessage) {
    // Voice unavailable state (RK9 graceful degradation)
    return (
      <div
        role="status"
        aria-live="polite"
        style={{
          position: "fixed",
          bottom: 80,
          left: "50%",
          transform: "translateX(-50%)",
          background: "#fff",
          border: "1px solid #E2E8F0",
          borderRadius: 16,
          boxShadow: "0 4px 24px rgba(12,35,64,0.12)",
          padding: "20px 24px",
          maxWidth: 360,
          width: "calc(100vw - 32px)",
          display: "flex",
          flexDirection: "column",
          gap: 12,
          zIndex: 50,
        }}
      >
        <p style={{ color: "#475569", fontSize: 14, margin: 0, textAlign: "center" }}>
          {unavailableMessage}
        </p>
        <button
          onClick={onSwitchToTyping}
          style={{
            background: "none",
            border: "none",
            color: "#0C2340",
            fontSize: 13,
            cursor: "pointer",
            textDecoration: "underline",
            padding: 0,
            alignSelf: "center",
          }}
        >
          Switch to typing
        </button>
      </div>
    );
  }

  return (
    <div
      role="dialog"
      aria-label="Voice session"
      aria-live="polite"
      style={{
        position: "fixed",
        bottom: 80,
        left: "50%",
        transform: "translateX(-50%)",
        background: "#fff",
        border: "1px solid #E2E8F0",
        borderRadius: 24,
        boxShadow: "0 8px 32px rgba(12,35,64,0.16)",
        padding: "24px 28px",
        maxWidth: 400,
        width: "calc(100vw - 32px)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 16,
        zIndex: 50,
      }}
    >
      {/* Waveform */}
      <Waveform active={isActive} />

      {/* State label */}
      <p
        style={{
          color: "#0C2340",
          fontSize: 14,
          fontWeight: 500,
          margin: 0,
          letterSpacing: "0.01em",
        }}
      >
        {STATE_LABELS[state]}
      </p>

      {/* Live transcript */}
      {transcript && (
        <p
          aria-label="Live transcript"
          style={{
            color: "#475569",
            fontSize: 13,
            margin: 0,
            textAlign: "center",
            fontStyle: "italic",
            maxWidth: 320,
          }}
        >
          &ldquo;{transcript}&rdquo;
        </p>
      )}

      {/* Controls row */}
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        {/* Barge-in / interrupt button (shown while speaking) */}
        {isSpeaking && (
          <button
            onClick={onInterrupt}
            aria-label="Interrupt assistant"
            style={{
              background: "#F1F5F9",
              border: "none",
              borderRadius: 20,
              padding: "8px 16px",
              fontSize: 13,
              color: "#0C2340",
              cursor: "pointer",
              fontWeight: 500,
            }}
          >
            Interrupt
          </button>
        )}

        {/* Stop button */}
        <button
          onClick={onStop}
          aria-label="Stop voice session"
          style={{
            background: "#0C2340",
            border: "none",
            borderRadius: 20,
            width: 40,
            height: 40,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
            <rect x="1" y="1" width="10" height="10" rx="2" fill="#fff" />
          </svg>
        </button>
      </div>

      {/* Switch to typing */}
      <button
        onClick={onSwitchToTyping}
        style={{
          background: "none",
          border: "none",
          color: "#64748B",
          fontSize: 12,
          cursor: "pointer",
          textDecoration: "underline",
          padding: 0,
        }}
      >
        Switch to typing
      </button>
    </div>
  );
}
