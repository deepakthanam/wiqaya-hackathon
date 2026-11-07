"""Wiqaya brand asset generator: one master geometry -> all five assets."""
import io, os, sys
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
import cairosvg

FONTDIR = "/home/claude/brand/fontpkg/x/package/files/"
OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/brand/out"
os.makedirs(OUT, exist_ok=True)

TEAL, TEAL_D, CORAL, INK, SAND, MUTED = "#0E6B68", "#0A4F4D", "#B5543F", "#2E2A26", "#F7F4F0", "#6B635B"


# ---------- master mark (256 x 256 design grid) ----------
def mark_shapes(arch=TEAL, adult=TEAL, child=CORAL, sw=26):
    """Protective arch (a doorway / canopy) sheltering an adult and a child."""
    return f'''
  <path d="M60 214 V118 A68 68 0 0 1 196 118 V214" fill="none" stroke="{arch}" stroke-width="{sw}"
        stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="110" cy="170" r="25" fill="{adult}"/>
  <circle cx="153" cy="180" r="16" fill="{child}"/>'''


def mark_svg(size=256):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 256 256">'
            f'<title>Wiqaya</title>{mark_shapes()}</svg>')


def tile_svg(size, radius_ratio=0.22, pad=0.16, simplified=False, rounded=True):
    """Solid teal tile with white mark (favicon / app icon)."""
    r = 256 * radius_ratio if rounded else 0
    s = 1 - 2 * pad
    o = 256 * pad
    if simplified:  # thicker strokes for 16 px legibility
        inner = mark_shapes(arch="#FFFFFF", adult="#FFFFFF", child="#F2B5A6", sw=34)
    else:
        inner = mark_shapes(arch="#FFFFFF", adult="#FFFFFF", child="#F2B5A6")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 256 256">'
            f'<rect width="256" height="256" rx="{r}" fill="{TEAL}"/>'
            f'<g transform="translate({o} {o}) scale({s})">{inner}</g></svg>')


# ---------- text to outlines ----------
def text_path(text, fontfile, size_px, x, baseline, rtl=False):
    data = open(fontfile, "rb").read()
    tt = TTFont(io.BytesIO(data))
    upem = tt["head"].unitsPerEm
    face = hb.Face(data)
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    if rtl:
        buf.direction = "rtl"
    hb.shape(font, buf, {"kern": True, "liga": True})
    gs = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    scale = size_px / upem
    pen = SVGPathPen(gs)
    cx = 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = order[info.codepoint]
        tp = TransformPen(pen, (scale, 0, 0, -scale, x + (cx + pos.x_offset) * scale,
                                baseline - pos.y_offset * scale))
        gs[name].draw(tp)
        cx += pos.x_advance
    return pen.getCommands(), cx * scale


LAT = FONTDIR + "ibm-plex-sans-arabic-latin-600-normal.ttf"
ARA = FONTDIR + "ibm-plex-sans-arabic-arabic-600-normal.ttf"


def logo_svg(w=1200, h=400, ink=INK, sub=MUTED, with_tag=False):
    # mark at left, 280 px tall, vertically centred
    m = 300
    my = (h - m) / 2
    tx = 40 + m + 36
    d_lat, wl = text_path("Wiqaya", LAT, 150, tx, 225)
    d_ara, wa = text_path("وقاية", ARA, 92, tx + 6, 330, rtl=True)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
             '<title>Wiqaya وقاية</title>',
             f'<g transform="translate(40 {my}) scale({m/256})">{mark_shapes()}</g>',
             f'<path d="{d_lat}" fill="{ink}"/>',
             f'<path d="{d_ara}" fill="{TEAL}"/>']
    parts.append('</svg>')
    return "".join(parts), tx + max(wl, wa)


def og_svg():
    W, H = 1200, 630
    d_lat, _ = text_path("Wiqaya", LAT, 120, 470, 270)
    d_ara, _ = text_path("وقاية", ARA, 70, 474, 360, rtl=True)
    d_t1, _ = text_path("Precision prevention & screening", LAT, 40, 474, 450)
    d_t2, _ = text_path("The right person, the right pathway, on time.", LAT, 30, 474, 505)
    d_badge, bw = text_path("Future Health Digital Innovation Challenge · Prototype", LAT, 22, 474, 572)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<rect width="{W}" height="{H}" fill="{SAND}"/>'
            f'<rect x="70" y="115" width="340" height="340" rx="72" fill="{TEAL}"/>'
            f'<g transform="translate(110 155) scale({260/256})">'
            f'{mark_shapes(arch="#FFFFFF", adult="#FFFFFF", child="#F2B5A6")}</g>'
            f'<path d="{d_lat}" fill="{INK}"/><path d="{d_ara}" fill="{TEAL}"/>'
            f'<path d="{d_t1}" fill="{INK}"/><path d="{d_t2}" fill="{MUTED}"/>'
            f'<path d="{d_badge}" fill="{MUTED}"/></svg>')


def write(name, svg):
    p = os.path.join(OUT, name)
    open(p, "w").write(svg)
    return p


def png(svg, name, w, h):
    p = os.path.join(OUT, name)
    cairosvg.svg2png(bytestring=svg.encode(), write_to=p, output_width=w, output_height=h)
    return p


# 1. mark
ms = mark_svg()
write("wiqaya-mark.svg", ms)
png(ms, "wiqaya-mark.png", 512, 512)
# 2. full logo (trim width to content)
ls, right = logo_svg()
W = int(right + 40)
ls, _ = logo_svg(w=W)
write("wiqaya-logo.svg", ls)
png(ls, "wiqaya-logo.png", W * 2, 800)
# 3. browser tab icon
png(tile_svg(512, simplified=True), "icon.png", 512, 512)
for s in (16, 32):
    png(tile_svg(s, simplified=True), f"preview-icon-{s}.png", s, s)
# 4. apple icon (square, solid, no transparency; iOS rounds corners itself)
png(tile_svg(180, rounded=False), "apple-icon.png", 180, 180)
# 5. link preview
og = og_svg()
write("opengraph-image.svg", og)
png(og, "opengraph-image.png", 1200, 630)
print("logo width", W)
