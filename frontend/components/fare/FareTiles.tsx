"use client";
import React, { useState } from "react";
import type { ComponentDescriptor } from "@/lib/api";
import type { RegistryHandlers } from "@/lib/componentRegistry";

// Checkmark SVG component
function Check({ color }: { color: string }) {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" style={{ flexShrink: 0 }}>
      <path d="M2.5 6.5 5 9 9.5 3.5" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function FareTiles({
  descriptor,
  handlers,
}: {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}) {
  const draftId = descriptor.draft_id as string | undefined;
  const options = (descriptor.options as any[]) ?? [];
  const [selected, setSelected] = useState<string | null>(
    (descriptor.current_package as string | null) ?? null
  );

  const handleSelect = async (optionId: string) => {
    setSelected(optionId);
    if (handlers?.onSetFare && draftId) {
      await handlers.onSetFare({ draft_id: draftId, package: optionId });
    }
  };

  return (
    <div className="mt-3" style={{ display: "flex", gap: "18px" }}>
      {options.map((opt) => {
        const isSignature = opt.id === "have_it_all";
        const isSelected = selected === opt.id;
        const borderStyle = isSelected
          ? "2px solid #0C2340"
          : isSignature && selected === null
          ? "2px solid #0C2340"
          : "1px solid rgba(12,35,64,.14)";
        const shadowStyle =
          isSelected || (isSignature && selected === null)
            ? "0 0 0 4px rgba(200,164,92,.25), 0 10px 30px rgba(12,35,64,.10)"
            : "none";

        return (
          <div
            key={opt.id}
            className="tile-selectable"
            role="button"
            tabIndex={0}
            aria-label={`${opt.name} fare package${isSelected ? ", selected" : ""}`}
            aria-pressed={isSelected}
            onClick={() => handleSelect(opt.id)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleSelect(opt.id);
              }
            }}
            style={{
              flex: 1,
              position: "relative",
              background: "#fff",
              border: borderStyle,
              borderRadius: "12px",
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              gap: "14px",
              boxShadow: shadowStyle,
              cursor: "pointer",
            }}
          >
            {/* Badge */}
            {opt.badge && (
              <div
                style={{
                  position: "absolute",
                  top: "-11px",
                  left: "24px",
                  background: "#C8A45C",
                  color: "#0C2340",
                  fontSize: "10.5px",
                  fontWeight: 700,
                  letterSpacing: ".1em",
                  textTransform: "uppercase",
                  padding: "4px 12px",
                  borderRadius: "4px",
                }}
              >
                {opt.badge}
              </div>
            )}

            {/* Header */}
            <div>
              <div
                style={{
                  fontSize: "10.5px",
                  fontWeight: 600,
                  letterSpacing: ".14em",
                  textTransform: "uppercase",
                  color: isSignature ? "#B08F44" : "#8A97A6",
                }}
              >
                Fare Package
              </div>
              <div
                className="font-display"
                style={{ fontSize: "22px", color: "#0C2340", marginTop: "4px" }}
              >
                {opt.name}
              </div>
              {opt.delta_per_day ? (
                <div style={{ fontSize: "14px", marginTop: "2px", fontVariantNumeric: "tabular-nums" }}>
                  <span style={{ fontWeight: 700, color: "#0C2340" }}>
                    {opt.delta_per_day.split(" ")[0]} {opt.delta_per_day.split(" ")[1]}
                  </span>{" "}
                  <span style={{ color: "#5A6B7E" }}>per person, per day</span>
                </div>
              ) : (
                <div style={{ fontSize: "14px", color: "#5A6B7E", marginTop: "2px" }}>
                  {opt.label}
                </div>
              )}
            </div>

            {/* Amenities */}
            <div style={{ display: "flex", flexDirection: "column", gap: "9px", fontSize: "14px" }}>
              {(opt.amenities ?? []).map((a: { text: string; included: boolean }, i: number) => (
                <div key={i} style={{ display: "flex", gap: "9px", alignItems: "center", color: a.included ? "#22344B" : "#8A97A6" }}>
                  {a.included ? (
                    <Check color={isSignature ? "#B08F44" : "#0C2340"} />
                  ) : (
                    <span style={{ width: "12px", textAlign: "center" }}>–</span>
                  )}
                  {a.text}
                </div>
              ))}
            </div>

            {/* Footer note */}
            <div
              style={{
                marginTop: "auto",
                borderTop: "1px solid rgba(12,35,64,.08)",
                paddingTop: "12px",
                fontSize: "11.5px",
                color: "#8A97A6",
              }}
            >
              {opt.deposit_note || opt.sharing_note || ""}
            </div>

            {/* CTA button */}
            <div
              style={{
                background: isSignature ? "#C8A45C" : "transparent",
                border: isSignature ? "none" : "1px solid rgba(12,35,64,.3)",
                color: "#0C2340",
                fontSize: "13.5px",
                fontWeight: isSignature ? 700 : 600,
                padding: "10px 0",
                borderRadius: "8px",
                textAlign: "center",
              }}
            >
              {isSelected ? (isSignature ? "Selected" : "Kept") : opt.cta}
            </div>
          </div>
        );
      })}
    </div>
  );
}
