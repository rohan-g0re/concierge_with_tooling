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
import { FareTiles } from "@/components/fare/FareTiles";
import { StateroomPicker } from "@/components/stateroom/StateroomPicker";
import { DiningTiles } from "@/components/dining/DiningTiles";
import { LandTourBuilder } from "@/components/land/LandTourBuilder";
import { ComparisonView } from "@/components/compare/ComparisonView";
import { ErrorState } from "@/components/states/ErrorState";
import { DraftDisambiguation } from "@/components/drafts/DraftDisambiguation";

// ---------------------------------------------------------------------------
// Handler types — injected by page.tsx when rendering
// ---------------------------------------------------------------------------

export type RegistryHandlers = {
  /** Called when the user taps Select on a cruise card. */
  onSelect?: (cruiseId: string, sailingId?: string) => void;
  /** Called when the user taps See Itinerary on a cruise card. */
  onOpenItinerary?: (card: unknown) => void;
  /** Called when the user taps a fare tile. */
  onSetFare?: (args: { draft_id: string; package: string }) => Promise<void>;
  /** Called when the user taps a stateroom category or changes location. Returns server result with total_formatted. */
  onSetStateroom?: (args: { draft_id: string; category: string; location: string }) => Promise<{ total_formatted?: string } | undefined>;
  /** Called after a successful dining reservation to merge refreshed components. */
  onReserveDining?: (data: unknown) => Promise<void>;
  /** Called after successful land day selection to merge refreshed components. */
  onSetLandDays?: (data: unknown) => Promise<void>;
  /** Called when the user clicks "Continue with this" in comparison view to set active draft. */
  onSetActiveDraft?: (draftId: string) => Promise<void>;
  /** Called when the user taps "Try again" on an errored component — re-invokes the failed call. */
  onRetry?: () => void;
  /** Called when the user taps a widen chip on an empty card_row (e.g. "Widen by a week"). */
  onChipClick?: (value: string) => void;
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
      onSelect={handlers?.onSelect ?? ((_cruiseId: string, _sailingId?: string) => {})}
      onOpenItinerary={handlers?.onOpenItinerary as CardRowProps["onOpenItinerary"] ?? (() => {})}
      onChipClick={handlers?.onChipClick}
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
// Comparison (real component — P12)
// ---------------------------------------------------------------------------

function Comparison({
  descriptor,
  handlers,
}: {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}) {
  return <ComparisonView descriptor={descriptor} handlers={handlers} />;
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
// ActiveDraftSet — subtle confirmation chip shown after a draft switch
// ---------------------------------------------------------------------------

function ActiveDraftSet({ descriptor }: { descriptor: ComponentDescriptor }) {
  const label = descriptor.label as string | undefined;
  if (!label) return null;
  return (
    <span
      className="mt-2 inline-flex items-center gap-1.5 px-3 py-1 rounded-full font-sans text-xs"
      style={{ background: "rgba(200,164,92,0.1)" }}
    >
      <span style={{ color: "#C8A45C" }}>✓</span>
      <span style={{ color: "#22344B" }}>Switched to {label}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// FareTiles wrapper
// ---------------------------------------------------------------------------

function FareTilesWrapper({
  descriptor,
  handlers,
}: {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}) {
  return <FareTiles descriptor={descriptor} handlers={handlers} />;
}

// ---------------------------------------------------------------------------
// StateroomPicker wrapper
// ---------------------------------------------------------------------------

function StateroomPickerWrapper({
  descriptor,
  handlers,
}: {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}) {
  return <StateroomPicker descriptor={descriptor} handlers={handlers} />;
}

// ---------------------------------------------------------------------------
// DiningTiles wrapper
// ---------------------------------------------------------------------------

function DiningTilesWrapper({
  descriptor,
  handlers,
}: {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}) {
  return <DiningTiles descriptor={descriptor} handlers={handlers} />;
}

// ---------------------------------------------------------------------------
// LandTourBuilder wrapper
// ---------------------------------------------------------------------------

function LandTourBuilderWrapper({
  descriptor,
  handlers,
}: {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}) {
  return <LandTourBuilder descriptor={descriptor} handlers={handlers} />;
}

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

/**
 * Map known backend error codes to polite, on-brand refusal copy so raw codes
 * (e.g. "draft_not_found", "draft_cap") never surface as bare text in chat.
 */
const ERROR_COPY: Record<string, string> = {
  draft_cap:
    "You already have five drafts — delete one before starting another.",
  compare_cap:
    "I can compare up to three drafts at a time. Pick up to three and I'll line them up side by side.",
  draft_not_found:
    "I couldn't find that draft — here's what you have saved.",
  no_drafts:
    "You'll need at least two drafts to compare. Create a second one and I'll set them side by side.",
  cruise_not_found:
    "I couldn't find that sailing just now. Let's try another option together.",
};

function politeErrorCopy(descriptor: ComponentDescriptor): string {
  const code = descriptor.code ?? descriptor.error;
  if (typeof code === "string" && ERROR_COPY[code]) {
    return ERROR_COPY[code];
  }
  // Fall back to a server-provided message only if it doesn't look like a raw
  // error code (no spaces, snake_case) — otherwise use a generic polite line.
  const message = descriptor.message;
  if (typeof message === "string" && message.trim() && /\s/.test(message.trim())) {
    return message;
  }
  return "Something went sideways on my end — let's try that again.";
}

function ErrorComponent({
  descriptor,
  handlers,
}: {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}) {
  // If a retry handler is available (e.g. re-run the last chat turn), surface a
  // "Try again" affordance so an errored component is never a dead-end (frame 1o).
  const onRetry = handlers?.onRetry;
  return <ErrorState message={politeErrorCopy(descriptor)} onRetry={onRetry} />;
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
  fare_tiles: FareTilesWrapper,
  stateroom_picker: StateroomPickerWrapper,
  dining_tiles: DiningTilesWrapper,
  land_builder: LandTourBuilderWrapper,
  draft_disambiguation: DraftDisambiguation,
  active_draft_set: ActiveDraftSet,
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
