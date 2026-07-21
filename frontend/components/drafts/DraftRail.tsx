/**
 * DraftRail — 240px right column showing pinned booking drafts.
 *
 * P9: real component replacing the placeholder in page.tsx.
 * Design: frames 1a (active draft + secondary chip), 1b (single draft + empty hint).
 */
"use client";

import React from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DraftInfo {
  draft_id: string;
  label: string;
  completed_steps: number[];
  total_formatted: string | null;
}

export interface DraftRailProps {
  drafts: DraftInfo[];
  activeDraftId: string | null;
  onSetActive: (draftId: string) => void;
  onRemoveDraft: (draftId: string) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ALL_STEPS = [1, 2, 3, 4, 5];

function nextStep(completed: number[]): number {
  const done = new Set(completed);
  for (const s of ALL_STEPS) {
    if (!done.has(s)) return s;
  }
  return 6; // all done
}

/** stroke-dashoffset for a 5-step ring. circumference = 2π×11 ≈ 69.1 */
function ringOffset(completed: number[]): number {
  const fraction = completed.length / 5;
  return Math.round(69 * (1 - fraction));
}

// ---------------------------------------------------------------------------
// Progress ring SVG
// ---------------------------------------------------------------------------

function ProgressRing({ completed }: { completed: number[] }) {
  const offset = ringOffset(completed);
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
      <circle
        cx="14" cy="14" r="11"
        fill="none"
        stroke="rgba(12,35,64,.12)"
        strokeWidth="3"
      />
      <circle
        cx="14" cy="14" r="11"
        fill="none"
        stroke="#C8A45C"
        strokeWidth="3"
        strokeDasharray="69"
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 14 14)"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// 5-segment bar
// ---------------------------------------------------------------------------

function SegmentBar({ completed }: { completed: number[] }) {
  const done = new Set(completed);
  const next = nextStep(completed);
  return (
    <div style={{ display: "flex", gap: "4px" }}>
      {ALL_STEPS.map((s) => {
        let bg: string;
        if (done.has(s)) {
          bg = "#0C2340"; // navy — done
        } else if (s === next) {
          bg = "#C8A45C"; // gold — active
        } else {
          bg = "rgba(12,35,64,.12)"; // hairline — upcoming
        }
        return (
          <div
            key={s}
            style={{
              height: "3px",
              flex: 1,
              borderRadius: "2px",
              background: bg,
            }}
          />
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Active draft card
// ---------------------------------------------------------------------------

function ActiveDraftCard({ draft, onRemove }: { draft: DraftInfo; onRemove: () => void }) {
  const [hovered, setHovered] = React.useState(false);
  const stepCount = draft.completed_steps.length;
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: "relative",
        border: "1px solid #C8A45C",
        borderRadius: "10px",
        padding: "12px",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        background: "rgba(200,164,92,.06)",
      }}
    >
      {/* Delete button — appears on hover */}
      {hovered && (
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          aria-label={`Delete draft: ${draft.label}`}
          style={{
            position: "absolute",
            top: "6px",
            right: "6px",
            width: "18px",
            height: "18px",
            borderRadius: "50%",
            border: "none",
            background: "rgba(12,35,64,0.15)",
            color: "#0C2340",
            fontSize: "11px",
            lineHeight: "18px",
            textAlign: "center",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 0,
          }}
        >
          ×
        </button>
      )}

      {/* Ring + label */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
        <div style={{ flexShrink: 0 }}>
          <ProgressRing completed={draft.completed_steps} />
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              fontFamily: "'Playfair Display', Georgia, serif",
              fontSize: "14px",
              color: "#0C2340",
              lineHeight: 1.3,
              overflowWrap: "anywhere",
            }}
          >
            {draft.label}
          </div>
          <div style={{ fontSize: "11px", color: "#8A97A6" }}>
            {stepCount} of 5 steps
          </div>
        </div>
      </div>

      {/* 5-segment progress bar */}
      <SegmentBar completed={draft.completed_steps} />

      {/* Total line */}
      {draft.total_formatted && (
        <div
          style={{
            fontSize: "12px",
            color: "#5A6B7E",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {draft.total_formatted}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inactive draft chip
// ---------------------------------------------------------------------------

function InactiveDraftChip({
  draft,
  onSetActive,
  onRemove,
}: {
  draft: DraftInfo;
  onSetActive: (id: string) => void;
  onRemove: () => void;
}) {
  const [hovered, setHovered] = React.useState(false);
  const stepCount = draft.completed_steps.length;
  return (
    <div
      style={{ position: "relative" }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <button
        onClick={() => onSetActive(draft.draft_id)}
        style={{
          border: "1px solid rgba(12,35,64,.12)",
          borderRadius: "10px",
          padding: "12px",
          display: "flex",
          alignItems: "center",
          gap: "10px",
          background: "#fff",
          cursor: "pointer",
          width: "100%",
          minWidth: 0,
          textAlign: "left",
        }}
        aria-label={`Switch to draft: ${draft.label}`}
      >
        <div style={{ flexShrink: 0 }}>
          <ProgressRing completed={draft.completed_steps} />
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              fontFamily: "'Playfair Display', Georgia, serif",
              fontSize: "14px",
              color: "#0C2340",
              lineHeight: 1.3,
              overflowWrap: "anywhere",
            }}
          >
            {draft.label}
          </div>
          <div style={{ fontSize: "11px", color: "#8A97A6" }}>
            {stepCount} of 5 steps
          </div>
        </div>
      </button>
      {/* Delete button — appears on hover */}
      {hovered && (
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          aria-label={`Delete draft: ${draft.label}`}
          style={{
            position: "absolute",
            top: "6px",
            right: "6px",
            width: "18px",
            height: "18px",
            borderRadius: "50%",
            border: "none",
            background: "rgba(12,35,64,0.15)",
            color: "#0C2340",
            fontSize: "11px",
            lineHeight: "18px",
            textAlign: "center",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 0,
          }}
        >
          ×
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DraftRail
// ---------------------------------------------------------------------------

export function DraftRail({ drafts = [], activeDraftId, onSetActive, onRemoveDraft }: DraftRailProps) {
  const activeDraft = drafts.find((d) => d.draft_id === activeDraftId) ?? null;
  const otherDrafts = drafts.filter((d) => d.draft_id !== activeDraftId);

  return (
    <aside
      className="draft-rail"
      style={{
        width: "240px",
        flexShrink: 0,
        overflow: "hidden",
        background: "#fff",
        borderLeft: "1px solid rgba(12,35,64,.10)",
        padding: "20px 16px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div
          style={{
            fontSize: "11px",
            fontWeight: 600,
            letterSpacing: ".14em",
            textTransform: "uppercase",
            color: "#8A97A6",
          }}
        >
          Drafts
        </div>
      </div>

      {/* Scrollable card list — grows to fill available aside height, scrolls internally */}
      <div
        style={{
          flex: "1 1 auto",
          minHeight: 0,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        {/* Active draft or empty state */}
        {activeDraft ? (
          <ActiveDraftCard draft={activeDraft} onRemove={() => onRemoveDraft(activeDraft.draft_id)} />
        ) : (
          <div
            style={{
              border: "1px dashed rgba(12,35,64,.2)",
              borderRadius: "10px",
              padding: "14px",
              textAlign: "center",
              fontSize: "12px",
              color: "#8A97A6",
            }}
          >
            Pinned drafts appear here as you plan.
          </div>
        )}

        {/* Other draft chips */}
        {otherDrafts.map((draft) => (
          <InactiveDraftChip
            key={draft.draft_id}
            draft={draft}
            onSetActive={onSetActive}
            onRemove={() => onRemoveDraft(draft.draft_id)}
          />
        ))}
      </div>

      {/* Footer note — pinned outside scroll area so always visible */}
      {drafts.length > 0 && (
        <div
          style={{
            flexShrink: 0,
            fontSize: "11px",
            color: "#8A97A6",
            lineHeight: 1.5,
            borderTop: "1px solid rgba(12,35,64,.08)",
            paddingTop: "12px",
          }}
        >
          Drafts are held for 7 days. Nothing is charged until you confirm a deposit.
        </div>
      )}
    </aside>
  );
}
