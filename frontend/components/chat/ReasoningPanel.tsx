/**
 * Compass — ReasoningPanel
 * 'View reasoning' toggle → collapsible panel listing tool calls/filters
 * from the last turn. Data comes from the terminal SSE components event.
 */
"use client";

import React, { useState } from "react";
import type { ComponentDescriptor } from "@/lib/api";

interface ReasoningPanelProps {
  components: ComponentDescriptor[];
  chips?: string[];
}

function getReasoningData(components: ComponentDescriptor[]) {
  // Extract tool calls and filters from system_event or card_row descriptors
  const systemEvent = components.find((c) => c.type === "system_event");
  const cardRow = components.find((c) => c.type === "card_row");

  const toolCalls: string[] = [];
  const filters: Record<string, unknown> = {};

  if (systemEvent) {
    const tc = systemEvent.tool_calls;
    if (Array.isArray(tc)) toolCalls.push(...(tc as string[]));
    const f = systemEvent.filters;
    if (f && typeof f === "object") Object.assign(filters, f);
  }

  if (cardRow) {
    if (!toolCalls.includes("search_cruises")) toolCalls.push("search_cruises");
    const f = cardRow.filters;
    if (f && typeof f === "object") Object.assign(filters, f);
  }

  if (components.find((c) => c.type === "itinerary") && !toolCalls.includes("get_itinerary")) {
    toolCalls.push("get_itinerary");
  }
  if (components.find((c) => c.type === "comparison") && !toolCalls.includes("compare_drafts")) {
    toolCalls.push("compare_drafts");
  }

  return { toolCalls, filters };
}

export function ReasoningPanel({ components }: ReasoningPanelProps) {
  const [open, setOpen] = useState(false);
  const { toolCalls, filters } = getReasoningData(components);

  // Only show if there's something to reason about
  if (toolCalls.length === 0 && Object.keys(filters).length === 0) return null;

  return (
    <div className="mt-2">
      {/* Toggle button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 font-sans text-xs transition-colors"
        style={{ color: "#8A97A6" }}
        aria-expanded={open}
      >
        <svg
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden
          style={{
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s",
          }}
        >
          <path
            d="M2 4l4 4 4-4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        View reasoning
      </button>

      {/* Collapsible panel */}
      {open && (
        <div
          className="mt-1.5 rounded-lg px-3 py-2.5 text-xs font-sans"
          style={{
            background: "rgba(255,255,255,0.6)",
            borderLeft: "2px solid rgba(12,35,64,0.12)",
          }}
        >
          {toolCalls.length > 0 && (
            <div className="mb-1.5">
              <span className="font-semibold" style={{ color: "#5A6B7E" }}>
                Tools called:{" "}
              </span>
              <span style={{ color: "#22344B" }}>{toolCalls.join(", ")}</span>
            </div>
          )}
          {Object.keys(filters).length > 0 && (
            <div>
              <span className="font-semibold" style={{ color: "#5A6B7E" }}>
                Active filters:{" "}
              </span>
              <span style={{ color: "#22344B" }}>
                {Object.entries(filters)
                  .map(([k, v]) => `${k}=${v}`)
                  .join(" · ")}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
