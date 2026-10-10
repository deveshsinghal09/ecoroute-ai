# Smartwatch health preview

SmartwatchHealth.jsx is a reusable React presentation component in the existing Wearable panel.
Physical design adapted from Sparsh Gupta / sparshcodes, SmartWatch (PURE CSS):
https://codepen.io/sparshgupta007/pen/abJZoVx
HTML and CSS were inspected directly from the CodePen page on 2026-10-10. The raw .css URL
returned 403; the page itself exposed the source successfully. No remote image is used.
Public Pen licensing: https://blog.codepen.io/legal/terms-of-service/ (MIT).

Retained structure: watch-container, watch, dial, reflection, home button, dial-face,
branding, top/bottom straps, buckle/shadows, keeper, molded lugs and perforations.
Changes: prefixed selectors, doubled case dimensions before responsive scaling, shortened
strap lengths for embedding, eight visible holes, EcoRoute wordmark, interactive OLED face
instead of the source's static face image. This is an adaptation, not a pixel-identical copy
or a representation of the user's actual Noise model. CSS perspective supplies depth; no Three.js.

Usage: import SmartwatchHealth from './SmartwatchHealth'; render <SmartwatchHealth/>.
The exported demoHealth object contains all placeholder health values. A data prop can replace
that object with another complete presentation dataset. This component currently ALWAYS labels
values demo: integrating actual API values requires explicit provenance/availability handling,
consent and authorization first. Scores are not derived from telemetry or medically validated.
No wearable API calls, device enrollment, consent changes, or cloud resources are added.
The pre-existing authorized latest-measurement control remains below the preview.

Screens: Home, Heart health, Sleep, Activity. Click the dots or arrows; swipe horizontally;
focus the screen and use Left/Right/Home; side crown returns Home. Current time is device-local.
Reduced-motion disables pulse, entrance and perspective transitions. Styles use swh prefixes.
React owns only local screen/time state; the clock interval is cleaned up on unmount.

Verification: npm run build:frontend; 10 existing dashboard browser tests passed. Two new watch
browser tests initially caught pointer capture intercepting dot clicks and buckle bounds; both
were fixed and the two tests passed on rerun. Tests cover four screens, pointer swipe, keyboard,
crown, demo labels, disabled live read, mobile strap bounds and reduced motion. Screenshots
reviewed at desktop size. No live hardware test or cloud deployment performed.
