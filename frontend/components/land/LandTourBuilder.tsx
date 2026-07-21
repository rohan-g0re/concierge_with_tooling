"use client";
import React, { useState } from "react";
import type { ComponentDescriptor } from "@/lib/api";
import type { RegistryHandlers } from "@/lib/componentRegistry";
import { ErrorState } from "@/components/states/ErrorState";

interface LandOption {
  id: string;
  name: string;
  price_formatted: string;
  conflicts_with: string[];
  conflict_reason: string;
  selected: boolean;
}

interface LandDay {
  day: number;
  label: string;
  options: LandOption[];
}

interface PlanItem {
  day: number;
  label: string;
  option_id: string;
  name: string;
}

export function LandTourBuilder({
  descriptor,
  handlers,
}: {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}) {
  const draftId = descriptor.draft_id as string | undefined;
  const initialDays = (descriptor.days as LandDay[]) ?? [];
  const initialPlan = (descriptor.plan as PlanItem[]) ?? [];

  // selectedIds: set of currently selected option_ids
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    () => new Set(initialPlan.map((p) => p.option_id))
  );
  const [days, setDays] = useState<LandDay[]>(initialDays);
  const [plan, setPlan] = useState<PlanItem[]>(initialPlan);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // Retryable network failure — holds the ids that failed to persist so
  // "Try again" can re-invoke the same set_land_days call (frame 1o).
  const [netErrorIds, setNetErrorIds] = useState<Set<string> | null>(null);

  const getConflictingIds = (ids: Set<string>): Set<string> => {
    const conflicting = new Set<string>();
    for (const day of days) {
      for (const opt of day.options) {
        if (ids.has(opt.id)) {
          for (const cid of opt.conflicts_with) {
            conflicting.add(cid);
          }
        }
      }
    }
    return conflicting;
  };

  const getConflictReason = (optId: string): string => {
    for (const day of days) {
      for (const opt of day.options) {
        if (selectedIds.has(opt.id) && opt.conflicts_with.includes(optId)) {
          return opt.conflict_reason || `Conflicts with ${opt.name}`;
        }
      }
    }
    return "Conflicts with a selected option";
  };

  const handleOptionClick = async (clickedOpt: LandOption, dayNum: number) => {
    if (!draftId) return;

    const conflicting = getConflictingIds(selectedIds);
    if (conflicting.has(clickedOpt.id)) {
      // Unselectable — no-op
      return;
    }

    if (selectedIds.has(clickedOpt.id)) {
      // Deselect: remove from selection
      const newIds = new Set(selectedIds);
      newIds.delete(clickedOpt.id);
      await postSelection(newIds);
    } else {
      // Select: replace any selection on same day, add new
      const newIds = new Set(selectedIds);
      // Remove any option currently selected on this day
      for (const opt of days.find((d) => d.day === dayNum)?.options ?? []) {
        newIds.delete(opt.id);
      }
      newIds.add(clickedOpt.id);
      await postSelection(newIds);
    }
  };

  const postSelection = async (newIds: Set<string>) => {
    if (!draftId) return;
    setLoading(true);
    setError(null);
    setNetErrorIds(null);

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/action/set_land_days`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: typeof window !== "undefined"
              ? sessionStorage.getItem("compass_session_id") ?? ""
              : "",
            args: {
              draft_id: draftId,
              option_ids: Array.from(newIds),
            },
          }),
        }
      );
      if (!res.ok) {
        setNetErrorIds(newIds);
        return;
      }
      const data = await res.json();

      if (data.result?.error) {
        const errCode = data.result.error;
        if (errCode === "conflict") {
          setError(data.result.reason || "These options conflict. Please choose one.");
        } else {
          setError(data.result.message || "Unable to update land options.");
        }
      } else {
        // Notify parent so DraftRail (total + steps) refreshes
        handlers?.onSetLandDays?.(data);
        // Update local state from server response
        setSelectedIds(newIds);

        // Update days to reflect new selected state
        setDays((prevDays) =>
          prevDays.map((day) => ({
            ...day,
            options: day.options.map((opt) => ({
              ...opt,
              selected: newIds.has(opt.id),
            })),
          }))
        );

        // Rebuild plan
        const newPlan: PlanItem[] = [];
        for (const day of days) {
          for (const opt of day.options) {
            if (newIds.has(opt.id)) {
              newPlan.push({ day: day.day, label: day.label, option_id: opt.id, name: opt.name });
            }
          }
        }
        setPlan(newPlan);
      }
    } catch {
      setNetErrorIds(newIds);
    } finally {
      setLoading(false);
    }
  };

  const conflictingIds = getConflictingIds(selectedIds);

  return (
    <div className="mt-3" style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Header */}
      <div style={{ fontSize: "13px", color: "#5A6B7E" }}>
        Choose one option per day for your land journey.
      </div>

      {/* Day columns */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${Math.max(days.length, 1)}, 1fr)`,
          gap: "14px",
        }}
      >
        {days.map((day) => (
          <div key={day.day} style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {/* Day label */}
            <div
              style={{
                fontSize: "11.5px",
                fontWeight: 700,
                letterSpacing: ".1em",
                textTransform: "uppercase",
                color: "#8A97A6",
                marginBottom: "4px",
              }}
            >
              {day.label}
            </div>

            {/* Options */}
            {day.options.map((opt) => {
              const isSelected = selectedIds.has(opt.id);
              const isConflicting = conflictingIds.has(opt.id);
              const conflictReason = isConflicting ? getConflictReason(opt.id) : "";

              return (
                <div
                  key={opt.id}
                  className="tile-selectable"
                  role="button"
                  tabIndex={isConflicting ? -1 : 0}
                  aria-disabled={isConflicting}
                  aria-pressed={isSelected}
                  aria-label={`${opt.name}, ${opt.price_formatted}${isSelected ? ", selected" : ""}${isConflicting ? `, unavailable: ${conflictReason}` : ""}`}
                  title={isConflicting ? conflictReason : ""}
                  onClick={() => !isConflicting && handleOptionClick(opt, day.day)}
                  onKeyDown={(e) => {
                    if (!isConflicting && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      handleOptionClick(opt, day.day);
                    }
                  }}
                  style={{
                    position: "relative",
                    background: "#fff",
                    border: isSelected ? "2px solid #0C2340" : "1px solid rgba(12,35,64,.14)",
                    borderRadius: "10px",
                    padding: "12px 14px",
                    boxShadow: isSelected
                      ? "0 0 0 3px rgba(200,164,92,.22)"
                      : "none",
                    opacity: isConflicting ? 0.45 : 1,
                    cursor: isConflicting ? "not-allowed" : loading ? "wait" : "pointer",
                    transition: "opacity 0.15s, box-shadow 0.15s",
                  }}
                >
                  <div
                    style={{
                      fontSize: "13.5px",
                      fontWeight: 600,
                      color: "#0C2340",
                      marginBottom: "4px",
                    }}
                  >
                    {opt.name}
                  </div>
                  <div style={{ fontSize: "12px", color: "#5A6B7E" }}>
                    {opt.price_formatted}
                  </div>
                  {isSelected && (
                    <div
                      style={{
                        marginTop: "6px",
                        fontSize: "11px",
                        fontWeight: 700,
                        color: "#B08F44",
                        letterSpacing: ".05em",
                      }}
                    >
                      Selected
                    </div>
                  )}

                  {/* Conflict tooltip (shown on hover via title attr above, but also render inline label) */}
                  {isConflicting && (
                    <div
                      style={{
                        position: "absolute",
                        top: "-38px",
                        left: "50%",
                        transform: "translateX(-50%)",
                        background: "#0C2340",
                        color: "#fff",
                        fontSize: "11px",
                        padding: "5px 10px",
                        borderRadius: "6px",
                        whiteSpace: "nowrap",
                        pointerEvents: "none",
                        zIndex: 5,
                        display: "none", // shown via CSS :hover on parent
                      }}
                      className="conflict-tooltip"
                    >
                      {conflictReason}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Inline (business) error — e.g. conflict */}
      {error && (
        <p style={{ fontSize: "12.5px", color: "#c0392b" }}>{error}</p>
      )}

      {/* Retryable network failure — re-invoke the same selection call */}
      {netErrorIds && (
        <ErrorState onRetry={() => postSelection(netErrorIds)} />
      )}

      {/* Mini timeline: "Your plan so far" */}
      <div
        style={{
          background: "#fff",
          borderRadius: "10px",
          padding: "16px 20px",
          border: "1px solid rgba(12,35,64,.10)",
        }}
      >
        <div
          style={{
            fontSize: "11.5px",
            fontWeight: 700,
            letterSpacing: ".1em",
            textTransform: "uppercase",
            color: "#8A97A6",
            marginBottom: "12px",
          }}
        >
          Your plan so far
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0" }}>
          {days.map((day, idx) => {
            const selectedOpt = day.options.find((o) => selectedIds.has(o.id));
            const isLast = idx === days.length - 1;

            return (
              <React.Fragment key={day.day}>
                {/* Dot + label */}
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1 }}>
                  <div
                    style={{
                      width: "10px",
                      height: "10px",
                      borderRadius: "50%",
                      background: selectedOpt ? "#C8A45C" : "transparent",
                      border: selectedOpt ? "2px solid #C8A45C" : "2px dashed #B0BEC5",
                      marginBottom: "6px",
                      flexShrink: 0,
                    }}
                  />
                  <div
                    style={{
                      fontSize: "10.5px",
                      color: selectedOpt ? "#0C2340" : "#B0BEC5",
                      textAlign: "center",
                      fontWeight: selectedOpt ? 600 : 400,
                      lineHeight: 1.3,
                    }}
                  >
                    {selectedOpt ? selectedOpt.name : `Day ${day.day} open`}
                  </div>
                </div>
                {/* Connector line */}
                {!isLast && (
                  <div
                    style={{
                      height: "1px",
                      width: "20px",
                      background: "#DCE4EC",
                      flexShrink: 0,
                      marginBottom: "16px",
                    }}
                  />
                )}
              </React.Fragment>
            );
          })}
          {/* Embark endpoint */}
          <div
            style={{
              height: "1px",
              width: "20px",
              background: "#DCE4EC",
              flexShrink: 0,
              marginBottom: "16px",
            }}
          />
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <div
              style={{
                width: "10px",
                height: "10px",
                borderRadius: "50%",
                background: "#0C2340",
                marginBottom: "6px",
              }}
            />
            <div style={{ fontSize: "10.5px", color: "#0C2340", fontWeight: 600, textAlign: "center", lineHeight: 1.3 }}>
              Embark
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
