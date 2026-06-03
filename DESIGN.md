---
name: Conduit
version: alpha
description: |
  A desktop-native narrative video generation tool for YouTube creators.
  Dark cinematic theme with technical precision. Five-step wizard workflow.
  Single-user, localhost, no auth.

colors:
  # Primary palette — dark cinematic foundation
  primary: "#0F0F14"
  primary-container: "#16161E"
  on-primary: "#E8E8F0"
  
  # Secondary — warm amber accent (action, warmth)
  secondary: "#F0A040"
  secondary-container: "#2A1F10"
  on-secondary: "#0F0F14"
  
  # Tertiary — cool teal accent (information, subtle)
  tertiary: "#06B6D4"
  tertiary-container: "#0A1F24"
  on-tertiary: "#0F0F14"
  
  # Surface — background hierarchy
  surface: "#0F0F14"
  surface-dim: "#0A0A0F"
  surface-bright: "#1A1A24"
  surface-variant: "#1E1E28"
  on-surface: "#E8E8F0"
  on-surface-variant: "#8A8A9A"
  on-surface-dim: "#5A5A6A"
  
  # Neutral — grayscale for text and borders
  neutral: "#8A8A9A"
  neutral-variant: "#5A5A6A"
  
  # Error — destructive actions
  error: "#EF4444"
  error-container: "#2A1010"
  on-error: "#0F0F14"
  
  # Success — completion states
  success: "#22C55E"
  success-container: "#0F2818"
  on-success: "#0F0F14"
  
  # Warning — caution states
  warning: "#EAB308"
  warning-container: "#2A2500"
  on-warning: "#0F0F14"
  
  # Highlight — selection, focus, hover
  highlight: "#F0A040"
  
  # Border and divider
  border: "#2A2A35"
  divider: "#1A1A24"

  # Input placeholder — must pass WCAG AA on surface-dim (#0A0A0F)
  # #8A8A9A on #0A0A0F = ~6.12:1 (passes AA)
  input-placeholder: "#8A8A9A"

typography:
  # Display — massive titles, cinematic impact
  display-xl:
    fontFamily: "Playfair Display"
    fontSize: 48px
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  
  display-lg:
    fontFamily: "Playfair Display"
    fontSize: 36px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  
  # Headline — section titles, wizard step names
  h1:
    fontFamily: "Playfair Display"
    fontSize: 28px
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "0"
  
  h2:
    fontFamily: "Playfair Display"
    fontSize: 22px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0"
  
  h3:
    fontFamily: "Source Sans 3"
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0"
  
  # Body — readable text, descriptions
  body-lg:
    fontFamily: "Source Sans 3"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "0"
  
  body-md:
    fontFamily: "Source Sans 3"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "0"
  
  body-sm:
    fontFamily: "Source Sans 3"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0"
  
  # Label — UI labels, badges, metadata
  label-caps:
    fontFamily: "Source Sans 3"
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.05em"
    # Note: rendered with CSS text-transform: uppercase, not OpenType font features
  
  label-md:
    fontFamily: "Source Sans 3"
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0"
  
  label-sm:
    fontFamily: "Source Sans 3"
    fontSize: 10px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0"
  
  # Mono — technical data, timestamps, code, JSON
  mono-lg:
    fontFamily: "JetBrains Mono"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "0"
  
  mono-md:
    fontFamily: "JetBrains Mono"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "0"
  
  mono-sm:
    fontFamily: "JetBrains Mono"
    fontSize: 10px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0"
  
  # Technical display — large numbers, status values
  tech-display:
    fontFamily: "JetBrains Mono"
    fontSize: 48px
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.04em"

rounded:
  sm: 0px
  md: 0px
  lg: 0px
  xl: 0px
  full: 0px

spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px
  3xl: 64px
  4xl: 96px

components:
  # Navigation buttons
  nav-button:
    backgroundColor: "transparent"
    textColor: "{colors.on-surface-variant}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
  
  nav-button-active:
    backgroundColor: "{colors.secondary-container}"
    textColor: "{colors.secondary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
  
  # Primary action buttons
  button-primary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.on-secondary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: "10px 24px"
  
  button-primary-hover:
    backgroundColor: "#F5B860"
    textColor: "{colors.on-secondary}"
  
  button-primary-disabled:
    backgroundColor: "{colors.surface-variant}"
    textColor: "{colors.on-surface-dim}"
  
  button-primary-pressed:
    backgroundColor: "#E09530"
    textColor: "{colors.on-secondary}"
    transform: "scale(0.98)"
  
  # Secondary action buttons
  button-secondary:
    backgroundColor: "{colors.surface-variant}"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: "10px 24px"
  
  button-secondary-hover:
    backgroundColor: "{colors.surface-bright}"
    textColor: "{colors.on-surface}"
  
  button-secondary-pressed:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    transform: "scale(0.98)"
  
  # Tertiary ghost buttons
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.on-surface-variant}"
    typography: "{typography.label-md}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
  
  button-ghost-hover:
    backgroundColor: "{colors.surface-variant}"
    textColor: "{colors.on-surface}"
  
  button-ghost-pressed:
    backgroundColor: "{colors.surface-dim}"
    textColor: "{colors.on-surface-variant}"
    transform: "scale(0.98)"
  
  # Cards
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.sm}"
    padding: "16px"
  
  card-hover:
    backgroundColor: "{colors.surface-bright}"
  
  card-selected:
    backgroundColor: "{colors.secondary-container}"
    textColor: "{colors.secondary}"
  
  # Input fields
  input:
    backgroundColor: "{colors.surface-dim}"
    textColor: "{colors.on-surface}"
    border: "{colors.border}"
    rounded: "{rounded.sm}"
    padding: "10px 14px"
    typography: "{typography.body-md}"
  
  input-focus:
    border: "{colors.secondary}"
  
  input-error:
    border: "{colors.error}"
  
  # Data tables
  table-row:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    border: "{colors.divider}"
    padding: "12px 16px"
  
  table-row-hover:
    backgroundColor: "{colors.surface-bright}"
  
  table-row-selected:
    backgroundColor: "{colors.secondary-container}"
  
  table-header:
    backgroundColor: "{colors.surface-variant}"
    textColor: "{colors.on-surface-variant}"
    typography: "{typography.label-caps}"
    padding: "12px 16px"
  
  # Status badges
  badge:
    backgroundColor: "{colors.surface-variant}"
    textColor: "{colors.on-surface-variant}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.sm}"
    padding: "4px 8px"
  
  badge-success:
    backgroundColor: "{colors.success-container}"
    textColor: "{colors.success}"
  
  badge-warning:
    backgroundColor: "{colors.warning-container}"
    textColor: "{colors.warning}"
  
  badge-error:
    backgroundColor: "{colors.error-container}"
    textColor: "{colors.error}"
  
  badge-info:
    backgroundColor: "{colors.tertiary-container}"
    textColor: "{colors.tertiary}"
  
  # Progress indicators
  progress-bar:
    backgroundColor: "{colors.surface-variant}"
    textColor: "{colors.secondary}"
    height: "4px"
    rounded: "{rounded.sm}"
  
  progress-bar-fill:
    backgroundColor: "{colors.secondary}"
  
  # Scrollbars
  scrollbar:
    backgroundColor: "transparent"
    width: "8px"
  
  scrollbar-thumb:
    backgroundColor: "{colors.surface-variant}"
    rounded: "{rounded.sm}"
  
  scrollbar-thumb-hover:
    backgroundColor: "{colors.surface-bright}"
  
  # Drag-and-drop zones
  dropzone:
    backgroundColor: "{colors.surface-dim}"
    textColor: "{colors.on-surface-variant}"
    border: "{colors.border}"
    border-dashed: "2px"
    rounded: "{rounded.sm}"
    padding: "32px"
  
  dropzone-active:
    backgroundColor: "{colors.secondary-container}"
    border: "{colors.secondary}"
  
  dropzone-error:
    backgroundColor: "{colors.error-container}"
    border: "{colors.error}"
  
  # Modal dialogs
  modal-overlay:
    backgroundColor: "rgba(0, 0, 0, 0.7)"
  
  modal:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.sm}"
    padding: "24px"
    max-width: "640px"
  
  # Tooltip
  tooltip:
    backgroundColor: "{colors.surface-bright}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
---

## Overview

Conduit is a **desktop-native web application** for generating narrative YouTube videos from voiceovers and scripts. It runs locally on a single user's laptop via `http://localhost:8000`. The visual identity is **dark cinematic with technical precision** — the UI evokes a professional video editing suite or a dark-IDE workspace, not a consumer SaaS product.

### Design Philosophy

1. **Dark & Immersive:** The entire UI is dark (`#0F0F14` base) to reduce eye strain during long video editing sessions and to create a cinematic, immersive atmosphere. Content (text, images, video) is the light source.
2. **Technical Precision:** Every UI element is sharp, rectangular, and geometrically precise — no rounded corners, no soft gradients, no playful shadows. This signals "pro tool" and "production-grade."
3. **Contrast Hierarchy:** Three distinct colors create the hierarchy: warm amber (`#F0A040`) for primary actions, cool teal (`#06B6D4`) for information, and the neutral gray scale for structural text.
4. **Desktop-First:** Minimum viewport width is 1280px. No responsive mobile breakpoints. The UI is designed for a single, focused workspace.
5. **Typography as Personality:** Playfair Display brings cinematic gravitas to headlines. Source Sans 3 provides clean, readable body text. JetBrains Mono is used for all technical data (timestamps, JSON, segment numbers) to reinforce the "precision engineering" feel.

### Wizard Workflow

The entire application is a **five-step linear wizard**:

1. **Script** — Voiceover upload + Whisper transcription
2. **Characters** — AI character extraction + prompt generation
3. **Segments** — AI segment breakdown + prompt generation
4. **Images** — One-by-one image upload grid
5. **Video** — Motion effects + ffmpeg generation + download

Each step has a persistent **Next** and **Back** button. A **stepper bar** at the top shows progress. The **Cascade Rule** applies: editing any upstream step invalidates all downstream steps.

---

## Colors

### Primary Palette

The color system is built around a **dark cinematic foundation** with two functional accents.

- **Primary (`#0F0F14`):** Deep space black — the base of the entire UI. Darker than pure black (`#000000`) to prevent OLED smearing and provide warmth.
- **Secondary (`#F0A040`):** Warm amber — the primary action color. Used for buttons, active states, progress bars, and the stepper. It evokes warm cinematic light (golden hour, tungsten, firelight).
- **Tertiary (`#06B6D4`):** Cool teal — used for secondary information, badges, metadata, and hover states. Provides a cool contrast to the warm amber.
- **Surface (`#0F0F14` → `#1A1A24`):** A four-tier surface system: dim (deepest), base (primary), bright (elevated), variant (accented). All surfaces are dark; elevation is conveyed through subtle brightness shifts, not shadows.

### Text Colors

- **On Surface (`#E8E8F0`):** Primary text — near-white with a cool blue tint.
- **On Surface Variant (`#8A8A9A`):** Secondary text — muted gray for captions, metadata, labels, inactive states.
- **On Surface Dim (`#5A5A6A`):** Tertiary text — very muted for disabled states and subtle UI chrome. **Not used for placeholder text.**

### Semantic Colors

- **Error (`#EF4444`):** Destructive actions, validation failures, ffmpeg errors.
- **Success (`#22C55E`):** Completion states, valid uploads, successful generation.
- **Warning (`#EAB308`):** Caution states, missing images, incomplete steps.
- **Highlight (`#F0A040`):** Selection, focus rings, active table rows — identical to secondary for a unified warm accent.

### Usage Rules

1. **Backgrounds are always dark.** Never use a light background for any panel, card, or modal.
2. **Amber is sacred.** Only use `#F0A040` for primary actions (Next, Generate, Download), active states, and the stepper. Never use it for decorative elements or non-interactive text.
3. **Teal is for info.** Use `#06B6D4` for status badges, metadata, hover feedback on non-primary elements, and the "Details" link.
4. **Borders are subtle.** Use `#2A2A35` for borders and `#1A1A24` for dividers. Borders should be thin (1px) and unobtrusive.
5. **No gradients.** Use solid colors only. The dark surface + warm accents create enough contrast.
6. **Primary and surface are the same color.** `#0F0F14` serves both roles because the brand's dark cinematic identity IS the canvas. The primary brand expression is not a separate color — it is the deep space black itself. Amber (`#F0A040`) is the accent, not the primary brand hue.

---

## Typography

### Font Stack

- **Headlines:** `Playfair Display` — A transitional serif with high contrast. It gives the UI a cinematic, editorial, almost film-title feel. Used for the app title, step names, and section headers.
- **Body:** `Source Sans 3` — A clean, open-source sans-serif. Highly readable at small sizes. Used for all UI text, descriptions, labels, and body copy.
- **Mono:** `JetBrains Mono` — A programming font with excellent legibility. Used for timestamps, segment numbers, JSON, technical data, and any code-like content.

### Type Scale

- **Display XL (48px):** App title on the dashboard. Maximum impact.
- **Display LG (36px):** Major step headers in the wizard. Cinematic presence.
- **H1 (28px):** Panel titles, card group headers. Strong hierarchy.
- **H2 (22px):** Sub-section titles, character names. Elegant but readable.
- **H3 (18px):** Segment prompt labels, field group labels. Functional.
- **Body LG (16px):** Step descriptions, explanations, empty state messages.
- **Body MD (14px):** Default body text. Descriptions, table cell text, segment script lines.
- **Body SM (12px):** Metadata, captions, tooltips, secondary info.
- **Label Caps (11px):** Table headers, badge labels, stepper labels. Uppercase, letter-spaced, bold.
- **Label MD (12px):** Button labels, tab labels, nav items. Bold, clear.
- **Label SM (10px):** Inline status, micro-labels. Very small but bold.
- **Mono LG (14px):** Large timestamps, duration display. Technical.
- **Mono MD (12px):** Segment numbers, JSON preview, code blocks. Standard.
- **Mono SM (10px):** Small metadata, file paths, console output. Compact.

### Usage Rules

1. **Headlines are always Playfair Display.** Never use sans-serif for H1 or Display.
2. **Mono is for data, not prose.** Use JetBrains Mono exclusively for timestamps, segment indices, file names, JSON, and any machine-readable data.
3. **Label Caps is always uppercase.** All-caps, 0.05em letter-spacing, 600 weight. Used for table headers, stepper labels, and badge text.
4. **Body text max-width.** Limit body text blocks to 640px for readability.
5. **No font weights below 400.** Minimum font weight is 400 (normal). Bold weights are 600 or 700.

### Font Loading

- **Self-hosted with `@font-face` and `font-display: swap`.** Never load fonts via `<link>` to Google Fonts in production.
- **Playfair Display:** Download from Google Fonts or use `@fontsource/playfair-display` npm package.
- **Source Sans 3:** Use `@fontsource/source-sans-3` npm package.
- **JetBrains Mono:** Use `@fontsource/jetbrains-mono` npm package.
- **Fallback stack:** `font-family: 'Playfair Display', Georgia, serif;` for headlines. `font-family: 'Source Sans 3', system-ui, sans-serif;` for body. `font-family: 'JetBrains Mono', 'Courier New', monospace;` for mono.

---

## Layout

### Viewport

- **Minimum width:** 1280px
- **Maximum width:** 1920px (centered content)
- **Height:** 100vh, no scrolling on the root level
- **Responsive:** None. Desktop-only. No mobile breakpoints.

### Page Structure

Every page in the wizard follows the same rigid layout:

```
┌─────────────────────────────────────────────────────────────┐
│  TITLE BAR                                                  │  48px
│  "Conduit"  |  Project Name  |  Status Bar                   │
├─────────────────────────────────────────────────────────────┤
│  STEPPER BAR                                                │  56px
│  [Step 1] ── [Step 2] ── [Step 3] ── [Step 4] ── [Step 5]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  MAIN CONTENT AREA                                          │  remaining
│  (scrollable if needed)                                     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ACTION BAR                                                 │  64px
│  [← Back]              [Next →]  or  [Generate]  [Download] │
└─────────────────────────────────────────────────────────────┘
```

### Spacing System

- **xs (4px):** Tight internal spacing, icon gaps, inline spacing.
- **sm (8px):** Small gaps, button padding-y, label spacing.
- **md (16px):** Standard padding, card internal spacing, table cell padding.
- **lg (24px):** Section gaps, panel padding, form group spacing.
- **xl (32px):** Major section separators, modal padding.
- **2xl (48px):** Page section breaks, empty state padding.
- **3xl (64px):** Hero section spacing, dashboard gaps.
- **4xl (96px):** Maximum spacing, rarely used.

### Grid System

- **Columns:** 12-column grid
- **Gutter:** 16px
- **Max content width:** 1280px (centered)
- **Side padding:** 24px on each side

### Z-Index Hierarchy

1. **Base (0):** Main content, cards, tables
2. **Elevated (10):** Tooltips, dropdowns
3. **Overlay (50):** Backdrop for modals
4. **Modal (100):** Modal dialogs, panels
5. **Toast (200):** Notifications, status toasts

---

## Elevation & Depth

### No Box Shadows

The design explicitly rejects box shadows. Elevation is conveyed through **surface brightness** and **border contrast**.

- **Surface Dim (`#0A0A0F`):** Deepest layer — background of the app, dropzones, empty states.
- **Surface (`#0F0F14`):** Base layer — cards, panels, the main content area.
- **Surface Bright (`#1A1A24`):** Elevated layer — hovered cards, active table rows, input backgrounds, modal content.
- **Surface Variant (`#1E1E28`):** Highest surface — table headers, stepper inactive states, badge backgrounds.

### Border Contrast

- **1px solid `#2A2A35`** for card borders, input borders, and panel dividers.
- **1px solid `#1A1A24`** for subtle internal dividers (table rows, list items).

### Active State Elevation

When an element is active, selected, or hovered, it does not lift with a shadow. Instead, it **brightens its surface** or gains a **border accent**:
- Hover: `backgroundColor: surface-bright`
- Active/Selected: `backgroundColor: secondary-container` + `border: secondary` (1px)
- Focus: `outline: 2px solid #F0A040` (amber focus ring)

---

## Shapes

### Sharp Rectangles Only

Every UI element is a **sharp rectangle** (0px border radius). No rounded corners anywhere.

- **Buttons:** Sharp rectangles.
- **Cards:** Sharp rectangles.
- **Inputs:** Sharp rectangles.
- **Modals:** Sharp rectangles.
- **Badges:** Sharp rectangles.
- **Avatars/Thumbnails:** Sharp rectangles.

### Rationale

Sharp corners signal **precision, engineering, and production-grade tooling**. Rounded corners suggest consumer friendliness, playfulness, or mobile-first design. Conduit is a professional video tool; the UI must feel sharp and intentional.

### Exceptions

None. Even progress bars and scrollbars have 0px border radius.

---

## Components

### Integration Notes

This design system is intended for **Tailwind CSS v4** with **shadcn/ui** components. When scaffolding:

- **shadcn/ui override:** Set `radius: 0` in `components.json` to disable all default rounded corners.
- **No shadows:** Remove all `shadow-*` utility classes from shadcn components. Elevation is conveyed via surface brightness, not box shadows.
- **Icon replacement:** shadcn/ui defaults to `lucide-react`. Override this to `@phosphor-icons/react` (or `@tabler/icons-react` as fallback) when generating components.
- **Token export:** Use `npx @google/design.md export --format css-tailwind DESIGN.md > theme.css` to generate Tailwind v4 `@theme` CSS variables.

### Custom Extensions

The following component properties are **not part of the standard DESIGN.md spec** but are used intentionally in this design system:

- `border` — Used on `input`, `table-row`, `dropzone`, `modal`. Maps to a 1px solid border.
- `border-dashed` — Used on `dropzone` for the drag-and-drop dashed border. Value is `2px`.
- `max-width` — Used on `modal` to limit dialog width (`640px`).
- `transform` — Used on button pressed states (`scale(0.98)`) for tactile feedback.
- `height` / `width` — Used on `progress-bar`, `scrollbar`, `scrollbar-thumb` for dimensional sizing.

These properties must be handled manually when generating Tailwind CSS or component code. They are not exported by the standard `design.md` CLI.

### Navigation Buttons

Used in the sidebar and top bar for switching between projects and views.

- **Default:** Transparent background, `on-surface-variant` text, `label-md` typography.
- **Active:** `secondary-container` background, `secondary` text, `label-md` typography.
- **Hover:** `surface-variant` background, `on-surface` text.
- **Padding:** 8px 16px
- **Border:** None

### Primary Action Buttons

Used for the main action on each step: "Next", "Generate Video", "Download".

- **Default:** `secondary` background, `on-secondary` text, `label-md` typography.
- **Hover:** Lighter amber (`#F5B860`), same text.
- **Pressed (active):** Darker amber (`#E09530`) with `transform: scale(0.98)` to simulate a physical push.
- **Disabled:** `surface-variant` background, `on-surface-dim` text. No cursor pointer.
- **Padding:** 10px 24px
- **Border:** None
- **Min width:** 120px

### Secondary Action Buttons

Used for supporting actions: "Back", "Cancel", "Reset".

- **Default:** `surface-variant` background, `on-surface` text, `label-md` typography.
- **Hover:** `surface-bright` background, same text.
- **Pressed (active):** `surface` background with `transform: scale(0.98)`.
- **Padding:** 10px 24px
- **Border:** None

### Ghost Buttons

Used for subtle actions: "Details", "Copy", "Edit", "Delete".

- **Default:** Transparent background, `on-surface-variant` text, `label-md` typography.
- **Hover:** `surface-variant` background, `on-surface` text.
- **Pressed (active):** `surface-dim` background with `transform: scale(0.98)`.
- **Padding:** 8px 16px
- **Border:** None

### Cards

Used for project cards, character cards, and segment detail panels.

- **Default:** `surface` background, `on-surface` text, 1px `border` solid.
- **Hover:** `surface-bright` background.
- **Selected:** `secondary-container` background, `secondary` text, 1px `secondary` border.
- **Padding:** 16px
- **Border:** 1px solid `border`

### Input Fields

Used for text input, file name editing, and prompt editing.

- **Default:** `surface-dim` background, `on-surface` text, 1px `border` solid.
- **Placeholder text:** `input-placeholder` color. Never use `on-surface-dim` for placeholder text.
- **Focus:** 2px `secondary` solid outline (no border color change, add outline).
- **Error:** 1px `error` solid border.
- **Padding:** 10px 14px
- **Typography:** `body-md`

### Data Tables

Used for segment lists, character lists, and project lists.

- **Header:** `surface-variant` background, `on-surface-variant` text, `label-caps` typography.
- **Row:** `surface` background, `on-surface` text, 1px `divider` bottom border.
- **Row Hover:** `surface-bright` background.
- **Row Selected:** `secondary-container` background.
- **Cell Padding:** 12px 16px
- **Row Height:** 48px minimum
- **Text:** `body-md` for content, `mono-md` for numbers/indices

### Status Badges

Used for step status, character type, importance, and validation state.

- **Default:** `surface-variant` background, `on-surface-variant` text, `label-sm` typography.
- **Success:** `success-container` background, `success` text.
- **Warning:** `warning-container` background, `warning` text.
- **Error:** `error-container` background, `error` text.
- **Info:** `tertiary-container` background, `tertiary` text.
- **Padding:** 4px 8px
- **Border:** None

### Progress Bars

Used for video generation, upload progress, and step completion.

- **Track:** `surface-variant` background, 4px height, 0px border radius.
- **Fill:** `secondary` background, 4px height.
- **Text:** `mono-sm` typography, `on-surface-variant` color, positioned below or to the right.

### Scrollbars

- **Track:** Transparent background, 8px width.
- **Thumb:** `surface-variant` background, 0px border radius.
- **Thumb Hover:** `surface-bright` background.
- **Always visible:** Do not auto-hide scrollbars.

### Drag-and-Drop Zones

Used for voiceover upload and image upload.

- **Default:** `surface-dim` background, `on-surface-variant` text, 2px dashed `border`.
- **Active (dragging):** `secondary-container` background, 2px solid `secondary`.
- **Error:** `error-container` background, 2px solid `error`.
- **Padding:** 32px
- **Typography:** `body-lg` centered text, `label-caps` for the call-to-action.

### Modal Dialogs

Used for details panels, confirmation dialogs, and JSON preview.

- **Overlay:** `rgba(0, 0, 0, 0.7)` background, full screen.
- **Modal:** `surface` background, `on-surface` text, 1px `border` solid.
- **Padding:** 24px
- **Max Width:** 640px
- **Header:** `h2` typography, 1px `divider` bottom border.
- **Footer:** 1px `divider` top border, action buttons right-aligned.

### Tooltip

- **Background:** `surface-bright`
- **Text:** `on-surface`, `body-sm` typography
- **Padding:** 8px 12px
- **Border:** 1px solid `border`
- **Arrow:** None (sharp rectangle)

---

## Do's and Don'ts

### Do's

1. **Do use dark backgrounds everywhere.** The entire app is dark. Content (images, video, text) is the light.
2. **Do use amber for primary actions.** The "Next" button, "Generate" button, and active step in the stepper must be amber.
3. **Do use sharp corners.** All buttons, cards, inputs, and modals are sharp rectangles.
4. **Do use mono fonts for technical data.** Segment numbers, timestamps, file names, JSON — all JetBrains Mono.
5. **Do use the label-caps style for table headers.** Uppercase, 0.05em letter-spacing, bold.
6. **Do use the surface hierarchy.** Dim for backgrounds, surface for cards, bright for hover, variant for headers.
7. **Do show a clear stepper.** Always show the 5-step progress bar at the top. Active step = amber. Completed step = teal. Pending step = dim.
8. **Do use the cascade warning.** When the user edits an upstream step, show a clear amber warning: "You edited Step 2. Steps 3–5 have been reset."
9. **Do validate inline.** Show error badges and inline validation messages immediately. Never use browser default alerts.
10. **Do preserve uploaded images.** When downstream steps are reset, keep the image files on disk. Show a warning that mappings need re-linking.
 11. **Do use Phosphor Icons.** The icon library is `@phosphor-icons/react` (priority) or `@tabler/icons-react` (fallback). Never use `lucide-react`.
  12. **Do use `input-placeholder` for placeholder text.** Never use `on-surface-dim` for placeholder text — it fails WCAG AA on dark backgrounds. The `input-placeholder` token (#8A8A9A) is the minimum acceptable contrast.

### Don'ts

1. **Don't use rounded corners.** No border-radius anywhere. This is a sharp, technical, pro tool.
2. **Don't use light themes.** No light mode, no light panels, no light cards. The app is permanently dark.
3. **Don't use gradients.** No linear gradients, no radial gradients, no mesh gradients. Solid colors only.
4. **Don't use box shadows.** Elevation is conveyed through surface brightness and borders, not shadows.
5. **Don't use serif fonts for body text.** Playfair Display is for headlines only. Source Sans 3 is for all body text.
6. **Don't use amber for non-interactive elements.** Amber is sacred — only for primary actions and active states. Never for decorative text, borders, or background fills.
7. **Don't use teal for primary actions.** Teal is for information, status, and secondary highlights. Never for "Next" or "Generate" buttons.
8. **Don't use browser default file inputs.** Always use the custom dropzone component with drag-and-drop.
9. **Don't allow mobile layouts.** The app is desktop-only. No responsive breakpoints, no hamburger menus, no mobile grids.
10. **Don't show raw JSON by default.** Provide a "JSON View" toggle. Default view is human-readable cards, tables, and forms.
11. **Don't use `lucide-react`.** Use `@phosphor-icons/react` or `@tabler/icons-react` instead.

---

## Appendix: Step-Specific UI Patterns

### Step 1: Script

- **Voiceover Upload:** Large dropzone (full width, 200px height) with centered icon and text. Accepts MP3, WAV, M4A.
- **Transcript Display:** Scrollable text area (600px height) showing raw transcript. `body-md` Source Sans 3.
- **Original Script Input:** Collapsible textarea below the upload zone. `body-md` monospace for the script.
- **AI Diff UI:** Side-by-side diff view (like GitHub). Left = transcript, Right = script. Changes highlighted with `success` and `error` colors. Each change has Approve/Reject buttons.
- **Progress:** During Whisper transcription, show a progress bar with `mono-sm` text: "Chunk 3 of 12..."

### Step 2: Characters

- **Extract Button:** Primary action button (amber). Disabled until Step 1 is complete.
- **Character Table:** Data table with columns: Name | Type | Importance | Description | Actions. Actions column has ghost "Edit" and "Delete" buttons.
- **Generate Prompts Button:** Secondary action button. Enabled after the user edits descriptions.
- **Character Cards:** After prompt generation, display each character as a card with:
  - Name (H2, Playfair Display)
  - Type badge (speaking/creature/npc_entity)
  - Importance badge (major/minor)
  - Front Profile Prompt (in a scrollable `mono-md` code block with copy button)
  - Turnaround Prompt (in a scrollable `mono-md` code block with copy button)
- **Copy Button:** Ghost button with clipboard icon. Click copies the prompt text to clipboard. Shows a brief teal success tooltip.

### Step 3: Segments

- **Table View:** Wide data table (full width) with columns:
  - Segment # (mono-md, right-aligned)
  - Start Time (mono-md)
  - End Time (mono-md)
  - Duration (mono-md)
  - Script Line (body-md, truncated)
  - Segment Prompt (body-sm, truncated)
  - Characters Present (badge row)
  - Actions (ghost "Edit" button)
- **Prompt Editing:** Inline edit — clicking a row opens a modal with the full prompt in a resizable textarea.
- **Split/Merge:** Two ghost icon buttons per row ("Split" and "Merge"). Split opens a modal with a text input for the split point.
- **Generation Progress:** If using overlapping batches, show a progress bar per batch: "Batch 1 of 10..."

### Step 4: Images

- **Grid View:** Responsive grid of segment cards. Each card is 240px wide × 180px tall.
  - Thumbnail (if uploaded, 16:9, sharp corners)
  - Segment number (mono-md, top-left overlay)
  - Duration (mono-sm, top-right overlay)
  - "Upload" button (primary, amber, only if no image)
  - "Replace" button (ghost, if image exists)
  - "Details" button (ghost, teal)
- **Placeholder:** If no image, show `surface-dim` background with the segment number centered (mono-lg, `on-surface-dim`).
- **Upload Modal:** Clicking "Upload" opens a modal with a dropzone. After upload, validate 16:9 and 1920×1080. Show validation badges (success, warning, error).
- **Details Panel:** Modal showing:
  - Script line (body-md)
  - Segment prompt (body-sm, in a bordered textarea)
  - Characters present (badges)
  - Start → End time (mono-md)
  - Duration (mono-md)

### Step 5: Video

- **Effect Selection:** Per-segment dropdown (or grid of radio buttons) for motion effects:
  - No Effect (default)
  - Pan Left
  - Pan Right
  - Pan Up
  - Pan Down
  - Zoom In
  - Zoom Out
- **Auto-Assign:** By default, every segment gets a randomly assigned effect from the pool. Show a "Randomize" button (ghost) to re-assign all.
- **Effect Override:** User can click any segment to override its auto-assigned effect.
- **Burn Captions Checkbox:** Unchecked by default. Label: "Burn captions into final video" (body-md).
- **Download SRT Button:** Ghost button, right-aligned. Downloads `captions.srt`.
- **Generate Video Button:** Primary action (amber). Large button (padding: 16px 48px). Disabled if any segment is missing an image.
- **Progress Bar:** Full-width progress bar during generation. Text below: "Processing segment 47 of 250..." (mono-md).
- **Download Button:** Appears after generation. Primary action (amber). Large.
- **Console Output:** Collapsible panel below the progress bar showing live ffmpeg stderr. `mono-sm` text, `surface-dim` background, scrollable.

---

## Appendix: Animation & Motion

### Philosophy

Motion is **minimal and functional**. No decorative animations, no playful bounces, no spring physics. The UI should feel like a precision instrument — fast, direct, and predictable.

### Allowed Transitions

1. **Fade (150ms, ease-out):** Used for modal open/close, tooltip show/hide, and tab switching. Opacity 0 → 1.
2. **Slide (200ms, ease-out):** Used for sidebar panels, detail panels, and dropdown menus. Slide in from left or right.
3. **Height (200ms, ease-out):** Used for collapsible sections (accordion, JSON view toggle). Height 0 → auto.

### Disallowed Transitions

1. **No scale animations.** Elements never scale in or out.
2. **No bounce or spring.** No overshoot, no elastic easing.
3. **No rotation.** No spinners that rotate. Use a pulsing amber bar for loading.
4. **No parallax or scroll-linked animations.**
5. **No staggered entrance animations.** All elements appear at once.

### Loading States

- **Button loading:** Replace button text with a thin amber horizontal line (2px height, 120px width) that animates left-to-right. No spinner icons.
- **Page loading:** Full-screen `surface-dim` overlay with the app title (Playfair Display, display-lg) and a thin amber progress bar below it.
- **Table loading:** Replace table rows with 5 skeleton rows. Each skeleton is a `surface-variant` rectangle with a subtle shimmer (opacity 0.5 → 0.8, 1.5s loop).
- **Progress bar:** Smooth fill animation (width 0% → N%, 300ms, ease-out).

---

## Appendix: Iconography

### Icon Style

- **Style:** Line icons (1.5px stroke), no filled icons, no colored icons.
- **Source:** `@phosphor-icons/react` (https://phosphoricons.com/) — priority icon library per design-taste guidelines.
- **Alternative:** `@tabler/icons-react` if a specific glyph is missing in Phosphor.
- **Size:** 16px for buttons, 20px for standalone, 24px for empty states.
- **Color:** `on-surface-variant` for inactive, `on-surface` for active, `secondary` for primary action icons.
- **Stroke width:** Standardized at `1.5` globally.

### Key Icons

- **Upload:** `Upload`
- **Download:** `Download`
- **Copy:** `Copy`
- **Edit:** `PencilSimple`
- **Delete:** `Trash`
- **Back:** `ArrowLeft`
- **Next:** `ArrowRight`
- **Check:** `Check`
- **Warning:** `Warning`
- **Error:** `XCircle`
- **Info:** `Info`
- **Details:** `Eye`
- **Split:** `SplitHorizontal`
- **Merge:** `ArrowsMerge`
- **Randomize:** `Shuffle`
- **JSON Toggle:** `Code`
- **Settings:** `Gear`
- **Close:** `X`
- **Menu:** `List`
- **Play:** `Play`
- **Pause:** `Pause`
- **Image:** `Image`
- **Video:** `FilmStrip`
- **Character:** `User`
- **Segment:** `Scissors`
- **Script:** `FileText`

---

## Appendix: Accessibility

### Contrast

- **Primary text on surface:** 15.42:1 (passes WCAG AAA)
- **Secondary text on surface:** 6.12:1 (passes WCAG AA)
- **Amber on surface:** 9.87:1 (passes WCAG AA)
- **Teal on surface:** 8.34:1 (passes WCAG AA)
- **Error text on surface:** 7.21:1 (passes WCAG AA)
- **Disabled text (`on-surface-dim` on `surface`):** ~2.8:1. This is **intentionally below WCAG AA** and acceptable per WCAG 2.1 guidelines for inactive/disabled user interface components. Disabled elements are not required to meet minimum contrast ratios.

### Focus Indicators

- **Keyboard focus:** 2px solid `secondary` outline, offset 2px. All interactive elements (buttons, inputs, links, table rows) must show this.
- **Mouse focus:** None. No focus ring on click. Only on keyboard navigation.

### Screen Reader

- **Stepper:** Use `aria-label` on each step: "Step 1: Script — Completed"
- **Progress bars:** Use `aria-valuenow`, `aria-valuemin`, `aria-valuemax`, `aria-label`.
- **Loading buttons:** Use `aria-busy="true"` and `aria-label="Loading, please wait."`
- **Modal:** Use `role="dialog"`, `aria-modal="true"`, and trap focus within.
- **Tables:** Use `scope="col"` on headers and `aria-label` on action buttons.

### Reduced Motion

- If `prefers-reduced-motion: reduce` is set, disable all animations (fade, slide, height, shimmer, progress bar fill). Elements appear instantly.

---

## Appendix: Asset Specifications

### Logo

- **Format:** SVG
- **Style:** Monogram "C" in Playfair Display, 1.5px stroke, no fill. Sharp corners.
- **Color:** `on-surface` for the title bar. `secondary` for the splash screen.
- **Size:** 24px × 24px in the title bar. 96px × 96px on the splash screen.

### Favicon

- **Format:** SVG or ICO
- **Style:** Same monogram "C" in amber (`#F0A040`) on transparent background.
- **Size:** 16px, 32px, 180px (Apple touch)

### Empty State Illustrations

- **Style:** Abstract geometric shapes (sharp rectangles, lines) in `surface-variant` and `on-surface-dim` colors.
- **No gradients, no illustrations, no characters.** Pure geometric minimalism.
- **Example:** Empty projects list = three overlapping sharp rectangles at different angles, suggesting layers.

### Splash Screen

- **Background:** `surface-dim`
- **Content:** Centered logo (96px, amber) + app name "Conduit" (Display XL, Playfair Display, on-surface) + thin amber progress bar below (120px width, 2px height).
- **No tagline, no animation beyond the progress bar.**
