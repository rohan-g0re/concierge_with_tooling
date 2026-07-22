/**
 * DraftDisambiguation — renders a list of candidate drafts from a
 * `draft_disambiguation` descriptor so the user can tap to switch.
 *
 * U8: R17 — tappable candidate cards (name, sailing dates, nights,
 * draft-held price). Tap → handlers.onSetActiveDraft(draft_id).
 * Active candidate shown with a "current" badge.
 */
"use client";

import React, { useState } from "react";
import type { ComponentDescriptor } from "@/lib/api";
import type { RegistryHandlers } from "@/lib/componentRegistry";

// ---------------------------------------------------------------------------
// Types matching backend draft_disambiguation descriptor
// ---------------------------------------------------------------------------

interface DisambiguationCandidate {
  draft_id: string;
  label: string;
  region?: string | null;
  departure_date?: string | null;
  return_date?: string | null;
  nights?: number | null;
  total_formatted?: string | null;
}

// ---------------------------------------------------------------------------
// Date helpers (re-implemented here to stay self-contained)
// ---------------------------------------------------------------------------

function formatShortDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const [, mm, dd] = iso.split("-");
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const month = months[parseInt(mm, 10) - 1];
  const day = parseInt(dd, 10);
  return `${month} ${day}`;
}

function sailingLine(candidate: DisambiguationCandidate): string | null {
  const dep = formatShortDate(candidate.departure_date);
  const ret = formatShortDate(candidate.return_date);
  if (!dep && !ret) return null;
  const datePart = dep && ret ? `${dep} – ${ret}` : dep ?? ret ?? "";
  const nightsPart = candidate.nights != null ? ` · ${candidate.nights} nights` : "";
  return `${datePart}${nightsPart}`;
}

// ---------------------------------------------------------------------------
// Region accent colours (mirrors DraftRail palette)
// ---------------------------------------------------------------------------

function regionAccent(region: string | null | undefined): string {
  if (!region) return "#8A97A6";
  const r = region.toLowerCase();
  if (r.includes("caribbean") || r.includes("bahama")) return "#0077B6";
  if (r.includes("alaska")) return "#4A7C6F";
  if (r.includes("europe") || r.includes("mediterr")) return "#7B5EA7";
  if (r.includes("hawaii")) return "#C05746";
  return "#8A97A6";
}

// ---------------------------------------------------------------------------
// Single candidate card
// ---------------------------------------------------------------------------

function CandidateCard({
  candidate,
  isCurrent,
  isSelected,
  onTap,
}: {
  candidate: DisambiguationCandidate;
  isCurrent: boolean;
  isSelected: boolean;
  onTap: () => void;
}) {
  const [hovered, setHovered] = React.useState(false);
  const accent = regionAccent(candidate.region);
  const sailing = sailingLine(candidate);

  // Border: gold ring on selected, accent on current, subtle on rest
  let borderStyle: string;
  if (isSelected) {
    borderStyle = "2px solid #C8A45C";
  } else if (isCurrent) {
    borderStyle = `1.5px solid ${accent}`;
  } else {
    borderStyle = "1px solid rgba(12,35,64,.12)";
  }

  return (
    <button
      onClick={onTap}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-label={`Switch to draft: ${candidate.label}`}
      aria-pressed={isCurrent}
      style={{
        display: "block",
        width: "100%",
        textAlign: "left",
        border: borderStyle,
        borderRadius: "10px",
        padding: "12px 14px",
        background: isSelected
          ? "rgba(200,164,92,.08)"
          : hovered
          ? "rgba(12,35,64,.03)"
          : "#fff",
        cursor: "pointer",
        transition: "border-color 0.15s, background 0.15s",
        position: "relative",
      }}
    >
      {/* Region accent bar */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: "10px",
          bottom: "10px",
          width: "3px",
          borderRadius: "2px",
          background: accent,
          opacity: 0.7,
        }}
      />

      {/* Header row: label + "current" badge */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: "8px",
          paddingLeft: "10px",
        }}
      >
        <div
          style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            fontSize: "13px",
            color: "#0C2340",
            lineHeight: 1.3,
            overflowWrap: "anywhere",
            flex: 1,
          }}
        >
          {candidate.label}
        </div>
        {isCurrent && (
          <span
            style={{
              fontSize: "9px",
              fontWeight: 700,
              letterSpacing: ".1em",
              textTransform: "uppercase",
              color: "#C8A45C",
              border: "1px solid #C8A45C",
              borderRadius: "4px",
              padding: "1px 5px",
              flexShrink: 0,
              lineHeight: "14px",
            }}
          >
            current
          </span>
        )}
      </div>

      {/* Sailing dates line */}
      {sailing && (
        <div
          style={{
            fontSize: "11px",
            color: "#5A6B7E",
            marginTop: "4px",
            paddingLeft: "10px",
          }}
        >
          {sailing}
        </div>
      )}

      {/* Price */}
      {candidate.total_formatted && (
        <div
          style={{
            fontSize: "12px",
            color: "#0C2340",
            fontWeight: 600,
            marginTop: "4px",
            paddingLeft: "10px",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {candidate.total_formatted}
        </div>
      )}

      {/* Region tag */}
      {candidate.region && (
        <div
          style={{
            fontSize: "10px",
            color: accent,
            marginTop: "4px",
            paddingLeft: "10px",
            fontWeight: 600,
            letterSpacing: ".05em",
            textTransform: "uppercase",
          }}
        >
          {candidate.region}
        </div>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// DraftDisambiguation
// ---------------------------------------------------------------------------

export function DraftDisambiguation({
  descriptor,
  handlers,
}: {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}) {
  const candidates = (descriptor.candidates as DisambiguationCandidate[] | undefined) ?? [];
  const activeDraftId = descriptor.active_draft_id as string | undefined;
  const [selectedId, setSelectedId] = useState<string | null>(null);

  async function handleTap(draftId: string) {
    setSelectedId(draftId);
    await handlers?.onSetActiveDraft?.(draftId);
  }

  if (candidates.length === 0) return null;

  return (
    <div
      style={{
        marginTop: "12px",
        border: "1px solid rgba(12,35,64,.12)",
        borderRadius: "12px",
        padding: "14px",
        background: "#fff",
      }}
    >
      {/* Header */}
      <p
        style={{
          fontFamily: "'Playfair Display', Georgia, serif",
          fontSize: "13px",
          color: "#0C2340",
          marginBottom: "10px",
          fontWeight: 600,
        }}
      >
        Which cruise did you mean?
      </p>

      {/* Candidate cards */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {candidates.map((c) => (
          <CandidateCard
            key={c.draft_id}
            candidate={c}
            isCurrent={c.draft_id === activeDraftId}
            isSelected={selectedId === c.draft_id}
            onTap={() => handleTap(c.draft_id)}
          />
        ))}
      </div>
    </div>
  );
}
