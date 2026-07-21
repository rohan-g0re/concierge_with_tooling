/**
 * StepTracker — in-chat 5-step horizontal booking progress tracker.
 *
 * P9: real component replacing tracker_update stub in componentRegistry.
 * Design: frame 1e (Booking Step Tracker — in-chat + micro).
 */
"use client";

import React from "react";
import type { ComponentDescriptor } from "@/lib/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STEP_NAMES: Record<number, string> = {
  1: "Sailing",
  2: "Fare",
  3: "Stateroom",
  4: "Add-ons",
  5: "Review",
};

const ALL_STEPS = [1, 2, 3, 4, 5];

// ---------------------------------------------------------------------------
// Checkmark SVG
// ---------------------------------------------------------------------------

function CheckIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 12 12" aria-hidden="true">
      <path
        d="M2.5 6.5 5 9 9.5 3.5"
        fill="none"
        stroke="#0C2340"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Step node
// ---------------------------------------------------------------------------

type StepState = "done" | "active" | "upcoming";

function StepNode({ step, state }: { step: number; state: StepState }) {
  const label = STEP_NAMES[step];

  let circleStyle: React.CSSProperties;
  let labelStyle: React.CSSProperties;
  let content: React.ReactNode;

  if (state === "done") {
    circleStyle = {
      width: "32px",
      height: "32px",
      borderRadius: "50%",
      border: "2px solid #C8A45C",
      background: "#fff",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    };
    labelStyle = { fontSize: "12.5px", fontWeight: 600, color: "#0C2340" };
    content = <CheckIcon />;
  } else if (state === "active") {
    circleStyle = {
      width: "32px",
      height: "32px",
      borderRadius: "50%",
      background: "#C8A45C",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    };
    labelStyle = { fontSize: "12.5px", fontWeight: 700, color: "#0C2340" };
    content = (
      <span style={{ fontSize: "13px", fontWeight: 700, color: "#0C2340" }}>
        {step}
      </span>
    );
  } else {
    circleStyle = {
      width: "32px",
      height: "32px",
      borderRadius: "50%",
      border: "1px solid rgba(12,35,64,.3)",
      background: "#fff",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    };
    labelStyle = { fontSize: "12.5px", color: "#5A6B7E" };
    content = (
      <span style={{ fontSize: "13px", color: "#5A6B7E" }}>{step}</span>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "7px",
        width: "110px",
      }}
    >
      <div style={circleStyle}>{content}</div>
      <div style={labelStyle}>{label}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Connector line between steps
// ---------------------------------------------------------------------------

function Connector({ filled }: { filled: boolean }) {
  return (
    <div
      style={{
        flex: 1,
        height: "1px",
        background: filled ? "#C8A45C" : "rgba(12,35,64,.15)",
        marginBottom: "22px",
      }}
    />
  );
}

// ---------------------------------------------------------------------------
// StepTracker
// ---------------------------------------------------------------------------

export function StepTracker({ descriptor }: { descriptor: ComponentDescriptor }) {
  const completed = new Set(
    (descriptor.completed_steps as number[] | undefined) ?? []
  );

  // Determine active step (checkout_entry or computed)
  let activeStep =
    (descriptor.checkout_entry as number | undefined) ??
    ALL_STEPS.find((s) => !completed.has(s)) ??
    6;

  function getState(step: number): StepState {
    if (completed.has(step)) return "done";
    if (step === activeStep) return "active";
    return "upcoming";
  }

  return (
    <div
      style={{
        marginTop: "12px",
        background: "#fff",
        border: "1px solid rgba(12,35,64,.10)",
        borderRadius: "12px",
        padding: "22px 26px",
        boxShadow: "0 2px 8px rgba(12,35,64,.05)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center" }}>
        {ALL_STEPS.map((step, idx) => (
          <React.Fragment key={step}>
            <StepNode step={step} state={getState(step)} />
            {idx < ALL_STEPS.length - 1 && (
              <Connector filled={completed.has(step)} />
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
