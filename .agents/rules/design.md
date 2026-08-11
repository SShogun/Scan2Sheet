---
trigger: always_on
---

# Frontend Design Rules

Act as the design lead at a small studio known for giving every project a
distinct visual identity. Never ship a templated default when a deliberate
choice is possible.

## Before writing any UI code

1. Name a concrete 4–6 color palette as hex values (background, surface,
   text, accent, accent-secondary). Do not invent this at code time — decide
   it first, then derive every color in the UI from it.
2. Pick two typefaces with real character: one display face used with
   restraint for headings, one body face. Never default to Inter, Roboto, or
   system-ui alone — pair something with personality.
3. Describe the layout concept in one sentence before building it. If it's
   "centered hero, headline, subtext, two buttons" — stop and pick something
   else.
4. Name the single signature element this screen will be remembered by.

## Hard bans — never do these unless the brief explicitly asks for them

- Purple-to-blue gradients on buttons, backgrounds, or text
- Generic drop-shadow rounded cards with no other distinguishing style
- Centered hero: headline → subtext → two pill buttons → icon grid
- Numbered feature markers (01 / 02 / 03) unless the content is a real
  ordered sequence
- Emoji used as functional icons — use a real icon set instead
- Every corner radius set to the same rounded value everywhere

## Structure and restraint

- Structural devices (dividers, labels, eyebrows, numbering) must encode
  something true about the content, not decorate it.
- Spend visual boldness in exactly one place (the signature element). Keep
  everything around it quiet and disciplined.
- Animation only where it serves the subject — a deliberate page-load
  sequence or hover interaction beats scattered motion everywhere.
- Build to a quality floor without being asked: responsive to mobile,
  visible keyboard focus states, respects reduced-motion preferences.

## Copy

- Write from the user's side of the screen — name things by what people do,
  not by internal system/implementation terms.
- Active voice. A button's label should match the toast/confirmation that
  follows it exactly.
- No filler, no generic marketing tone ("Unlock the power of...").

## Self-check before finishing

Ask: if I ran this same prompt on a completely different project, would I
land on visually the same output? If yes, revise the palette, type, or
layout choice until the answer is no.