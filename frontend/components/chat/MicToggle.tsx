/**
 * Compass — MicToggle (P14 voice parity)
 *
 * Mic button in the chat composer. On click:
 *   1. Calls POST /voice/token (backend mints ephemeral token).
 *   2. If unavailable (placeholder key / not configured): shows VoiceOverlay
 *      in unavailable/disabled state with a polite message.
 *   3. If available: starts the WebRTC Realtime session via voiceClient,
 *      shows VoiceOverlay with waveform + transcript.
 *
 * Voice tool calls relay through POST /action/{tool} (R21 parity) so
 * component descriptors and session state match the tap path exactly.
 *
 * Frame 1a pattern: mic toggle in composer, glows while active.
 */
"use client";

import React, { useState, useCallback, useRef } from "react";
import { VoiceOverlay } from "../voice/VoiceOverlay";
import {
  startVoiceSession,
  type VoiceSession,
  type VoiceState,
} from "../../lib/voiceClient";
import type { ComponentDescriptor } from "../../lib/api";

type Props = {
  sessionId: string;
  onActionResult?: (
    tool: string,
    result: unknown,
    components: ComponentDescriptor[],
    chips: string[]
  ) => void;
  onTranscript?: (role: "user" | "assistant", text: string) => void;
};

export function MicToggle({ sessionId, onActionResult, onTranscript }: Props) {
  const [overlayOpen, setOverlayOpen] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState("");
  const [unavailableMessage, setUnavailableMessage] = useState<string | undefined>();
  const sessionRef = useRef<VoiceSession | null>(null);

  const handleMicClick = useCallback(async () => {
    if (overlayOpen) {
      // Already open — stop session
      sessionRef.current?.stop();
      sessionRef.current = null;
      setOverlayOpen(false);
      setVoiceState("idle");
      setTranscript("");
      setUnavailableMessage(undefined);
      return;
    }

    // Open overlay immediately with connecting state
    setOverlayOpen(true);
    setVoiceState("connecting");
    setUnavailableMessage(undefined);
    setTranscript("");

    const session = await startVoiceSession(sessionId, {
      onTranscript: (role, text) => {
        setTranscript(text);
        onTranscript?.(role, text);
      },
      onActionResult: (tool, result, components, chips) => {
        onActionResult?.(tool, result, components as ComponentDescriptor[], chips);
      },
      onStateChange: (state) => {
        setVoiceState(state);
        if (state === "disconnected") {
          sessionRef.current = null;
        }
      },
      onError: (err) => {
        // Check if it's the "unavailable" error from a placeholder key
        const msg = err.message;
        if (msg.includes("not configured") || msg.includes("unavailable")) {
          setUnavailableMessage(msg);
          setVoiceState("disconnected");
        } else {
          setUnavailableMessage("Voice is temporarily unavailable. Please type your request.");
          setVoiceState("disconnected");
        }
      },
    });

    if (session) {
      sessionRef.current = session;
    }
  }, [overlayOpen, sessionId, onActionResult, onTranscript]);

  const handleStop = useCallback(() => {
    sessionRef.current?.stop();
    sessionRef.current = null;
    setOverlayOpen(false);
    setVoiceState("idle");
    setTranscript("");
    setUnavailableMessage(undefined);
  }, []);

  const handleInterrupt = useCallback(() => {
    sessionRef.current?.interrupt();
  }, []);

  const handleSwitchToTyping = useCallback(() => {
    handleStop();
  }, [handleStop]);

  const isActive = overlayOpen && voiceState !== "idle" && voiceState !== "disconnected";

  return (
    <>
      <button
        type="button"
        aria-label={overlayOpen ? "Stop voice input" : "Start voice input"}
        aria-pressed={overlayOpen}
        onClick={handleMicClick}
        className="flex-none w-8 h-8 rounded-full flex items-center justify-center"
        style={{
          background: isActive
            ? "rgba(12,35,64,0.15)"
            : "rgba(12,35,64,0.06)",
          cursor: "pointer",
          transition: "background 0.15s",
          outline: isActive ? "2px solid #0C2340" : "none",
        }}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 14 14"
          fill="none"
          aria-hidden
        >
          <rect
            x="4"
            y="1"
            width="6"
            height="8"
            rx="3"
            stroke={isActive ? "#0C2340" : "#8A97A6"}
            strokeWidth="1.5"
          />
          <path
            d="M2 7c0 2.761 2.239 5 5 5s5-2.239 5-5"
            stroke={isActive ? "#0C2340" : "#8A97A6"}
            strokeWidth="1.5"
            strokeLinecap="round"
          />
          <line
            x1="7"
            y1="12"
            x2="7"
            y2="14"
            stroke={isActive ? "#0C2340" : "#8A97A6"}
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      </button>

      {overlayOpen && (
        <VoiceOverlay
          state={voiceState}
          transcript={transcript}
          unavailableMessage={unavailableMessage}
          onInterrupt={handleInterrupt}
          onStop={handleStop}
          onSwitchToTyping={handleSwitchToTyping}
        />
      )}
    </>
  );
}
