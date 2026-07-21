/**
 * Compass — Preamble
 * Wrapper for assistant message text with optional reasoning panel.
 */
"use client";

import React from "react";
import { ReasoningPanel } from "./ReasoningPanel";
import type { ComponentDescriptor } from "@/lib/api";

interface PreambleProps {
  text: string;
  streaming?: boolean;
  components?: ComponentDescriptor[];
}

export function Preamble({ text, streaming, components = [] }: PreambleProps) {
  return (
    <div>
      <p className="font-sans text-sm leading-relaxed" style={{ color: "#22344B" }}>
        {text}
        {streaming && (
          <span
            className="inline-block w-0.5 h-3.5 ml-0.5 align-middle animate-pulse"
            style={{ background: "#C8A45C" }}
          />
        )}
      </p>
      {!streaming && components.length > 0 && (
        <ReasoningPanel components={components} />
      )}
    </div>
  );
}
