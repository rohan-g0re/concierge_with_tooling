/**
 * CardRow — horizontally scrollable cruise result cards (frame 1c).
 *
 * Renders ≤5 cards per search_cruises descriptor shape:
 *   cruise_id, name, ship, nights, embark_port, fare_was, fare_now,
 *   badge, photo, region
 *
 * Props injected by componentRegistry via CardRowWrapper in page.tsx:
 *   descriptor  – the card_row ComponentDescriptor
 *   onSelect    – called with cruise_id when user clicks Select
 *   onOpenItinerary – called with card object when user clicks See Itinerary
 */
"use client";

import React, { useState } from "react";
import type { ComponentDescriptor } from "@/lib/api";
import { EmptyState } from "@/components/states/Empty";

// ---------------------------------------------------------------------------
// Ship icon SVG (inline, from design doc)
// ---------------------------------------------------------------------------
function ShipIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" aria-hidden="true">
      <path d="M1.5 9.5 h11 l-2 3 h-7 Z" fill="#8A97A6" />
      <path
        d="M3.5 9.5 V6.5 h7 v3 M5.5 6.5 V4.5 h3 v2"
        fill="none"
        stroke="#8A97A6"
        strokeWidth="1.2"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Individual cruise card
// ---------------------------------------------------------------------------

interface CardData {
  cruise_id: string;
  name: string;
  ship: string;
  nights: number;
  embark_port: string;
  fare_was: string;
  fare_now: string;
  badge: string | null;
  photo: string;
  region?: string;
  // Sailing fields (Unit 6 — R6, R12)
  departure_date?: string;
  return_date?: string;
  sailing_id?: string;
  alt_sailings?: Array<{ sailing_id: string; departure_date: string; return_date: string }>;
  [key: string]: unknown;
}

interface CruiseCardProps {
  card: CardData;
  onSelect: (cruiseId: string, sailingId?: string) => void;
  onOpenItinerary: (card: CardData) => void;
}

function formatShortDate(iso: string): string {
  const [, mm, dd] = iso.split("-");
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${months[parseInt(mm, 10) - 1]} ${parseInt(dd, 10)}`;
}

function CruiseCard({ card, onSelect, onOpenItinerary }: CruiseCardProps) {
  const [imgFailed, setImgFailed] = useState(false);
  const [selectedSailingId, setSelectedSailingId] = useState<string | null>(card.sailing_id ?? null);

  const dur = `${card.nights}-Night`;

  return (
    <div
      style={{
        width: "296px",
        flexShrink: 0,
        background: "#fff",
        border: "1px solid rgba(12,35,64,.10)",
        borderRadius: "12px",
        boxShadow: "0 8px 24px rgba(12,35,64,.08)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* ── Image area ── */}
      <div
        style={{
          position: "relative",
          height: "148px",
          background:
            "repeating-linear-gradient(135deg,#D8E1EA 0 12px,#E4EAF1 12px 24px)",
          flexShrink: 0,
        }}
      >
        {/* Port photo */}
        {card.photo && !imgFailed && (
          <img
            src={card.photo}
            alt={card.name}
            onError={() => setImgFailed(true)}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        )}
        {/* Gradient overlay */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "linear-gradient(180deg,rgba(12,35,64,.08),rgba(12,35,64,.55))",
          }}
        />
        {/* Badge */}
        {card.badge && (
          <div
            style={{
              position: "absolute",
              top: "12px",
              left: "12px",
              background: "#C8A45C",
              color: "#0C2340",
              fontSize: "10.5px",
              fontWeight: 700,
              letterSpacing: ".1em",
              textTransform: "uppercase",
              padding: "5px 10px",
              borderRadius: "4px",
            }}
          >
            {card.badge}
          </div>
        )}
      </div>

      {/* ── Card body ── */}
      <div
        style={{
          padding: "16px 18px 18px",
          display: "flex",
          flexDirection: "column",
          gap: "6px",
          flex: 1,
        }}
      >
        {/* Duration kicker */}
        <div
          style={{
            fontSize: "10.5px",
            fontWeight: 600,
            letterSpacing: ".14em",
            textTransform: "uppercase",
            color: "#8A97A6",
          }}
        >
          {dur}
        </div>

        {/* Cruise name — Playfair */}
        <div
          style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            fontSize: "19px",
            lineHeight: 1.25,
            color: "#0C2340",
          }}
        >
          {card.name}
        </div>

        {/* Embark port */}
        <div style={{ fontSize: "13px", color: "#5A6B7E" }}>
          {card.embark_port}
        </div>

        {/* Ship with icon */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            fontSize: "13px",
            color: "#5A6B7E",
          }}
        >
          <ShipIcon />
          {card.ship}
        </div>

        {/* Fare row */}
        <div
          style={{
            marginTop: "6px",
            display: "flex",
            alignItems: "baseline",
            gap: "10px",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {card.fare_was && (
            <span style={{ fontSize: "13px", color: "#8A97A6", textDecoration: "line-through" }}>
              {card.fare_was}
            </span>
          )}
          <span style={{ fontSize: "21px", fontWeight: 700, color: "#0C2340" }}>
            {card.fare_now}
          </span>
          <span style={{ fontSize: "12px", color: "#8A97A6" }}>/person</span>
        </div>

        {/* Tax line */}
        <div style={{ fontSize: "11px", color: "#8A97A6" }}>
          Includes Taxes, Fees &amp; Port Expenses
        </div>

        {/* Sailing block */}
        {(() => {
          if (!card.departure_date) return null;
          const allSailings = card.sailing_id && card.departure_date && card.return_date
            ? [
                { sailing_id: card.sailing_id, departure_date: card.departure_date, return_date: card.return_date },
                ...(card.alt_sailings ?? []),
              ]
            : [];
          if (allSailings.length === 0) {
            // Edge case: dates present but no sailing_id
            return (
              <div style={{ fontSize: "12px", color: "#5A6B7E", marginTop: "2px" }}>
                Departs {formatShortDate(card.departure_date!)} · Returns {card.return_date ? formatShortDate(card.return_date) : ""}
              </div>
            );
          }
          if (allSailings.length === 1) {
            const dep = formatShortDate(allSailings[0].departure_date);
            const ret = formatShortDate(allSailings[0].return_date);
            return (
              <div style={{ fontSize: "12px", color: "#5A6B7E", marginTop: "2px" }}>
                Departs {dep} · Returns {ret}
              </div>
            );
          }
          // Multiple sailings — show compact select
          return (
            <div style={{ marginTop: "4px" }}>
              <select
                value={selectedSailingId ?? card.sailing_id}
                onChange={(e) => setSelectedSailingId(e.target.value)}
                style={{
                  fontSize: "12px",
                  color: "#5A6B7E",
                  background: "none",
                  border: "1px solid rgba(12,35,64,.15)",
                  borderRadius: "4px",
                  padding: "3px 6px",
                  cursor: "pointer",
                }}
              >
                {allSailings.map((s) => (
                  <option key={s.sailing_id} value={s.sailing_id}>
                    {formatShortDate(s.departure_date)} – {formatShortDate(s.return_date)}
                  </option>
                ))}
              </select>
            </div>
          );
        })()}

        {/* Action row */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "14px",
            marginTop: "10px",
          }}
        >
          {/* Select button */}
          <button
            onClick={() => onSelect(card.cruise_id, selectedSailingId ?? undefined)}
            style={{
              background: "#C8A45C",
              color: "#0C2340",
              fontSize: "13px",
              fontWeight: 700,
              padding: "9px 22px",
              borderRadius: "8px",
              border: "none",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "#B08F44";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "#C8A45C";
            }}
          >
            Select
          </button>

          {/* See Itinerary link */}
          <button
            onClick={() => onOpenItinerary(card)}
            style={{
              background: "none",
              border: "none",
              padding: 0,
              fontSize: "13px",
              fontWeight: 600,
              color: "#0C2340",
              borderBottom: "1px solid rgba(12,35,64,.25)",
              cursor: "pointer",
              lineHeight: 1.4,
            }}
          >
            See Itinerary
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CardRow — exported component
// ---------------------------------------------------------------------------

export interface CardRowProps {
  descriptor: ComponentDescriptor;
  onSelect: (cruiseId: string, sailingId?: string) => void;
  onOpenItinerary: (card: CardData) => void;
  /** Widen-chip taps flow through the existing chip-click path (sends as a message). */
  onChipClick?: (value: string) => void;
}

/** Widen chips shown on an empty search — phrased so they re-run search when sent. */
const WIDEN_CHIPS = [
  { label: "Widen by a week", value: "Widen the date range by a week" },
  { label: "Try July instead", value: "Try July instead" },
];

// ---------------------------------------------------------------------------
// Internal helpers for sections rendering
// ---------------------------------------------------------------------------

interface Section {
  label: string | null;
  cards: CardData[];
}

function SectionScroller({
  cards,
  onSelect,
  onOpenItinerary,
}: {
  cards: CardData[];
  onSelect: (cruiseId: string, sailingId?: string) => void;
  onOpenItinerary: (card: CardData) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: "16px",
        overflowX: "auto",
        paddingBottom: "4px",
        scrollbarWidth: "none",
      }}
    >
      {cards.map((card, i) => (
        <CruiseCard
          key={card.cruise_id ?? i}
          card={card}
          onSelect={onSelect}
          onOpenItinerary={onOpenItinerary}
        />
      ))}
    </div>
  );
}

export function CardRow({ descriptor, onSelect, onOpenItinerary, onChipClick }: CardRowProps) {
  const sections = descriptor.sections as Section[] | undefined;
  const filters = (descriptor.filters as Record<string, unknown> | undefined) ?? {};

  // ── Sections mode ───────────────────────────────────────────────────────
  if (sections && sections.length > 0) {
    // Check if ALL sections are empty (true zero-match with no near-misses)
    const totalCards = sections.reduce((n, s) => n + s.cards.length, 0);
    if (totalCards === 0) {
      return (
        <EmptyState
          message="No sailings match those dates."
          chips={WIDEN_CHIPS}
          onChipClick={onChipClick}
        />
      );
    }

    return (
      <div style={{ marginTop: "12px", width: "100%", minWidth: 0 }}>
        {/* Active filters summary */}
        {Object.keys(filters).length > 0 && (
          <p
            style={{
              fontSize: "11px",
              color: "#8A97A6",
              marginBottom: "10px",
              fontFamily: "var(--font-source-sans), system-ui, sans-serif",
            }}
          >
            {Object.entries(filters)
              .map(([k, v]) => `${k}: ${v}`)
              .join(" · ")}
          </p>
        )}

        {sections.map((section, si) => {
          if (section.cards.length === 0) return null;
          return (
            <div key={si} style={{ marginBottom: si < sections.length - 1 ? "20px" : 0 }}>
              {/* Section label (kicker + hairline) — only for non-null labels */}
              {section.label && (
                <>
                  <div
                    style={{
                      fontSize: "10px",
                      fontWeight: 700,
                      letterSpacing: ".13em",
                      textTransform: "uppercase",
                      color: "#8A97A6",
                      marginBottom: "8px",
                    }}
                  >
                    {section.label}
                  </div>
                  <div
                    style={{
                      height: "1px",
                      background: "rgba(12,35,64,.08)",
                      marginBottom: "12px",
                    }}
                  />
                </>
              )}
              <SectionScroller
                cards={section.cards}
                onSelect={onSelect}
                onOpenItinerary={onOpenItinerary}
              />
            </div>
          );
        })}
      </div>
    );
  }

  // ── Flat mode (back-compat) ──────────────────────────────────────────────
  const cards = ((descriptor.cards as CardData[] | undefined) ?? []).slice(0, 5);

  if (cards.length === 0) {
    return (
      <EmptyState
        message="No sailings match those dates."
        chips={WIDEN_CHIPS}
        onChipClick={onChipClick}
      />
    );
  }

  return (
    <div style={{ marginTop: "12px", width: "100%", minWidth: 0 }}>
      {/* Active filters summary */}
      {Object.keys(filters).length > 0 && (
        <p
          style={{
            fontSize: "11px",
            color: "#8A97A6",
            marginBottom: "10px",
            fontFamily: "var(--font-source-sans), system-ui, sans-serif",
          }}
        >
          {Object.entries(filters)
            .map(([k, v]) => `${k}: ${v}`)
            .join(" · ")}
        </p>
      )}

      {/* Scrollable card row */}
      <div
        style={{
          display: "flex",
          gap: "16px",
          overflowX: "auto",
          paddingBottom: "4px",
          scrollbarWidth: "none",
        }}
      >
        {cards.map((card, i) => (
          <CruiseCard
            key={card.cruise_id ?? i}
            card={card}
            onSelect={onSelect}
            onOpenItinerary={onOpenItinerary}
          />
        ))}
      </div>
    </div>
  );
}
