# Logo Cine (cas) phile.

Final asset: `web/assets/brand-avatar.svg`. The SVG embeds the generated silhouette unchanged and adds white Operation Napalm glyph outlines. `brand-avatar.png` is the editable silhouette base without lettering. `tools/build_brand.py` rebuilds the composition (developer dependency: fonttools).

The person is solid black on white. The head has no eyes, eyebrows or wrinkles. Index and middle fingers extend together toward the viewer, thumb upright, ring and little fingers folded. The white circular outlines around the extended fingertips have been removed.

Typography is typeset from the real Operation Napalm Regular TTF by GGBotNet, downloaded from https://www.1001fonts.com/operation-napalm-font.html. The font maps lowercase letters to its uppercase display style. Font files and CC0/Public Domain license notices are preserved in `web/assets/fonts/operation-napalm/`.

Built-in image generation/editing was used, with the user's original photograph as pose reference. Final edit prompt: “Remove both white circular/crescent outlines around the two forward-pointing fingertips, filling those arcs solid black. Keep the rounded external fingertip contours, thin separation between index/middle fingers, two-finger-gun gesture, solid featureless black head/torso, and white background. No text or other edits.” Exact font lettering was then composed as vector outlines: `cine` / `cas phile` in white inside the black torso.
