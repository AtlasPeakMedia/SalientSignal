---
aliases: [SalientSignal Icon Prompt, SalientSignal App Icon]
tags: [apex, business, salientsignal, design, icon]
created: 2026-04-13
---

# SalientSignal App Icon — Gemini Prompt

> [!abstract] Purpose
> Prompt for generating the SalientSignal app icon / favicon / brand mark. SalientSignal is a foreign media intelligence platform that monitors state-run media across 151+ countries, tracking domestic vs. international messaging divergence. The icon should communicate "global signal intelligence" and "media monitoring" while feeling serious and analytical. Dark base with teal accent matching the live globe UI.

---

## Primary Concept

**Send this to Gemini:**

```
A premium app icon, 1024x1024 pixels, square format with rounded
corners following Apple's iOS 18 icon guidelines. The composition is
centered and minimal.

Subject: A stylized abstract globe rendered as a wireframe sphere
made of thin latitude and longitude lines. The globe is viewed from
a slight angle (roughly 20 degrees from front-facing, tilted to show
the Atlantic/European hemisphere). The wireframe lines are rendered
in teal #00E5CC at approximately 40% opacity, creating a subtle
grid. One section of the globe — roughly covering the Middle East
and Central Asia region — glows brighter, with its wireframe lines
at full 100% teal opacity and a soft radial glow emanating outward,
as if that region is "lighting up" with detected signal activity.
2-3 additional small bright dots (teal, full opacity, ~3% of icon
width) are scattered on other parts of the globe, suggesting active
monitoring points.

Background: A very dark near-black background #0A0E14 with a subtle
radial gradient — slightly lighter #111822 at the center behind the
globe, darker at the edges. The darkness makes the teal wireframe
and glow points pop.

Depth cues: The wireframe lines on the far side of the globe are
rendered at lower opacity (~15%) than the near side (~40%), creating
a natural 3D sphere effect. The glowing region has a soft halo that
bleeds slightly onto the dark background. No hard shadows.

Texture: A barely-perceptible noise grain overlay at approximately
8% opacity across the entire icon, consistent with APM brand texture.

Style: Analytical, serious, intelligence-grade, modern. Should feel
like a tool used by analysts and researchers, not a consumer social
app. Think of the aesthetic of Bloomberg Terminal, Palantir, or
Recorded Future — data-dense professional tooling rendered as a
clean icon. The wireframe globe must remain recognizable at 60x60
pixels (the bright glow region is the key landmark at small sizes).

What to avoid: No literal newspaper or news feed icons, no speech
bubbles, no satellite dishes, no radar screens, no crosshairs or
targeting reticles, no flags, no country outlines, no text or
letters, no literal signal waves. No heavy skeuomorphism. No brand
logos. No bright colors beyond teal — this is a dark, serious tool.

Deliver as: PNG, 1024x1024, no alpha channel, no rounded corner mask.
```

---

## Alternative Concept (Backup)

```
A premium app icon, 1024x1024 pixels, square format with rounded
corners.

Subject: Two overlapping signal pulse lines rendered horizontally
across the center of the icon — one in teal #00E5CC (representing
international messaging) and one in a muted warm amber #C4956A
(representing domestic messaging). The two lines mostly track each
other but DIVERGE visibly in one section near the right third of
the icon, with the teal line spiking upward and the amber line
dropping — visualizing the "messaging divergence" that is
SalientSignal's core analytical concept. The lines are smooth
bezier curves, not jagged, rendered with a subtle glow.

Background: Near-black #0A0E14 with subtle horizontal grid lines
at 3% opacity, suggesting a data dashboard.

Depth cues: Each line has a faint glow matching its color. The
divergence point has a slightly brighter background glow.

Texture: Noise grain overlay at 8% opacity.

Style: Dashboard-analytical, data visualization as icon. The
divergence IS the signal.

What to avoid: No text, no globe, no literal media imagery.

Deliver as: PNG, 1024x1024, no alpha channel.
```

---

## Evaluation Criteria

1. **Reads clearly at 60x60 pixels** — the bright glow region or divergence point must be visible
2. **Distinct silhouette** — wireframe globe or diverging lines recognizable when squinting
3. **Uses dark base + teal #00E5CC accent** (matches the live salientsignal.com globe)
4. **Communicates "global monitoring" or "signal detection"** without being literal
5. **Feels analytical and intelligence-grade**, not consumer or social
6. **Consistent with the live product aesthetic** — dark background, teal accents, grain texture
7. **No text, no flags, no news imagery, no radar**
8. **Professional enough for .mil users** — this app's free tier targets military/IC analysts

---

## Related Files

- [[SalientSignal-Project]] — Product vision
- [[iOS-Premium-Design-Reference]] — APM design language
