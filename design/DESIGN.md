```markdown
# Design System Specification: Clinical Obsidian

## 1. Overview & Creative North Star
**Creative North Star: "The Digital Microscope"**

This design system rejects the "bubbly" friendliness of consumer SaaS in favor of high-fidelity, mission-critical precision. It is designed for the Clinical Decision Support System (CDSS) where every pixel must represent an auditable data point. 

To move beyond a "standard" dark mode, we employ **Monolithic Architecture**. Instead of rounded cards and soft shadows, the UI is treated as a single, carved slab of obsidian. Hierarchy is driven by surgical cuts (high-contrast dividers) and tonal shifts rather than elevation. We break the "template" look through **Rigid Density**: a layout that prioritizes information velocity over white space, using intentional asymmetry to draw the eye toward critical diagnostic alerts.

---

## 2. Colors & Surface Logic
The "Clinical Obsidian" palette is rooted in medical optics—deep voids contrasted against luminescent data markers.

### The "No-Line" Rule
Traditional 1px solid borders for sectioning are strictly prohibited for general layout. Boundaries must be defined by background shifts.
*   **Primary Layout:** Use `surface` (#0b1326) for the base.
*   **Sectioning:** Use `surface_container_low` (#131b2e) to define global navigation or sidebar regions.
*   **Data Nesting:** Use `surface_container_high` (#222a3e) for the most critical interactive panels.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical "wells." Inner data containers should feel recessed or extruded through color:
1.  **Level 0 (Base):** `surface`
2.  **Level 1 (Workspaces):** `surface_container`
3.  **Level 2 (Active Modules):** `surface_container_highest`

### The "Glass & Gradient" Rule
To prevent the UI from feeling "flat," use **Subtle Refraction**. Floating diagnostic modals should use `surface_bright` at 80% opacity with a `backdrop-blur` of 20px. 
*   **Signature Texture:** Primary CTAs should utilize a linear gradient from `primary` (#8aebff) to `primary_container` (#22d3ee) at a 135-degree angle to mimic the glow of a medical monitor.

---

## 3. Typography: Inter Precision
We use **Inter** exclusively for its neutral, high-legibility x-height. In this system, typography is an instrument.

*   **Display (lg/md):** Reserved for high-level clinical metrics (e.g., Heart Rate, SpO2). Use `primary` color to emphasize "Living Data."
*   **Headlines:** Used for patient names and diagnostic categories. 
*   **Labels (md/sm):** These are the workhorses. Use `on_surface_variant` (#bbc9cd) for metadata labels to ensure they don't compete with the actual patient data (`on_surface`).
*   **Editorial Intent:** Use `label-sm` in all-caps with a 0.05rem letter-spacing for "Audit Logs" and "Timestamp" data to provide a technical, laboratory-stamped aesthetic.

---

## 4. Elevation & Depth: Tonal Layering
We abandon the "shadow-heavy" web. Elevation is communicated through **Luminance Contrast**.

*   **The Layering Principle:** A "Surface-on-Surface" approach. Place a `surface_container_lowest` (#060d20) module inside a `surface_container` area to create a "sunken" data-entry field.
*   **Ambient Shadows:** Use only for critical overrides (e.g., an emergency drug-interaction alert). Use a shadow with a 40px blur, 0% spread, and color `surface_container_lowest` at 50% opacity. It should feel like a soft glow, not a drop shadow.
*   **The "Ghost Border" Fallback:** In high-density tables where rows must be distinct, use a "Ghost Border": `outline_variant` (#3c494c) at **15% opacity**. It should be felt, not seen.

---

## 5. Components

### Primitive Controls
*   **Buttons:**
    *   *Primary:* Rectangular (`0px` radius). Gradient fill (`primary` to `primary_container`). `on_primary` text.
    *   *Secondary:* `0px` radius. Ghost-style with a `primary` 1px ghost border (20% opacity).
*   **Inputs:** Use `surface_container_lowest` for the field background. No borders on default state; 1px `primary` underline on focus to mimic a clinical readout.
*   **Checkboxes/Radios:** Sharp 90-degree angles. Use `secondary` (#ffc640) for the "selected" state to provide high-contrast warning/action visibility against the cyan primary.
*   **Cards & Lists:** **Strictly forbid divider lines.** Separate patient records using the Spacing Scale (e.g., `spacing-2` vertical gap) and a background shift to `surface_container_low`.

### CDSS Specific Components
*   **The "Vitals Strip":** A horizontal, high-density component using `surface_container_highest`. Data points are separated by a 1px vertical `outline_variant` (10% opacity) that spans only 50% of the container height.
*   **Audit-Trail Timeline:** A vertical component using a 1px `primary` line (15% opacity) with `primary_fixed` diamond-shaped markers (0px radius) to indicate clinical interventions.
*   **Alert Banners:** Use `error_container` (#93000a) with `on_error_container` text. These must span the full width of the workspace to break the vertical flow of the grid, signaling an immediate stop-state.

---

## 6. Do’s and Don'ts

### Do:
*   **Align to a 0.1rem (1px) Grid:** Precision is paramount. Ensure all elements align to the exact pixel to prevent "blur" on high-density medical displays.
*   **Use Asymmetric Weight:** Balance a heavy data table on the left with a slim, high-contrast action rail on the right.
*   **Embrace the "Dark Void":** Use `surface` (#0b1326) to create "breathing room" between complex data modules.

### Don't:
*   **Don't Round Corners:** Any radius above `0px` is a violation of the "Precision Laboratory" aesthetic.
*   **Don't Use Pure White:** `on_background` (#dbe2fd) is a tinted blue-white. Pure #FFFFFF causes eye strain in dark clinical environments.
*   **Don't Use Standard Tooltips:** Tooltips should be opaque `surface_bright` with sharp corners, appearing instantly without "fade-in" animations to respect the user's need for speed.

---

## 7. Spacing & Rhythm
We use a **Tight-Tolerance Scale**.

*   **Nano-spacing (0.5 - 1.5):** Use for internal padding of data cells and buttons.
*   **Macro-spacing (10 - 24):** Use for separating major clinical modules (e.g., Patient History vs. Active Meds).
*   **The Rule of Density:** On a desktop CDSS, prioritize information density. If a screen feels "empty," increase the granularity of the displayed data rather than increasing the white space.```