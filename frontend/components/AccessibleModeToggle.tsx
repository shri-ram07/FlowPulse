"use client";
import { useAccessibleMode } from "@/hooks/useAccessibleMode";

/** Top-nav switch that flips the whole PWA into Accessible Mode. */
export default function AccessibleModeToggle() {
  const { on, toggle } = useAccessibleMode();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={on ? "Turn off Accessible Mode" : "Turn on Accessible Mode"}
      title="Accessible Mode — higher contrast, larger targets, shape-coded zones, no motion"
      onClick={toggle}
      className={`a11y-toggle${on ? " on" : ""}`}
    >
      <span aria-hidden className="a11y-icon">
        {on ? "🅰" : "🅰"}
      </span>
      <span className="a11y-label">{on ? "Accessible: on" : "Accessible mode"}</span>
    </button>
  );
}
