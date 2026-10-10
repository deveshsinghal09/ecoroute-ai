# Original EcoRoute Pulse wearable preview

This design is authored from scratch. No watch template, UI kit, CodePen code, external 3D model,
remote texture, or branded watch geometry is used. This concept is not a Noise hardware replica.

Files in frontend/src/wearable:
- SmartwatchShowcase.tsx: reusable preview, lazy 3D loading, accessible navigation, local settings,
  reduced-motion/visibility tracking, WebGL error fallback and demo disclosures.
- WatchScene.tsx: procedural bevel/extrusion geometry, perforated straps, textured OLED display,
  metallic rim/crown, lighting, floating/rotation behavior and camera fitting.
- watchScreen.ts: original seven-screen canvas artwork, clipped by rounded display geometry.
- watchData.ts: one demo data object, typed props, screen names and accessible metric summaries.
- watch.css: scoped visual styles and prefixed Tailwind utilities; no global Preflight reset.

Home shows local time/date, health, heart, steps, calories, sleep, oxygen and demo battery.
Heart has a pulse animation and illustrative chart; Activity has three movement rings; Sleep
and Wellness show placeholders. Notifications contains example cards only. Settings changes
screen theme, brightness and preview cards. Tap/swipe the display, use navigation controls or
click the modeled crown to return home. Equivalent keyboard-accessible controls sit below it.
The existing registered-device/latest-reading controls remain below the preview.

All scores, oxygen, hydration, sleep, battery and health values are invented DEMO placeholders,
not fabricated measurements represented as real data. They are never sent to telemetry APIs.
Data props may replace the demo object for another preview. Connecting real responses later
requires explicit availability/provenance/consent handling and changing the demo labeling safely;
this component does not automatically turn an API response into medically validated scores.

Performance: lazy-loaded Three/Fiber chunk (~245 kB gzip), DPR capped at 1.5, no postprocessing,
no network model assets, static geometries/textures disposed on unmount. Off-screen, hidden-tab,
reduced-motion and paused states use demand rendering. Local time refreshes every 15 seconds.
Only the heart screen repaints its pulse while animating. Full model camera fit adapts to container.
WebGL loss or startup failure renders an explicitly static original SVG fallback; DOM controls
and text summaries still work. The sidebar scrolls independently to retain connection controls.

Verified: build, 6 unit tests, 14 browser tests across the full run and targeted follow-up,
including actual WebGL render on desktop/mobile, swipe/tap, modeled crown, theme/brightness,
notification preview toggle, motion pause/reduced motion and WebGL-denied fallback. Screenshot
inspection fixed screen UV mapping under React Strict Mode. No paid services or hardware tested.

Commands:
    npm --prefix frontend ci
    npm run dev
    npm run build:frontend
    npm --prefix frontend test
    cd frontend
    npx playwright test

Library compatibility checked against official docs:
https://r3f.docs.pmnd.rs/getting-started/installation (Fiber 9 + React 19)
https://tailwindcss.com/docs/installation/using-vite (Vite plugin)

Readability update: case/display scale increased 45%; full straps remain in the camera frame.
Screen texture is now 1024x1200 with DPR capped at 2, minimum 25px logical texture text, stronger
contrast, and a more front-facing viewing angle. Wearable width is now 460px on desktop. Build
and four watch tests passed; desktop screenshot reviewed.
