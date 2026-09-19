# Testing brief for Codex

Context: Claude has been making UI/UX and bug fixes to Clarette this session, working
directly in this `Resources` folder (never touching `/Applications/Clarette.app`).
The app has just been rebuilt to `dist/Clarette.app` in this same folder with all the
changes below included.

**Please test only — do not edit any source files.** Report findings back to Kleber
(bugs, anything that looks wrong, anything confusing), and he'll relay them to Claude,
who made these changes and knows the codebase context needed to fix them correctly.
If you and Claude both start editing this code without coordinating through him, we'll
end up with conflicting changes.

Launch `dist/Clarette.app` (not the one in /Applications) to test.

## What changed, and what to check

### 1. Enhance-with dropdown (Adjustments panel > Detail)
- Should only list engines actually usable right now: Classical, EDSR always; Clarette
  Restore/HYPIR/OSEDiff/FlowSR/SeeSR only if genuinely installed/ready; ChatGPT/Gemini/
  Seedream only if an API key is saved and connected.
- Labels should be plain names, no "· Not Installed / Experimental" suffixes.
- Clarette Restore should now show as usable (a bundled Real-ESRGAN model), not "Missing" —
  worth confirming Enhance Portrait actually runs and produces a real result, not an error.

### 2. Restore Faces (Adjustments panel > Detail, checkbox above Enhance Portrait)
- Off by default. When on, after Enhance Portrait runs, it should also run a face-specific
  restoration pass and blend it back in. Check it doesn't look "melted"/uncanny, doesn't
  visibly seam at the edges, and doesn't crash if no face is detected.

### 3. Masking speed
- "Try Apple acceleration" is now on by default (Settings > Cache & Performance). Detect
  Subject should feel meaningfully faster than before on Apple Silicon.

### 4. Native pop-up windows (Settings, Documentation & Tutorials, New Batch, Rename Batch,
   Export, Presets, Workspace, Check for Updates)
- Drag by the title bar: should be smooth, native, no lag/stutter/jump.
- Should NOT be draggable by clicking elsewhere in the window content, and there should be
  no misleading "drag" cursor anywhere except the actual title bar.
- Closing: only the native red traffic-light button should exist — no second "×" anywhere.
- Reopening a window you already closed/switched away from should not spawn a duplicate
  window, and should feel instant (no rebuild lag).
- New Batch and Rename Batch specifically: confirm nothing is cut off at the bottom now.

### 5. View menu
- Exactly one "Entire Screen" item (⌘⇧F), not two.
- Clicking it should toggle between normal size and filling the screen, and toggle back
  correctly on a second click (this uses a plain resize now, not native macOS Spaces
  fullscreen, because the native transition wasn't resizing the window's content correctly
  — worth double-checking content fills the window correctly both ways).

### 6. Portrait Mode workspace (Workspace menu > Portrait Mode) — new, unverified layout
- Preview panel should span the full height on the left.
- Portraits panel should sit top-right (short, wide), Adjustments bottom-right.
- Portraits panel should show as a horizontal scrolling "filmstrip" of compact thumbnail
  cards in this mode, not the normal vertical list.
- No drag-to-resize between these panels yet (fixed proportions) — that's expected, not a bug.
- Switching back to Landscape Mode should restore the normal 3-column layout correctly.

### 7. Drag Panels setting (Settings > Workspace & Preview, was "Show Panel Names" in General)
- Toggling it on should show a small grip icon on each panel (no text label) that lets you
  drag panels to reorder them in Landscape Mode.
- Toggling it off should hide the grip entirely.
- In Portrait Mode, the grip should not appear at all (reordering isn't wired up for that
  layout yet — expected, not a bug).
- Attempting to drag while the workspace is locked should show a clear warning message
  instead of silently doing nothing.

## What's explicitly NOT done yet (don't report these as bugs)
- Freeform drag-anywhere panel positioning (only Landscape Mode's simple reordering exists).
- The Adjustments panel rotating into 4 columns when moved to a side position.
- Resize dividers for Portrait Mode's new layout.
- HYPIR/OSEDiff/FlowSR/SeeSR full installers (separate large project, discussed and
  deliberately deferred).
