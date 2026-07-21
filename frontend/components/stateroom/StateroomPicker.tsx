"use client";
import React, { useState } from "react";
import type { ComponentDescriptor } from "@/lib/api";
import type { RegistryHandlers } from "@/lib/componentRegistry";

export function StateroomPicker({
  descriptor,
  handlers,
}: {
  descriptor: ComponentDescriptor;
  handlers?: RegistryHandlers;
}) {
  const draftId = descriptor.draft_id as string | undefined;
  const categories = (descriptor.categories as any[]) ?? [];
  const locations = (descriptor.locations as string[]) ?? ["Forward", "Midship", "Aft"];
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedLocation, setSelectedLocation] = useState<string>("Midship");
  const [totalFormatted, setTotalFormatted] = useState<string | null>(
    (descriptor.total_formatted as string | null) ?? null
  );

  const handleCategorySelect = async (category: string) => {
    setSelectedCategory(category);
    if (handlers?.onSetStateroom && draftId) {
      const result = await handlers.onSetStateroom({
        draft_id: draftId,
        category,
        location: selectedLocation,
      });
      if (result?.total_formatted) {
        setTotalFormatted(result.total_formatted);
      }
    }
  };

  const handleLocationSelect = async (location: string) => {
    setSelectedLocation(location);
    if (selectedCategory && handlers?.onSetStateroom && draftId) {
      const result = await handlers.onSetStateroom({
        draft_id: draftId,
        category: selectedCategory,
        location,
      });
      if (result?.total_formatted) {
        setTotalFormatted(result.total_formatted);
      }
    }
  };

  return (
    <div className="mt-3" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Category grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "14px" }}>
        {categories.map((cat: any) => {
          const isSelected = selectedCategory === cat.category;
          return (
            <div
              key={cat.category}
              className="tile-selectable"
              role="button"
              tabIndex={0}
              aria-label={`${cat.category} stateroom${cat.delta_formatted ? `, ${cat.delta_formatted} per person` : ""}${isSelected ? ", selected" : ""}`}
              aria-pressed={isSelected}
              onClick={() => handleCategorySelect(cat.category)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleCategorySelect(cat.category);
                }
              }}
              style={{
                background: "#fff",
                border: isSelected ? "2px solid #0C2340" : "1px solid rgba(12,35,64,.14)",
                borderRadius: "12px",
                overflow: "hidden",
                boxShadow: isSelected
                  ? "0 0 0 4px rgba(200,164,92,.25), 0 10px 30px rgba(12,35,64,.10)"
                  : "none",
                cursor: "pointer",
              }}
            >
              {/* Photo placeholder */}
              <div
                style={{
                  height: "88px",
                  background: "repeating-linear-gradient(135deg,#DCE4EC 0 10px,#E6EBF1 10px 20px)",
                  position: "relative",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    left: "10px",
                    bottom: "8px",
                    fontFamily: "ui-monospace, Menlo, monospace",
                    fontSize: "9.5px",
                    color: "#5A6B7E",
                  }}
                >
                  room photo
                </div>
              </div>

              {/* Content */}
              <div style={{ padding: "12px 14px 14px", display: "flex", flexDirection: "column", gap: "5px" }}>
                <div className="font-display" style={{ fontSize: "16px", color: "#0C2340" }}>
                  {cat.category}
                </div>
                <div style={{ fontSize: "13px", color: "#22344B", fontVariantNumeric: "tabular-nums" }}>
                  {cat.delta_formatted}{" "}
                  <span style={{ color: "#8A97A6", fontSize: "11.5px" }}>per person</span>
                </div>
                {/* Scarcity chip — ONLY when field-backed scarcity present */}
                {cat.scarcity && cat.scarcity.length > 0 && (
                  <div
                    style={{
                      alignSelf: "flex-start",
                      fontSize: "11px",
                      fontWeight: 600,
                      color: "#4E7E86",
                      background: "rgba(78,126,134,.10)",
                      padding: "3px 9px",
                      borderRadius: "999px",
                    }}
                  >
                    {cat.scarcity[0]}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Location segmented control */}
      <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
        <div
          style={{
            fontSize: "12px",
            fontWeight: 600,
            letterSpacing: ".1em",
            textTransform: "uppercase",
            color: "#8A97A6",
          }}
        >
          Location
        </div>
        <div
          style={{
            display: "flex",
            background: "#fff",
            border: "1px solid rgba(12,35,64,.14)",
            borderRadius: "999px",
            padding: "3px",
          }}
        >
          {locations.map((loc) => {
            const isActive = loc === selectedLocation;
            return (
              <div
                key={loc}
                className="tile-selectable"
                role="button"
                tabIndex={0}
                aria-label={`${loc} location${isActive ? ", selected" : ""}`}
                aria-pressed={isActive}
                onClick={() => handleLocationSelect(loc)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    handleLocationSelect(loc);
                  }
                }}
                style={{
                  padding: "7px 20px",
                  borderRadius: "999px",
                  fontSize: "13px",
                  fontWeight: isActive ? 700 : 400,
                  color: isActive ? "#0C2340" : "#5A6B7E",
                  background: isActive ? "rgba(200,164,92,.22)" : "transparent",
                  cursor: "pointer",
                }}
              >
                {loc}
              </div>
            );
          })}
        </div>
      </div>

      {/* Navy live-total bar */}
      <div
        style={{
          background: "#0C2340",
          borderRadius: "10px",
          padding: "14px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div
          style={{
            fontSize: "13.5px",
            color: "rgba(255,255,255,.85)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {totalFormatted
            ? `Draft total · ${descriptor.party ?? 2} guest${(descriptor.party ?? 2) === 1 ? '' : 's'} · ${totalFormatted}`
            : `Draft total · ${descriptor.party ?? 2} guest${(descriptor.party ?? 2) === 1 ? '' : 's'}`}
        </div>
        <div
          style={{
            fontSize: "12.5px",
            color: "#C8A45C",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          View breakdown ›
        </div>
      </div>
    </div>
  );
}
