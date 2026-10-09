---
name: EcoRoute City Observatory
colors:
  charcoal: "#25292b"
  silver: "#bac2c9"
  frost: "#eef0ef"
  orange: "#ff702d"
  ink: "#202628"
  muted: "#525e63"
typography:
  display:
    fontFamily: "Manrope, Arial, sans-serif"
  body:
    fontFamily: "Manrope, Arial, sans-serif"
  utility:
    fontFamily: "Consolas, monospace"
---
## Overview
User-pinned cinematic city dashboard. Operate mode: planning a route is always one action away.
The memorable element is a real WebGL transit plaza with porcelain buildings and orange trams.
## Colors
Cool silver canvas, charcoal sidebar/navigation, frost panels and a single transport-orange accent.
## Typography
Manrope locally bundled; large restrained display line on the canvas, readable compact UI labels.
Monospace only for units and coordinates.
## Layout
Desktop: 184px left instrument rail, horizontal pill navigation, viewport-filling 3D city, right
planner. Mobile: compact header, city viewport, then planner and metrics in normal document flow.
## Elevation & Depth
Depth comes primarily from the actual 3D city. Translucent panels follow the supplied reference;
text panels have opaque-enough backgrounds for readability. One soft offset panel shadow.
## Shapes
Broad rounded city frame and reference-inspired instrument cards; pill controls, fine separators.
## Components
Top navigation changes useful views. City controls orbit/zoom/reset and pause motion. Route view
uses actual GeoJSON. Historical data badge persists; live mode explicitly requires authenticated API.
## Do's and Don'ts
Do preserve reduced motion and a WebGL fallback. Do label the city illustrative. Never call
historical pollution live, decorate with fake metrics or imply the watch is connected.

## Reference correction: sky and material detail

The user rejected the initial pale city. Use slate-blue cloud sky, darker blue glass and asphalt,
porcelain structural frames and restrained warm transit accents. Camera-centered sky geometry avoids
far-plane clipping at any allowed orbit. Keep facade glazing, physical floor bands and articulated
rounded trams readable. Original procedural scene remains stylized, not a photoreal video replica.
