"""Compose the generated silhouette and exact Operation Napalm outlines as SVG.

Developer-only dependency: pip install fonttools. The raster is embedded unchanged.
"""
from pathlib import Path
import base64
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "web" / "assets"


def typeset(font, text, x, y, max_width, height):
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    cursor = 0
    paths = []
    bounds = []
    for char in text:
        name = cmap[ord(char)]
        glyph = glyphs[name]
        pen = SVGPathPen(glyphs)
        glyph.draw(TransformPen(pen, (1, 0, 0, 1, cursor, 0)))
        paths.append(pen.getCommands())
        bp = BoundsPen(glyphs)
        glyph.draw(TransformPen(bp, (1, 0, 0, 1, cursor, 0)))
        if bp.bounds:
            bounds.append(bp.bounds)
        cursor += glyph.width
    left = min(b[0] for b in bounds)
    bottom = min(b[1] for b in bounds)
    right = max(b[2] for b in bounds)
    top = max(b[3] for b in bounds)
    scale = min(max_width / (right - left), height / (top - bottom))
    dx, dy = x - left * scale, y + top * scale
    return f'<path fill="white" transform="translate({dx:.4f} {dy:.4f}) scale({scale:.6f} {-scale:.6f})" d="{" ".join(paths)}"/>'


def main():
    font = TTFont(ASSETS / "fonts" / "operation-napalm" / "OperationNapalm-Regular.ttf")
    raster = base64.b64encode((ASSETS / "brand-avatar.png").read_bytes()).decode()
    # The illustration is laid out on a 1254-square canvas; the chest is left
    # clear of the extended hand, so both lines remain inside the black torso.
    letters = typeset(font, "cine", 180, 910, 420, 105)
    letters += typeset(font, "(cas) phile.", 180, 1040, 500, 105)
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1254 1254" '
           'role="img" aria-labelledby="title"><title id="title">Cine (cas) phile. — '
           'two-finger gun silhouette, Operation Napalm lettering</title>'
           f'<image width="1254" height="1254" href="data:image/png;base64,{raster}"/>'
           f'{letters}</svg>')
    (ASSETS / "brand-avatar.svg").write_text(svg, encoding="utf-8")
    print("Saved web/assets/brand-avatar.svg using original Operation Napalm glyphs")


if __name__ == "__main__":
    main()
