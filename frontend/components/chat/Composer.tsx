/**
 * Compass — Composer
 * Rounded pill input with mic placeholder and gold send button.
 * Matches frame 1a design: 760px max, white bg, subtle border.
 */
"use client";

import React, { useState, useRef, useCallback } from "react";
import { MicToggle } from "./MicToggle";

interface ComposerProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
  sessionId: string;
}

export function Composer({ onSend, disabled, placeholder = "Ask about cruises, itineraries, dining…", sessionId }: ComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const msg = value.trim();
    if (!msg || disabled) return;
    onSend(msg);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, disabled, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    // Auto-resize textarea
    const ta = e.target;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`;
  };

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div className="px-4 pb-4 pt-2">
      <div
        className="flex items-end gap-2 rounded-full px-3 py-2 w-full max-w-3xl mx-auto"
        style={{
          background: "#fff",
          border: "1px solid rgba(12,35,64,0.15)",
          boxShadow: "0 1px 4px rgba(12,35,64,0.06)",
        }}
      >
        {/* Mic button */}
        <MicToggle sessionId={sessionId} />

        {/* Input */}
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          className="flex-1 resize-none bg-transparent border-none outline-none font-sans text-sm py-1 leading-relaxed"
          style={{
            color: "#22344B",
            maxHeight: "120px",
          }}
        />

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Send message"
          className="flex-none w-8 h-8 rounded-full flex items-center justify-center transition-all duration-150"
          style={{
            background: canSend ? "#C8A45C" : "rgba(12,35,64,0.08)",
            cursor: canSend ? "pointer" : "default",
          }}
        >
          {/* Send arrow icon */}
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            aria-hidden
          >
            <path
              d="M1 7h12M7 1l6 6-6 6"
              stroke={canSend ? "#fff" : "#8A97A6"}
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
