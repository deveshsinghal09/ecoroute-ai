# Cinematic city artwork

File: ecoroute-cinematic-city.png
Created 2026-10-10 using the built-in image_gen tool, not a CLI/API-key workflow.
User-provided screenshot was used as a composition/material reference. This is generated
illustrative architecture, not measured data or a photograph of Delhi. Image includes no UI;
labels, controls, route data and interactions are real frontend elements. Original generated
output remains in the local Codex generated_images directory; this copy is tracked for deployment.

## Generation prompt

Create a high quality wide landscape 16:9 cinematic photorealistic architectural 3D city render for a web dashboard. Use the attached reference image as a very close composition, material, camera and lighting guide. The image is ONLY the city artwork, no UI, no text, no letters, no icons, no pins, no logos, no border. Match the low slightly elevated camera, central glass transit station with gently arched silver roof, exquisite structural mullions, visible warm amber lit lobby interior and escalators. Surround it with varied low white modern buildings and a few tall slender towers with dark metallic vertical ribs and restrained orange vertical accents. Two highly detailed white-and-charcoal articulated trams with vivid orange door panels on curving tracks crossing the foreground diagonally; realistic windows, articulated joints and headlights. Reflective polished wet silver pavement with clear reflections of trains and warm linear street lights. Realistic finely textured dark green trees, street lamps, small pedestrians for scale, one white car. Cool slate cloudy sky in the upper third, subtle cinematic haze at horizon. Architectural miniature photography with a tilt shift depth of field: sharp center station and middle tram, subtly blurred extreme foreground corners and distant buildings. Palette graphite, porcelain white, silver grey and amber orange. No blocky low-poly geometry, no cartoon trees, no blue all-glass skyscraper wall. Preserve generous reflective empty pavement lower left for our real HTML headline. The building and train detail and reflective lighting should be as close to the reference quality as possible.

## Animated layers

Built-in image_gen edits of the original artwork, 2026-10-10:
- ecoroute-city-clear.png: remove all three trams and their reflections; preserve camera,
  station, sky, buildings, trees, lights and framing; restore continuous empty rails and paving.
- ecoroute-tram.png: isolate/recreate the middle white/charcoal articulated tram with orange
  doors on a transparent background, matching its three-quarter side perspective and roughly
  9-degree rail baseline. No scenery, text or ground reflections. Reflections are composited in SVG.

These decorative layers are not a train tracking feed or geographic model. No generation service
is called at runtime. The original combined artwork remains tracked as asset provenance.
