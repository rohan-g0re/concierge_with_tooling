/**
 * Compass component registry — maps descriptor.type → React component.
 *
 * P7: real stubs that render structured data legibly in brand style.
 * P8-P12: full visual components replace these stubs.
 */
"use client";

import React from "react";
import type { ComponentDescriptor } from "./api";

// ---------------------------------------------------------------------------
// Card Row (search_cruises result)
// ---------------------------------------------------------------------------

function CardRow({ descriptor }: { descriptor: ComponentDescriptor }) {
  const cards = (descriptor.cards as Record<string, unknown>[] | undefined) ?? [];
  const filters = (descriptor.filters as Record<string, unknown> | undefined) ?? {};

  return (
    <div className="mt-3 w-full">
      {Object.keys(filters).length > 0 && (
        <p className="text-xs font-sans mb-2" style={{ color: "#8A97A6" }}>
          Filters:{" "}
          {Object.entries(filters)
            .map(([k, v]) => `${k}: ${v}`)
            .join(" · ")}
        </p>
      )}
      <div className="flex gap-3 overflow-x-auto pb-2">
        {cards.map((card, i) => (
          <div
            key={(card.cruise_id as string) ?? i}
            className="flex-none w-64 rounded-xl overflow-hidden border"
            style={{ borderColor: "rgba(12,35,64,0.12)", background: "#fff" }}
          >
            {/* Image placeholder */}
            <div
              className="w-full h-32"
              style={{ background: "linear-gradient(135deg, #0C2340 0%, #4E7E86 100%)" }}
            />
            <div className="p-3">
              <p className="font-display font-semibold text-sm" style={{ color: "#0C2340" }}>
                {(card.name as string) ?? "Cruise"}
              </p>
              <p className="font-sans text-xs mt-0.5" style={{ color: "#5A6B7E" }}>
                {card.nights as number} nights · {card.embark_port as string}
              </p>
              <p className="font-sans text-xs mt-0.5" style={{ color: "#5A6B7E" }}>
                {card.ship as string}
              </p>
              <p className="font-sans text-sm mt-2" style={{ color: "#0C2340" }}>
                {card.fare_was ? (
                  <span
                    className="font-normal text-xs mr-1.5 line-through"
                    style={{ color: "#8A97A6" }}
                  >
                    {card.fare_was as string}
                  </span>
                ) : null}
                <span className="font-semibold" style={{ color: "#0C2340" }}>
                  {(card.fare_now as string) ?? "—"}
                </span>{" "}
                <span className="font-normal text-xs" style={{ color: "#8A97A6" }}>
                  /person
                </span>
              </p>
              <div className="flex gap-2 mt-2">
                <button
                  className="flex-1 py-1.5 rounded-full text-xs font-sans font-semibold transition-colors"
                  style={{ background: "#C8A45C", color: "#fff" }}
                >
                  Select
                </button>
                <button
                  className="flex-1 py-1.5 rounded-full text-xs font-sans border transition-colors"
                  style={{ borderColor: "#0C2340", color: "#0C2340" }}
                >
                  Itinerary
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Itinerary
// ---------------------------------------------------------------------------

function Itinerary({ descriptor }: { descriptor: ComponentDescriptor }) {
  const days = (descriptor.days as Array<{ day: number; port: string; description?: string }> | undefined) ?? [];
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
        {days.map((d) => (
          <div key={d.day} className="flex gap-3 items-baseline">
            <span
              className="font-sans text-xs font-semibold w-10 flex-none"
              style={{ color: "#C8A45C" }}
            >
              Day {d.day}
            </span>
            <span className="font-sans text-sm" style={{ color: "#22344B" }}>
              {d.port}
            </span>
            {d.description && (
              <span className="font-sans text-xs" style={{ color: "#8A97A6" }}>
                {d.description}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tracker Update (draft booking progress)
// ---------------------------------------------------------------------------

function TrackerUpdate({ descriptor }: { descriptor: ComponentDescriptor }) {
  const draftId = descriptor.draft_id as string | undefined;
  const steps = (descriptor.completed_steps as string[] | undefined) ?? [];
  const total = descriptor.total_formatted as string | undefined;

  return (
    <div
      className="mt-3 rounded-xl p-4 border"
      style={{ background: "#fff", borderColor: "rgba(200,164,92,0.4)" }}
    >
      <div className="flex items-center justify-between mb-2">
        <p className="font-sans text-xs font-semibold" style={{ color: "#0C2340" }}>
          Draft {draftId}
        </p>
        {total && (
          <p className="font-display text-sm font-semibold" style={{ color: "#C8A45C" }}>
            {total}
          </p>
        )}
      </div>
      <div className="flex gap-1">
        {["select", "fare", "stateroom", "dining", "land"].map((step) => (
          <div
            key={step}
            className="flex-1 h-1 rounded-full"
            style={{
              background: steps.includes(step) ? "#0C2340" : "rgba(12,35,64,0.12)",
            }}
          />
        ))}
      </div>
      {steps.length > 0 && (
        <p className="font-sans text-xs mt-2" style={{ color: "#5A6B7E" }}>
          Completed: {steps.join(", ")}
        </p>
      )}
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

const REGISTRY: Record<string, React.ComponentType<{ descriptor: ComponentDescriptor }>> = {
  card_row: CardRow,
  itinerary: Itinerary,
  tracker_update: TrackerUpdate,
  comparison: Comparison,
  handoff: Handoff,
  error: ErrorComponent,
};

/**
 * Render a component descriptor using the registry.
 * Unknown types render a small debug pill so nothing is silently swallowed.
 */
export function renderComponent(descriptor: ComponentDescriptor, key: string | number): React.ReactNode {
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
  return <Component key={key} descriptor={descriptor} />;
}
