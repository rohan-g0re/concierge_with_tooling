/**
 * ItineraryPanel — 480px right slide-over (frame 1d).
 *
 * Shows day-by-day itinerary for a selected cruise.
 *
 * Footer input → scoped itinerary Q&A. The answer is rendered INSIDE the panel
 * (below the input) and the panel stays OPEN. To avoid polluting the main chat
 * transcript with the scoped message, the panel issues its OWN local postChat
 * call and accumulates the streamed deltas into local component state
 * (`answer`) — the parent's `sendMessage`/transcript is never touched. The
 * `onAsk` callback is retained purely as an optional notification hook.
 */
"use client";

import React, { useState, useRef, useEffect } from "react";

import { postChat } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ItineraryDay {
  day: string;
  port: string;
  note?: string | null;
  tag?: string | null;
  dot: string;
  ring: string;
  thumb: boolean;
}

export interface ItineraryPanelProps {
  cruiseId: string;
  cruiseName: string;
  nights: number;
  isCruisetour?: boolean;
  datesLine?: string;
  ship?: string;
  days: ItineraryDay[];
  loading?: boolean;
  /** Session id used for the panel-local scoped Q&A postChat call. */
  sessionId: string;
  onClose: () => void;
  /**
   * Optional notification hook fired with the scoped message when the user asks
   * a question. The panel handles the request itself (local postChat), so this
   * is NOT required to render the answer and must NOT re-send into main chat.
   */
  onAsk?: (message: string) => void;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function RouteStrip() {
  return (
    <div
      style={{
        height: "64px",
        background: "repeating-linear-gradient(90deg,#DCE4EC 0 10px,#E6EBF1 10px 20px)",
        position: "relative",
        flexShrink: 0,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "linear-gradient(180deg,rgba(12,35,64,.06),rgba(12,35,64,.3))",
        }}
      />
    </div>
  );
}

function DayRow({ day, isLast }: { day: ItineraryDay; isLast: boolean }) {
  return (
    <div style={{ display: "flex", gap: "16px" }}>
      {/* Timeline column */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          width: "12px",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: "11px",
            height: "11px",
            borderRadius: "50%",
            background: day.dot,
            border: `2px solid ${day.ring}`,
            flexShrink: 0,
            marginTop: "4px",
          }}
        />
        {!isLast && (
          <div
            style={{
              width: "1px",
              flex: 1,
              background: "rgba(12,35,64,.14)",
              minHeight: "12px",
            }}
          />
        )}
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          paddingBottom: isLast ? "8px" : "18px",
          display: "flex",
          gap: "12px",
          alignItems: "flex-start",
        }}
      >
        {/* Text block */}
        <div style={{ flex: 1 }}>
          <div
            style={{
              fontSize: "10.5px",
              fontWeight: 600,
              letterSpacing: ".12em",
              textTransform: "uppercase" as const,
              color: "#8A97A6",
            }}
          >
            {day.day}
          </div>
          <div
            style={{
              fontFamily: "'Playfair Display', Georgia, serif",
              fontSize: "16px",
              color: "#0C2340",
              marginTop: "1px",
            }}
          >
            {day.port}
          </div>
          {day.note && (
            <div style={{ fontSize: "12.5px", color: "#5A6B7E", marginTop: "1px" }}>
              {day.note}
            </div>
          )}
          {day.tag && (
            <div
              style={{
                display: "inline-block",
                marginTop: "5px",
                fontSize: "11px",
                fontWeight: 600,
                color: "#4E7E86",
                background: "rgba(78,126,134,.10)",
                padding: "3px 9px",
                borderRadius: "999px",
              }}
            >
              {day.tag}
            </div>
          )}
        </div>

        {/* Thumb placeholder */}
        {day.thumb && (
          <div
            style={{
              width: "64px",
              height: "44px",
              borderRadius: "6px",
              background: "repeating-linear-gradient(135deg,#DCE4EC 0 8px,#E6EBF1 8px 16px)",
              border: "1px solid rgba(12,35,64,.10)",
              flexShrink: 0,
            }}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function ItineraryPanel({
  cruiseId,
  cruiseName,
  nights,
  isCruisetour = false,
  datesLine,
  ship,
  days,
  loading = false,
  sessionId,
  onClose,
  onAsk,
}: ItineraryPanelProps) {
  const [question, setQuestion] = useState("");
  // Panel-local Q&A state — the answer renders inside the panel, not main chat.
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState("");
  const [askedQuestion, setAskedQuestion] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const durLabel = isCruisetour
    ? `${nights}-Day Cruisetour`
    : `${nights}-Night Cruise`;

  const headerDateLine = [datesLine, ship].filter(Boolean).join(" · ");

  async function handleSend() {
    const q = question.trim();
    if (!q || asking) return;

    // Scope message to this itinerary (matches backend scoped-pattern routing).
    const scoped = `About the ${cruiseName} itinerary (${cruiseId}): ${q}`;

    // Optional parent notification — parent must NOT re-send into main chat.
    onAsk?.(scoped);

    // Reset UI to loading state; keep the panel open.
    setAskedQuestion(q);
    setQuestion("");
    setAnswer("");
    setAsking(true);

    try {
      // Local-only postChat: deltas accumulate into panel state. Because this
      // call originates in the panel (not the parent's sendMessage), the scoped
      // message never enters the main transcript.
      await postChat(
        sessionId,
        scoped,
        (delta: string) => setAnswer((prev) => prev + delta),
        () => {
          /* terminal components/chips ignored inside the panel */
        }
      );
    } catch {
      setAnswer("Sorry, I couldn't answer that just now. Please try again.");
    } finally {
      setAsking(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(12,35,64,.28)",
          zIndex: 40,
        }}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Itinerary for ${cruiseName}`}
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          width: "480px",
          height: "100vh",
          background: "#fff",
          boxShadow: "-16px 0 40px rgba(12,35,64,.18)",
          display: "flex",
          flexDirection: "column",
          zIndex: 50,
          overflowY: "hidden",
        }}
      >
        {/* ── Header ── */}
        <div
          style={{
            padding: "24px 28px 16px",
            borderBottom: "1px solid rgba(12,35,64,.10)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            flexShrink: 0,
          }}
        >
          <div>
            <div
              style={{
                fontSize: "10.5px",
                fontWeight: 600,
                letterSpacing: ".14em",
                textTransform: "uppercase",
                color: "#B08F44",
              }}
            >
              {durLabel}
            </div>
            <div
              style={{
                fontFamily: "'Playfair Display', Georgia, serif",
                fontSize: "24px",
                color: "#0C2340",
                marginTop: "4px",
              }}
            >
              {cruiseName}
            </div>
            {headerDateLine && (
              <div
                style={{
                  fontSize: "13px",
                  color: "#5A6B7E",
                  marginTop: "2px",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {headerDateLine}
              </div>
            )}
          </div>

          {/* Close button */}
          <button
            onClick={onClose}
            aria-label="Close itinerary panel"
            style={{
              width: "30px",
              height: "30px",
              borderRadius: "50%",
              border: "1px solid rgba(12,35,64,.18)",
              background: "none",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#5A6B7E",
              cursor: "pointer",
              fontSize: "14px",
              flexShrink: 0,
            }}
          >
            ×
          </button>
        </div>

        {/* ── Route strip ── */}
        <RouteStrip />

        {/* ── Day timeline ── */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "20px 28px",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {loading && (
            <div style={{ fontSize: "14px", color: "#8A97A6", textAlign: "center", padding: "32px 0" }}>
              Loading itinerary…
            </div>
          )}
          {!loading && days.length === 0 && (
            <div style={{ fontSize: "14px", color: "#8A97A6", textAlign: "center", padding: "32px 0" }}>
              No itinerary data available.
            </div>
          )}
          {!loading &&
            days.map((day, i) => (
              <DayRow key={`${day.day}-${i}`} day={day} isLast={i === days.length - 1} />
            ))}
        </div>

        {/* ── Footer: scoped Q&A answer + input ── */}
        <div
          style={{
            padding: "14px 20px 18px",
            borderTop: "1px solid rgba(12,35,64,.10)",
            flexShrink: 0,
          }}
        >
          {/* Answer / loading block — rendered inside the panel */}
          {(asking || answer) && (
            <div
              style={{
                marginBottom: "12px",
                maxHeight: "220px",
                overflowY: "auto",
                background: "#F4F6F8",
                border: "1px solid rgba(12,35,64,.10)",
                borderRadius: "12px",
                padding: "12px 14px",
              }}
              aria-live="polite"
            >
              {askedQuestion && (
                <div
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    letterSpacing: ".06em",
                    textTransform: "uppercase" as const,
                    color: "#8A97A6",
                    marginBottom: "6px",
                  }}
                >
                  {askedQuestion}
                </div>
              )}
              {asking && !answer ? (
                <div style={{ fontSize: "13.5px", color: "#8A97A6" }}>Thinking…</div>
              ) : (
                <div style={{ fontSize: "13.5px", color: "#22344B", lineHeight: 1.5 }}>
                  {answer}
                </div>
              )}
            </div>
          )}

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              background: "#F4F6F8",
              border: "1px solid rgba(12,35,64,.12)",
              borderRadius: "999px",
              padding: "6px 6px 6px 18px",
            }}
          >
            <input
              ref={inputRef}
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={asking}
              placeholder={asking ? "Waiting for answer…" : "Ask about this itinerary…"}
              style={{
                flex: 1,
                fontSize: "13.5px",
                color: "#22344B",
                background: "none",
                border: "none",
                outline: "none",
              }}
            />
            <button
              onClick={() => void handleSend()}
              disabled={!question.trim() || asking}
              aria-label="Send question"
              style={{
                width: "30px",
                height: "30px",
                borderRadius: "50%",
                background: question.trim() && !asking ? "#C8A45C" : "rgba(200,164,92,.4)",
                border: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: question.trim() && !asking ? "pointer" : "default",
                flexShrink: 0,
                transition: "background 0.15s",
              }}
            >
              <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true">
                <path
                  d="M3 8 h9 M8.5 4.5 12 8 l-3.5 3.5"
                  stroke="#0C2340"
                  strokeWidth="1.8"
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
