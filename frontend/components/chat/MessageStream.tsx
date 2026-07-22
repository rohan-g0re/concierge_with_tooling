/**
 * Compass — MessageStream
 * Renders the scrollable list of chat messages.
 * User bubbles right/navy, assistant bubbles white with streaming text
 * and rendered components beneath via registry.
 */
"use client";

import React, { useEffect, useRef } from "react";
import { renderComponent } from "@/lib/componentRegistry";
import type { RegistryHandlers } from "@/lib/componentRegistry";
import { Preamble } from "./Preamble";
import { Feedback } from "./Feedback";
import { SkeletonCardRow } from "@/components/states/Skeleton";
import type { TranscriptMessage } from "@/lib/session";

/** Descriptor types that are trace-only — surfaced in ReasoningPanel, never rendered as chat components. */
const TRACE_ONLY_TYPES = new Set(["system_event"]);

interface MessageStreamProps {
  messages: TranscriptMessage[];
  onChipClick?: (chip: string) => void;
  /** Optional callback handlers forwarded to registry components (e.g. CardRow). */
  registryHandlers?: RegistryHandlers;
  /** Ambient session context merged into each message's feedback state_snapshot. */
  feedbackContext?: {
    session_id?: string;
    active_draft_id?: string | null;
    active_draft_completed_steps?: number[];
    draft_count?: number;
  };
}

export function MessageStream({ messages, onChipClick, registryHandlers, feedbackContext }: MessageStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) return null;

  return (
    <div className="flex flex-col gap-4 px-4 py-4 w-full">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex flex-col w-full min-w-0 ${msg.role === "user" ? "items-end" : "items-start"}`}
        >
          {/* Bubble — capped at 80% width */}
          <div className={`min-w-0 max-w-[80%] ${msg.role === "user" ? "flex flex-col items-end" : "flex flex-col items-start"}`}>
            <div
              className={`rounded-2xl px-4 py-2.5 font-sans text-sm leading-relaxed ${
                msg.role === "user"
                  ? "rounded-br-sm"
                  : "rounded-bl-sm shadow-sm"
              }`}
              style={
                msg.role === "user"
                  ? { background: "#0C2340", color: "#fff" }
                  : { background: "#fff", color: "#22344B" }
              }
            >
              {msg.role === "assistant" ? (
                <>
                  <Preamble
                    text={msg.text}
                    streaming={msg.streaming}
                    components={msg.components ?? []}
                  />
                  {/* Streaming cursor */}
                  {msg.streaming && (
                    <span
                      className="inline-block w-0.5 h-3.5 ml-0.5 align-middle animate-pulse"
                      style={{ background: "#C8A45C" }}
                    />
                  )}
                </>
              ) : (
                msg.text
              )}
            </div>
            {msg.role === "assistant" && !msg.streaming && (
              <Feedback
                messageId={msg.id}
                stateSnapshot={{
                  ...feedbackContext,
                  last_component_types: (msg.components ?? [])
                    .map((c) => c.type)
                    .filter((t) => !TRACE_ONLY_TYPES.has(t)),
                }}
              />
            )}
          </div>

          {/* While a chat turn is in flight (streaming, before components arrive),
              show a skeleton card row so the panel is never blank (frame 1o). */}
          {msg.role === "assistant" &&
            msg.streaming &&
            (!msg.components || msg.components.length === 0) && (
              <div className="w-full min-w-0 mt-1">
                <SkeletonCardRow />
              </div>
            )}

          {/* Visible components rendered beneath assistant bubble at full column width
              (trace-only descriptors like system_event go to ReasoningPanel, not here) */}
          {msg.role === "assistant" && msg.components && msg.components.length > 0 && (
            <div className="w-full min-w-0 mt-1">
              {msg.components
                .filter((c) => !TRACE_ONLY_TYPES.has(c.type))
                .map((c, i) => renderComponent(c, i, registryHandlers))}
            </div>
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
