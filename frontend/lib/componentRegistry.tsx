/**
 * Compass component registry — maps descriptor.type → React component.
 *
 * P7: real stubs that render structured data legibly in brand style.
 * P8: CardRow replaced with real component; ItineraryPanel opened via handlers.
 * P9-P12: full visual components replace remaining stubs.
 */
"use client";

import React from "react";
import type { ComponentDescriptor } from "./api";
import { CardRow as CardRowComponent } from "@/components/cards/CardRow";
import type { CardRowProps } from "@/components/cards/CardRow";
import { StepTracker } from "@/components/tracker/StepTracker";

// ---------------------------------------------------------------------------
// Handler types — injected by page.tsx when rendering
// ---------------------------------------------------------------------------

export type RegistryHandlers = {
  /** Called when the user taps Select on a cruise card. */
  onSelect?: (cruiseId: string) => void;
  /** Called when the user taps See Itinerary on a cruise card. */
  onOpenItinerary?: (card: unknown) => void;
};

// ---------------------------------------------------------------------------
// Card Row (search_cruises result) — real component (P8)
// ---------------------------------------------------------------------------

function CardRow({
  descriptor,
  handlers,
}: {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}) {
  return (
    <CardRowComponent
      descriptor={descriptor}
      onSelect={handlers?.onSelect ?? (() => {})}
      onOpenItinerary={handlers?.onOpenItinerary as CardRowProps["onOpenItinerary"] ?? (() => {})}
    />
  );
}

// ---------------------------------------------------------------------------
// Itinerary (inline summary — panel opened via onOpenItinerary from CardRow)
// ---------------------------------------------------------------------------

function Itinerary({ descriptor }: { descriptor: ComponentDescriptor }) {
  // When get_itinerary is called directly (e.g. via postAction), render an
  // inline day summary. The full panel is opened via "See Itinerary" on cards.
  const days = (descriptor.days as Array<{ day: string | number; port: string; note?: string }> | undefined) ?? [];
  const cruiseId = descriptor.cruise_id as string | undefined;

  return (
    <div
      className="mt-3 rounded-xl p-4 border"
      style={{ background: "#fff", borderColor: "rgba(12,35,64,0.12)" }}
    >
      {cruiseId && (
        <p className="font-display font-semibold text-sm mb-3" style={{ color: "#0C2340" }}>
          Itinerary · {cruiseId}
        </p>
      )}
      <div className="space-y-1.5">
        {days.map((d, i) => (
          <div key={i} className="flex gap-3 items-baseline">
            <span
              className="font-sans text-xs font-semibold w-10 flex-none"
              style={{ color: "#C8A45C" }}
            >
              {d.day}
            </span>
            <span className="font-sans text-sm" style={{ color: "#22344B" }}>
              {d.port}
            </span>
            {d.note && (
              <span className="font-sans text-xs" style={{ color: "#8A97A6" }}>
                {d.note}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Comparison
// ---------------------------------------------------------------------------

function Comparison({ descriptor }: { descriptor: ComponentDescriptor }) {
  const rows = (descriptor.rows as Array<{ label: string; values: unknown[]; differ?: boolean }> | undefined) ?? [];

  return (
    <div
      className="mt-3 rounded-xl overflow-hidden border"
      style={{ background: "#fff", borderColor: "rgba(12,35,64,0.12)" }}
    >
      <p className="font-display font-semibold text-sm p-4 pb-2" style={{ color: "#0C2340" }}>
        Comparison
      </p>
      <table className="w-full text-sm font-sans">
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              style={{
                background: row.differ ? "rgba(200,164,92,0.06)" : "transparent",
                borderTop: "1px solid rgba(12,35,64,0.08)",
              }}
            >
              <td className="px-4 py-2 font-semibold text-xs" style={{ color: "#5A6B7E", width: "30%" }}>
                {row.label}
              </td>
              {(row.values ?? []).map((v, j) => (
                <td key={j} className="px-4 py-2 text-xs" style={{ color: "#22344B" }}>
                  {String(v ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Handoff
// ---------------------------------------------------------------------------

function Handoff({ descriptor }: { descriptor: ComponentDescriptor }) {
  const url = descriptor.url as string | undefined;

  return (
    <div
      className="mt-3 rounded-xl p-4 border text-center"
      style={{ background: "#fff", borderColor: "rgba(200,164,92,0.4)" }}
    >
      <p className="font-display text-base font-semibold mb-2" style={{ color: "#0C2340" }}>
        Ready to book!
      </p>
      <p className="font-sans text-sm mb-3" style={{ color: "#5A6B7E" }}>
        Your cruise draft is ready for checkout.
      </p>
      {url && (
        <a
          href={url}
          className="inline-block px-6 py-2 rounded-full font-sans font-semibold text-sm"
          style={{ background: "#C8A45C", color: "#fff" }}
        >
          Continue to Checkout
        </a>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

function ErrorComponent({ descriptor }: { descriptor: ComponentDescriptor }) {
  return (
    <div
      className="mt-3 rounded-xl p-3 border"
      style={{ background: "#fff5f5", borderColor: "rgba(200,50,50,0.2)" }}
    >
      <p className="font-sans text-sm" style={{ color: "#c0392b" }}>
        {(descriptor.message as string) ?? "An error occurred."}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

type RegistryEntry = React.ComponentType<{
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}>;

const REGISTRY: Record<string, RegistryEntry> = {
  card_row: CardRow,
  itinerary: Itinerary,
  tracker_update: StepTracker,
  comparison: Comparison,
  handoff: Handoff,
  error: ErrorComponent,
};

/**
 * Render a component descriptor using the registry.
 *
 * @param descriptor - The component descriptor to render
 * @param key        - React key for the element
 * @param handlers   - Optional callback handlers (onSelect, onOpenItinerary)
 *
 * Unknown types render a small debug pill so nothing is silently swallowed.
 */
export function renderComponent(
  descriptor: ComponentDescriptor,
  key: string | number,
  handlers?: RegistryHandlers
): React.ReactNode {
  const Component = REGISTRY[descriptor.type];
  if (!Component) {
    return (
      <div
        key={key}
        className="mt-2 px-3 py-1.5 rounded font-sans text-xs inline-block"
        style={{ background: "rgba(12,35,64,0.06)", color: "#5A6B7E" }}
      >
        [{descriptor.type}]
      </div>
    );
  }
  return <Component key={key} descriptor={descriptor} handlers={handlers} />;
}
