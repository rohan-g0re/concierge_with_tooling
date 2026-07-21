/**
 * Compass — MessageStream
 * Renders the scrollable list of chat messages.
 * User bubbles right/navy, assistant bubbles white with streaming text
 * and rendered components beneath via registry.
 */
"use client";

import React, { useEffect, useRef } from "react";
import { renderComponent } from "@/lib/componentRegistry";
import { Preamble } from "./Preamble";
import type { TranscriptMessage } from "@/lib/session";

/** Descriptor types that are trace-only — surfaced in ReasoningPanel, never rendered as chat components. */
const TRACE_ONLY_TYPES = new Set(["system_event"]);

interface MessageStreamProps {
  messages: TranscriptMessage[];
  onChipClick?: (chip: string) => void;
}

export function MessageStream({ messages, onChipClick }: MessageStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) return null;

  return (
    <div className="flex flex-col gap-4 px-4 py-4">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
        >
          <div className={`max-w-[80%] ${msg.role === "user" ? "flex flex-col items-end" : "flex flex-col items-start"}`}>
            {/* Bubble */}
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
                <Preamble
                  text={msg.text}
                  streaming={msg.streaming}
                  components={msg.components ?? []}
                />
              ) : (
                <>
                  {msg.text}
                  {/* Streaming cursor */}
                  {msg.streaming && (
                    <span
                      className="inline-block w-0.5 h-3.5 ml-0.5 align-middle animate-pulse"
                      style={{ background: "#C8A45C" }}
                    />
                  )}
                </>
              )}
            </div>

            {/* Visible components rendered beneath assistant bubble
                (trace-only descriptors like system_event go to ReasoningPanel, not here) */}
            {msg.role === "assistant" && msg.components && msg.components.length > 0 && (
              <div className="w-full mt-1">
                {msg.components
                  .filter((c) => !TRACE_ONLY_TYPES.has(c.type))
                  .map((c, i) => renderComponent(c, i))}
              </div>
            )}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
