"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { getSessionId } from "@/lib/session";
import { postAction, getStepOptions, type ComponentDescriptor } from "@/lib/api";
import { renderComponent, type RegistryHandlers } from "@/lib/componentRegistry";
import { ErrorState } from "@/components/states/ErrorState";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Steps that support real inline editing on the checkout page. */
const EDITABLE_STEPS = new Set([2, 3, 4]);

const FARE_DISPLAY: Record<string, string> = {
  good_to_go: "Standard Fare",
  have_it_all: "The Signature Collection",
};

const STEP_LABELS: Record<number, string> = {
  1: "Sailing",
  2: "Fare Package",
  3: "Stateroom",
  4: "Add-ons",
  5: "Review",
};

interface DraftSummary {
  draft_id: string;
  label: string;
  completed_steps: number[];
  total_formatted: string | null;
  fare_package: string;
  deposit_formatted: string | null;
  balance_formatted: string | null;
}

function checkoutEntry(completedSteps: number[]): number {
  const done = new Set(completedSteps);
  for (let s = 1; s <= 5; s++) {
    if (!done.has(s)) return s;
  }
  return 6;
}

function StepIndicator({ completedSteps, entryStep }: { completedSteps: number[]; entryStep: number }) {
  const done = new Set(completedSteps);
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 0, justifyContent: "center" }}>
      {[1, 2, 3, 4, 5].map((step, idx) => {
        const isDone = done.has(step);
        const isActive = step === entryStep;
        return (
          <React.Fragment key={step}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 600,
                  fontSize: 14,
                  background: isDone ? "#0C2340" : isActive ? "#C8A45C" : "rgba(12,35,64,.10)",
                  color: isDone || isActive ? "#fff" : "#8A97A6",
                  border: isActive ? "2px solid #C8A45C" : "none",
                }}
              >
                {isDone ? "✓" : step}
              </div>
              <div style={{ fontSize: 11, color: isActive ? "#C8A45C" : isDone ? "#0C2340" : "#8A97A6", fontWeight: isActive ? 600 : 400, textAlign: "center", maxWidth: 64 }}>
                {STEP_LABELS[step]}
              </div>
            </div>
            {idx < 4 && (
              <div style={{ height: 3, flex: 1, marginTop: 16, background: isDone ? "#C8A45C" : "rgba(12,35,64,.10)" }} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

export default function CheckoutPage() {
  const params = useParams();
  const draftId = params?.draft_id as string;

  const [state, setState] = useState<"loading" | "session_missing" | "not_found" | "loaded">("loading");
  const [draft, setDraft] = useState<DraftSummary | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [bookingRef] = useState(() => `MRD-${String(Math.floor(Math.random() * 900000) + 100000)}`);
  const [editingStep, setEditingStep] = useState<number | null>(null);

  // Inline-edit panel state: descriptors fetched for the step being edited.
  const [editComponents, setEditComponents] = useState<ComponentDescriptor[]>([]);
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const searchParams = useSearchParams();
  const urlSessionId = searchParams?.get("session");
  // Prefer URL-carried session_id (cross-tab checkout link) over tab-local storage.
  // Also write it back into sessionStorage so in-tab subsequent calls keep working.
  const sessionId = (() => {
    const stored = getSessionId();
    if (urlSessionId && urlSessionId !== stored) {
      if (typeof window !== "undefined") {
        sessionStorage.setItem("compass_session_id", urlSessionId);
      }
      return urlSessionId;
    }
    return stored;
  })();

  /** Refetch /session and update this draft's summary in place (stay on page). */
  const refreshDraft = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/session/${sessionId}`);
      const data = await res.json();
      const drafts = (data.drafts ?? []) as DraftSummary[];
      const found = drafts.find((d) => d.draft_id === draftId);
      if (found) setDraft(found);
    } catch {
      // keep prior summary on transient failure
    }
  }, [sessionId, draftId]);

  useEffect(() => {
    if (!sessionId || sessionId === "ssr-placeholder") {
      setState("session_missing");
      return;
    }
    fetch(`${API_BASE}/session/${sessionId}`)
      .then((r) => r.json())
      .then((data) => {
        const drafts = (data.drafts ?? []) as DraftSummary[];
        const found = drafts.find((d) => d.draft_id === draftId);
        if (!found) {
          setState("not_found");
        } else {
          setDraft(found);
          setState("loaded");
        }
      })
      .catch(() => setState("session_missing"));
  }, [draftId, sessionId]);

  /** Fetch a step's option descriptors (retryable — powers ErrorState "Try again"). */
  const loadStepOptions = useCallback(
    async (step: number) => {
      if (!EDITABLE_STEPS.has(step)) return;
      setEditError(null);
      setEditLoading(true);
      try {
        const data = await getStepOptions(sessionId, draftId, step);
        setEditComponents(data.components ?? []);
      } catch {
        setEditError("That didn't go through.");
      } finally {
        setEditLoading(false);
      }
    },
    [sessionId, draftId]
  );

  /** Open/close the inline editor for a step; fetch its option descriptors. */
  const toggleEdit = useCallback(
    async (step: number) => {
      if (editingStep === step) {
        setEditingStep(null);
        setEditComponents([]);
        setEditError(null);
        return;
      }
      setEditingStep(step);
      setEditComponents([]);
      setEditError(null);
      await loadStepOptions(step);
    },
    [editingStep, loadStepOptions]
  );

  // Handlers wired to the real /action endpoints, scoped to this draft.
  // After any successful edit, refresh the draft summary (total/steps) in place.
  const editHandlers: RegistryHandlers = {
    onSetFare: async (args) => {
      await postAction("set_fare", sessionId, args as Record<string, unknown>);
      await refreshDraft();
    },
    onSetStateroom: async (args) => {
      const resp = await postAction("set_stateroom", sessionId, args as Record<string, unknown>);
      await refreshDraft();
      const result = (resp.result ?? {}) as { total_formatted?: string };
      return { total_formatted: result.total_formatted };
    },
    onReserveDining: async () => {
      // DiningTiles posts to /action/reserve_dining itself; just refresh summary.
      await refreshDraft();
    },
    onSetLandDays: async () => {
      // LandTourBuilder posts to /action/set_land_days itself; just refresh summary.
      await refreshDraft();
    },
  };

  const entryStep = draft ? checkoutEntry(draft.completed_steps) : 1;

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "#E9ECEF" }}>
      {/* Top bar */}
      <header style={{ background: "#0C2340", padding: "16px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2 }}>
          <span style={{ fontFamily: "'Playfair Display', Georgia, serif", color: "#C8A45C", fontSize: "1.05rem", letterSpacing: "0.2em", textTransform: "uppercase", fontWeight: 600 }}>
            MERIDIAN LINE
          </span>
          <span style={{ color: "rgba(255,255,255,0.55)", fontSize: "0.65rem", letterSpacing: "0.18em", textTransform: "uppercase" }}>
            COMPASS · CRUISE CONCIERGE
          </span>
        </div>
        <a
          href="/"
          style={{ color: "#C8A45C", fontSize: 14, textDecoration: "none", border: "1px solid #C8A45C", borderRadius: 20, padding: "6px 16px" }}
        >
          Return to concierge
        </a>
      </header>

      {/* Content */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", padding: "40px 24px" }}>
        <div style={{ width: "100%", maxWidth: 800 }}>

          {state === "loading" && (
            <div style={{ textAlign: "center", color: "#5A6B7E", padding: "60px 0" }}>
              Loading your draft…
            </div>
          )}

          {state === "session_missing" && (
            <div style={{ background: "#fff", borderRadius: 12, padding: 32, textAlign: "center" }}>
              <p style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 20, color: "#0C2340", marginBottom: 12 }}>
                No session found
              </p>
              <p style={{ color: "#5A6B7E", marginBottom: 24 }}>
                We weren&apos;t able to locate your session. Please return to the concierge to continue planning.
              </p>
              <a href="/" style={{ color: "#C8A45C", textDecoration: "underline" }}>Return to concierge</a>
            </div>
          )}

          {state === "not_found" && (
            <div style={{ background: "#fff", borderRadius: 12, padding: 32, textAlign: "center" }}>
              <p style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 20, color: "#0C2340", marginBottom: 12 }}>
                Draft not found
              </p>
              <p style={{ color: "#5A6B7E", marginBottom: 24 }}>
                We couldn&apos;t find that draft in your session. It may have expired or been removed.
              </p>
              <a href="/" style={{ color: "#C8A45C", textDecoration: "underline" }}>Return to concierge</a>
            </div>
          )}

          {state === "loaded" && draft && (
            <>
              {/* Draft header */}
              <div style={{ background: "#fff", borderRadius: 12, padding: 24, marginBottom: 24, boxShadow: "0 1px 4px rgba(12,35,64,.08)" }}>
                <h1 style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 24, color: "#0C2340", margin: "0 0 8px 0" }}>
                  {draft.label}
                </h1>
                <p style={{ color: "#5A6B7E", margin: "0 0 4px 0", fontSize: 14 }}>
                  {FARE_DISPLAY[draft.fare_package] ?? draft.fare_package}
                </p>
                {draft.total_formatted && (
                  <p style={{ color: "#0C2340", fontWeight: 700, fontSize: 22, margin: "12px 0 0 0", fontVariantNumeric: "tabular-nums" }}>
                    {draft.total_formatted}
                  </p>
                )}
              </div>

              {/* Step indicator */}
              <div style={{ background: "#fff", borderRadius: 12, padding: "24px 32px", marginBottom: 24, boxShadow: "0 1px 4px rgba(12,35,64,.08)" }}>
                <StepIndicator completedSteps={draft.completed_steps} entryStep={entryStep} />
                {entryStep <= 5 && (
                  <p style={{ textAlign: "center", marginTop: 16, color: "#5A6B7E", fontSize: 14 }}>
                    Entering at Step {entryStep}: <strong style={{ color: "#0C2340" }}>{STEP_LABELS[entryStep]}</strong>
                  </p>
                )}
                {entryStep === 6 && (
                  <p style={{ textAlign: "center", marginTop: 16, color: "#5A6B7E", fontSize: 14 }}>
                    All steps complete — ready to reserve.
                  </p>
                )}
              </div>

              {/* Completed steps — editable inline */}
              {draft.completed_steps.length > 0 && !confirmed && (
                <div style={{ background: "#fff", borderRadius: 12, padding: 24, marginBottom: 24, boxShadow: "0 1px 4px rgba(12,35,64,.08)" }}>
                  <h2 style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 16, color: "#0C2340", margin: "0 0 16px 0" }}>
                    Completed Steps
                  </h2>
                  {[...draft.completed_steps].sort((a, b) => a - b).map((step) => (
                    <div key={step}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid rgba(12,35,64,.08)" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <span style={{ color: "#C8A45C", fontWeight: 700 }}>✓</span>
                          <span style={{ color: "#0C2340", fontSize: 14, fontWeight: 500 }}>
                            Step {step}: {STEP_LABELS[step] ?? `Step ${step}`}
                          </span>
                        </div>
                        <button
                          onClick={() => toggleEdit(step)}
                          style={{
                            background: "transparent",
                            border: "1px solid #C8A45C",
                            borderRadius: 6,
                            color: "#C8A45C",
                            fontSize: 12,
                            fontWeight: 600,
                            padding: "4px 12px",
                            cursor: "pointer",
                          }}
                        >
                          {editingStep === step ? "Close" : "Edit"}
                        </button>
                      </div>
                      {editingStep === step && (
                        <div style={{ background: "rgba(200,164,92,.08)", borderRadius: 8, padding: "14px 16px", margin: "8px 0 4px 0" }}>
                          <p style={{ color: "#5A6B7E", fontSize: 13, margin: "0 0 6px 0" }}>
                            Editing Step {step} — {STEP_LABELS[step] ?? `Step ${step}`}: adjust your selection below. Changes save automatically.
                          </p>

                          {!EDITABLE_STEPS.has(step) && (
                            <p style={{ color: "#8A97A6", fontSize: 13, margin: "8px 0 0 0" }}>
                              This step is set from your sailing selection and isn&apos;t editable here.
                            </p>
                          )}

                          {EDITABLE_STEPS.has(step) && editLoading && (
                            <p style={{ color: "#5A6B7E", fontSize: 13, margin: "8px 0 0 0" }}>
                              Loading your options…
                            </p>
                          )}

                          {EDITABLE_STEPS.has(step) && editError && (
                            <ErrorState
                              message={editError}
                              onRetry={() => loadStepOptions(step)}
                            />
                          )}

                          {EDITABLE_STEPS.has(step) && !editLoading && !editError && (
                            <div style={{ marginTop: 8 }}>
                              {editComponents.length === 0 ? (
                                <p style={{ color: "#8A97A6", fontSize: 13, margin: 0 }}>
                                  No editable options for this step.
                                </p>
                              ) : (
                                editComponents.map((desc, i) =>
                                  renderComponent(desc, `${step}-${i}`, editHandlers)
                                )
                              )}
                            </div>
                          )}

                          <button
                            onClick={() => toggleEdit(step)}
                            style={{
                              background: "#C8A45C",
                              color: "#0C2340",
                              border: "none",
                              borderRadius: 6,
                              padding: "6px 16px",
                              fontSize: 12,
                              fontWeight: 700,
                              cursor: "pointer",
                              marginTop: 12,
                            }}
                          >
                            Done
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Remaining Steps — steps not yet in completed_steps */}
              {!confirmed && (() => {
                const completedSet = new Set(draft.completed_steps);
                const remainingSteps = [1, 2, 3, 4, 5].filter((s) => !completedSet.has(s));
                if (remainingSteps.length === 0) return null;
                return (
                  <div style={{ background: "#fff", borderRadius: 12, padding: 24, marginBottom: 24, boxShadow: "0 1px 4px rgba(12,35,64,.08)" }}>
                    <h2 style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 16, color: "#0C2340", margin: "0 0 16px 0" }}>
                      Remaining Steps
                    </h2>
                    {remainingSteps.map((step) => (
                      <div key={step} id={`remaining-step-${step}`}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid rgba(12,35,64,.08)" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <span style={{ color: "#C8A45C", fontWeight: 700, fontSize: 14 }}>{step}</span>
                            <span style={{ color: "#0C2340", fontSize: 14, fontWeight: 500 }}>
                              Step {step}: {STEP_LABELS[step] ?? `Step ${step}`}
                            </span>
                          </div>
                          {EDITABLE_STEPS.has(step) && (
                            <button
                              onClick={() => toggleEdit(step)}
                              style={{
                                background: "transparent",
                                border: "1px solid #C8A45C",
                                borderRadius: 6,
                                color: "#C8A45C",
                                fontSize: 12,
                                fontWeight: 600,
                                padding: "4px 12px",
                                cursor: "pointer",
                              }}
                            >
                              {editingStep === step ? "Close" : "Open"}
                            </button>
                          )}
                        </div>

                        {/* Step 5 — static review summary panel */}
                        {step === 5 && (
                          <div style={{ background: "rgba(200,164,92,.06)", borderRadius: 8, padding: "14px 16px", margin: "8px 0 4px 0" }}>
                            <p style={{ color: "#5A6B7E", fontSize: 13, margin: "0 0 10px 0" }}>
                              Review your booking details before reserving.
                            </p>
                            <div style={{ fontSize: 13, color: "#0C2340" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                                <span style={{ color: "#5A6B7E" }}>Fare package</span>
                                <span style={{ fontWeight: 600 }}>{FARE_DISPLAY[draft.fare_package] ?? draft.fare_package}</span>
                              </div>
                              {draft.total_formatted && (
                                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                                  <span style={{ color: "#5A6B7E" }}>Total</span>
                                  <span style={{ fontWeight: 700, color: "#0C2340" }}>{draft.total_formatted}</span>
                                </div>
                              )}
                              {draft.deposit_formatted && (
                                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                                  <span style={{ color: "#5A6B7E" }}>Deposit due today (20%)</span>
                                  <span style={{ fontWeight: 600, color: "#C8A45C" }}>{draft.deposit_formatted}</span>
                                </div>
                              )}
                              {draft.balance_formatted && (
                                <div style={{ display: "flex", justifyContent: "space-between" }}>
                                  <span style={{ color: "#5A6B7E" }}>Balance due at sailing</span>
                                  <span style={{ fontWeight: 600 }}>{draft.balance_formatted}</span>
                                </div>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Steps 2/3/4 — inline edit panel (same machinery as completed steps) */}
                        {EDITABLE_STEPS.has(step) && editingStep === step && (
                          <div style={{ background: "rgba(200,164,92,.08)", borderRadius: 8, padding: "14px 16px", margin: "8px 0 4px 0" }}>
                            <p style={{ color: "#5A6B7E", fontSize: 13, margin: "0 0 6px 0" }}>
                              Complete Step {step} — {STEP_LABELS[step] ?? `Step ${step}`}: select your preference below.
                            </p>

                            {editLoading && (
                              <p style={{ color: "#5A6B7E", fontSize: 13, margin: "8px 0 0 0" }}>
                                Loading your options…
                              </p>
                            )}

                            {editError && (
                              <ErrorState
                                message={editError}
                                onRetry={() => loadStepOptions(step)}
                              />
                            )}

                            {!editLoading && !editError && (
                              <div style={{ marginTop: 8 }}>
                                {editComponents.length === 0 ? (
                                  <p style={{ color: "#8A97A6", fontSize: 13, margin: 0 }}>
                                    No options for this step.
                                  </p>
                                ) : (
                                  editComponents.map((desc, i) =>
                                    renderComponent(desc, `remaining-${step}-${i}`, editHandlers)
                                  )
                                )}
                              </div>
                            )}

                            <button
                              onClick={() => toggleEdit(step)}
                              style={{
                                background: "#C8A45C",
                                color: "#0C2340",
                                border: "none",
                                borderRadius: 6,
                                padding: "6px 16px",
                                fontSize: 12,
                                fontWeight: 700,
                                cursor: "pointer",
                                marginTop: 12,
                              }}
                            >
                              Done
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                );
              })()}

              {/* Reserve CTA or confirmation */}
              {confirmed ? (
                <div style={{ background: "#0C2340", borderRadius: 12, padding: 32, textAlign: "center", color: "#fff" }}>
                  <p style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 22, marginBottom: 8 }}>
                    Reserved, and gladly so.
                  </p>
                  <p style={{ color: "rgba(255,255,255,0.7)", fontSize: 14, marginBottom: 12 }}>
                    Booking reference: <span style={{ color: "#C8A45C", fontWeight: 600 }}>{bookingRef}</span>
                  </p>
                  {draft.deposit_formatted && draft.balance_formatted && (
                    <div style={{ display: "inline-block", textAlign: "left", background: "rgba(255,255,255,0.06)", borderRadius: 8, padding: "12px 20px", marginBottom: 12 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 40, marginBottom: 6 }}>
                        <span style={{ color: "rgba(255,255,255,0.6)", fontSize: 13 }}>Deposit due today (20%)</span>
                        <span style={{ color: "#C8A45C", fontWeight: 600, fontSize: 13 }}>{draft.deposit_formatted}</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 40 }}>
                        <span style={{ color: "rgba(255,255,255,0.6)", fontSize: 13 }}>Balance due at sailing</span>
                        <span style={{ color: "rgba(255,255,255,0.85)", fontWeight: 600, fontSize: 13 }}>{draft.balance_formatted}</span>
                      </div>
                    </div>
                  )}
                  <p style={{ color: "rgba(255,255,255,0.45)", fontSize: 11, margin: 0 }}>
                    A deposit confirmation will be sent to your email on file.
                  </p>
                </div>
              ) : (() => {
                const completedSet = new Set(draft.completed_steps);
                const reviewReady = [1, 2, 3, 4].every((s) => completedSet.has(s));
                const nextIncomplete = checkoutEntry(draft.completed_steps);

                if (reviewReady) {
                  // All steps 1–4 complete → show Reserve button
                  return (
                    <div style={{ textAlign: "center" }}>
                      <button
                        onClick={() => setConfirmed(true)}
                        style={{
                          background: "#C8A45C",
                          color: "#0C2340",
                          border: "none",
                          borderRadius: 8,
                          padding: "14px 40px",
                          fontSize: 16,
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        Reserve {draft.total_formatted ? `· ${draft.total_formatted}` : ""}
                      </button>
                      <p style={{ color: "#8A97A6", fontSize: 12, marginTop: 8 }}>
                        Nothing is charged until you confirm your deposit.
                      </p>
                    </div>
                  );
                }

                // Next incomplete step ≤ 4 → "Next: <label>" gated CTA
                return (
                  <div style={{ textAlign: "center" }}>
                    <button
                      onClick={() => {
                        toggleEdit(nextIncomplete);
                        const el = document.getElementById(`remaining-step-${nextIncomplete}`);
                        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
                      }}
                      style={{
                        background: "#0C2340",
                        color: "#fff",
                        border: "none",
                        borderRadius: 8,
                        padding: "14px 40px",
                        fontSize: 16,
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      Next: {STEP_LABELS[nextIncomplete] ?? `Step ${nextIncomplete}`}
                    </button>
                    <p style={{ color: "#8A97A6", fontSize: 12, marginTop: 8 }}>
                      Complete the remaining steps to reserve.
                    </p>
                  </div>
                );
              })()}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
