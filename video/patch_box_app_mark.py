#!/usr/bin/env python3
"""WS Film, ecosystem v6 box (round 5, approved 28 Nov 2026): swap every old «WS» mark on a VibeCAD box GLB for the WS·TECH
app mark (projects/ecosystem-v6/assets/wm.svg, the square the film shows on screen),
clipped to the same rounded square as the film's #wm container (radius 14/64 of the side).
Square side = the old mark's height, at the old top-left corner, so it covers the old WS block.

Based on patch_box_mark.py:

The Field Ops box the film turns (footage/ws-fieldops) came from the Figma variant
20260718-114821-figma, whose Figma SVG is no longer on disk, so the box cannot be
regenerated from its template without losing the Figma edits. This tool works on the
GLB itself and leaves every other pixel of the art alone:

  1. Diffuse (baseColor, 6000 x 3636, 12 px/mm): each old mark is erased by copying
     clean board from the same face, shifted by whole periods of the 8 mm board grid
     (96 px), so the grid and the face gradient carry on underneath. The official mark
     (/root/ws-assets/logos/svg/ws-tech-{white,dark}.svg, rasterised as is, never
     retyped or traced) is then laid in at the old mark's ink box: same top-left corner
     and same width, because the top of the WS·TECH mark is the old «WS» lockup drawn
     to the same proportions; «TECH» hangs below it.
  2. Normal + ORM (1500 x 909): only the spine and right-side marks were embossed.
     Those areas are rebuilt with VibeCAD's own height_to_maps() from a height map
     holding the new marks at the same strength (EMBOSS-73), then the same two
     half-size steps as make_lite.py. The board grain uses the same seed, so the
     patch matches its surroundings to within a level or two.

Usage: patch_box_app_mark.py <source box-lite.glb> <out dir>
Writes <out dir>/box-lite.glb plus the four maps it built, for checking.
"""
import os, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
import pygltflib
from PIL import Image, ImageDraw

sys.path.insert(0, "/root/ws-vibecad")
import import_svg  # noqa: E402  (VibeCAD's own relief → normal/ORM maths)

WM = Path("/root/ws-assets/video/projects/ecosystem-v6/assets/wm.svg")
RADIUS = 14 / 64            # film #wm: border-radius 14px on a 64px square
S = 12                      # diffuse px per mm
GRID = 8 * S                # board grid period in px
FACES = {                   # atlas faces in diffuse px (gen_art.py REGIONS x 12)
    "spine": (0, 0, 720, 2916), "front": (720, 0, 3000, 2916),
    "right": (3000, 0, 3720, 2916), "back": (3720, 0, 6000, 2916),
    "top": (0, 2916, 2280, 3636), "bottom": (2280, 2916, 4560, 3636),
}
# Round 5: every mark on the cover. erase = old ink box (x0, y0, x1, y1, inclusive, measured on
# the variant's atlas); sq = new square (x, y, side) from the alignment rule:
#   beside text  -> side = text block height (cap top of first line to baseline of last line),
#                   centred on it, original gap between mark and text kept;
#   on its own   -> centred on the round 3 WS·TECH lockup's box, side = that lockup's height;
#   front lockup -> stacked above «FIELD OPS»: left edge on the FIELD OPS column, side = old
#                   lockup height, so the gap down to FIELD OPS is unchanged.
MARKS = [
    dict(name="front lockup", face="front",  erase=(888, 180, 1181, 491),   sq=(888, 180, 312),   emboss=73),
    dict(name="spine",        face="spine",  erase=(72, 96, 233, 206),      sq=(67, 96, 170),     emboss=73),
    dict(name="right",        face="right",  erase=(3072, 96, 3233, 206),   sq=(3067, 96, 170),   emboss=73),
    dict(name="front band",   face="front",  erase=(840, 2670, 1019, 2792), sq=(916, 2713, 104),  emboss=None),
    dict(name="back band",    face="back",   erase=(5640, 2670, 5819, 2792),sq=(5640, 2702, 111), emboss=None),
    dict(name="top",          face="top",    erase=(72, 3240, 299, 3395),   sq=(116, 3224, 184),  emboss=None),
    dict(name="bottom",       face="bottom", erase=(4248, 3132, 4415, 3246),sq=(4248, 3198, 136), emboss=None),
]
PAD = 8                     # anti-aliasing margin around the old ink


# Review guides (GUIDES=1 only, never for the real box): magenta = what the square is aligned to
# (text block cap top and baseline, the round 3 lockup's box, the FIELD OPS column); yellow = centre line.
MAG, YEL, LW = (255, 45, 149), (255, 212, 0), 4
GUIDES = [
    ("h", 180, 860, 1240, MAG), ("h", 491, 860, 1240, MAG), ("h", 648, 860, 1760, MAG), ("v", 888, 150, 1160, MAG),
    ("h", 335.5, 860, 1240, YEL),
    *[g for x0, y0, x1, y1 in [(72, 96, 232, 265), (3072, 96, 3232, 265)] for g in
      [("h", y0, x0, x1, MAG), ("h", y1, x0, x1, MAG), ("v", x0, y0, y1, MAG), ("v", x1, y0, y1, MAG),
       ("h", (y0 + y1) / 2, x0 - 30, x1 + 30, YEL), ("v", (x0 + x1) / 2, y0 - 30, y1 + 30, YEL)]],
    *[g for ya, yb, xa, xb in [(2713, 2816, 892, 2172), (2702, 2812, 4464, 5774), (3224, 3407, 92, 1875), (3198, 3333, 3121, 4407)]
      for g in [("h", ya, xa, xb, MAG), ("h", yb, xa, xb, MAG), ("h", (ya + yb) / 2, xa, xb, YEL)]],
]


def draw_guides(rgb):
    for kind, c, a, b, col in GUIDES:
        c0 = int(round(c - LW / 2))
        if kind == "h":
            rgb[c0:c0 + LW, int(a):int(b)] = col
        else:
            rgb[int(a):int(b), c0:c0 + LW] = col


def raster(side, tmp):
    """wm.svg as delivered, rasterised at side x side, alpha = film's rounded-square clip."""
    out = Path(tmp) / f"wm-{side}.png"
    subprocess.run(["rsvg-convert", str(WM), "-w", str(side), "-h", str(side), "-o", str(out)], check=True)
    art = np.asarray(Image.open(out).convert("RGBA")).astype(np.float32) / 255.0
    ss = 8                                   # supersampled, anti-aliased corner mask
    m = Image.new("L", (side * ss, side * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, side * ss - 1, side * ss - 1], radius=RADIUS * side * ss, fill=255)
    mask = np.asarray(m.resize((side, side), Image.LANCZOS)).astype(np.float32) / 255.0
    art[..., 3] *= mask
    return art


def erase(rgb, m):
    """Fill the old ink box with clean board from the same face, whole grid periods away."""
    fx0, fy0, fx1, fy1 = FACES[m["face"]]
    ex0, ey0, ex1, ey1 = m["erase"]
    x0, y0, x1, y1 = ex0 - PAD, ey0 - PAD, ex1 + 1 + PAD, ey1 + 1 + PAD
    # board colour = the median of a ring just outside the box
    ring = np.concatenate([rgb[y0 - 12:y0, x0:x1].reshape(-1, 3), rgb[y1:y1 + 12, x0:x1].reshape(-1, 3),
                           rgb[y0:y1, x0 - 12:x0].reshape(-1, 3), rgb[y0:y1, x1:x1 + 12].reshape(-1, 3)])
    board = np.median(ring, axis=0)
    shifts = sorted(((dx, dy) for dx in range(-30, 31) for dy in range(-12, 13) if (dx, dy) != (0, 0)),
                    key=lambda d: (abs(d[1]), abs(d[0])))   # prefer sideways: keeps the vertical gradient
    for dx, dy in shifts:
        sx0, sy0 = x0 + dx * GRID, y0 + dy * GRID
        sx1, sy1 = sx0 + (x1 - x0), sy0 + (y1 - y0)
        if sx0 < fx0 + 6 or sy0 < fy0 + 6 or sx1 > fx1 - 6 or sy1 > fy1 - 6:
            continue
        src = rgb[sy0:sy1, sx0:sx1]
        if np.abs(src - board).sum(-1).max() <= 30:     # clean board: grid lines only
            # the face carries a gradient: fit a plane to (target ring - source ring) and add it,
            # so the patch meets its surroundings without a step
            R = 16
            yy, xx = np.mgrid[y0 - R:y1 + R, x0 - R:x1 + R]
            ring = ~((yy >= y0) & (yy < y1) & (xx >= x0) & (xx < x1))
            d = rgb[y0 - R:y1 + R, x0 - R:x1 + R][ring] - rgb[sy0 - R:sy1 + R, sx0 - R:sx1 + R][ring]
            A = np.stack([np.ones(ring.sum()), xx[ring] - x0, yy[ring] - y0], 1)
            ok = np.abs(d).sum(-1) < 24                  # leave out ink (either ring may touch a mark)
            coef = np.linalg.lstsq(A[ok], d[ok], rcond=None)[0] if ok.sum() > 200 else np.zeros((3, 3))
            py, px = np.mgrid[0:y1 - y0, 0:x1 - x0]
            rgb[y0:y1, x0:x1] = src + coef[0] + px[..., None] * coef[1] + py[..., None] * coef[2]
            return (dx, dy)
    raise SystemExit(f"no clean board found for the {m['name']} mark")


def place(rgb, m, tmp):
    x, y, side = m["sq"]
    art = raster(side, tmp)
    a = art[..., 3:4]
    reg = rgb[y:y + side, x:x + side]
    rgb[y:y + side, x:x + side] = reg * (1 - a) + art[..., :3] * 255.0 * a
    return side, side


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    g = pygltflib.GLTF2().load(str(src))
    blob = g.binary_blob()
    mat = g.materials[0]
    tex_img = lambda ti: g.textures[ti.index].source
    idx = dict(base=tex_img(mat.pbrMetallicRoughness.baseColorTexture), normal=tex_img(mat.normalTexture),
               mr=tex_img(mat.pbrMetallicRoughness.metallicRoughnessTexture), occ=tex_img(mat.occlusionTexture))

    def load(i):
        bv = g.bufferViews[g.images[i].bufferView]
        p = out / f"_src{i}.png"
        p.write_bytes(blob[bv.byteOffset:bv.byteOffset + bv.byteLength])
        return Image.open(p)

    base = load(idx["base"]).convert("RGB")
    rgb = np.asarray(base).astype(np.float32)
    with tempfile.TemporaryDirectory() as tmp:
        for m in MARKS:
            dx, dy = erase(rgb, m)
            w, h = place(rgb, m, tmp)
            print(f"{m['name']:<11} erased from ({dx:+d},{dy:+d}) grid periods · wm {w}x{h}px "
                  f"({w / S:.1f} x {h / S:.1f} mm) at {m['sq'][0] / S:.2f},{m['sq'][1] / S:.2f} mm")
        if os.environ.get("GUIDES"):
            draw_guides(rgb)
        Image.fromarray(np.clip(rgb + 0.5, 0, 255).astype(np.uint8)).save(out / "diffuse.png")

        # relief: height map with the embossed marks only (+ one full-height block outside
        # every face so the AO edge normalisation matches the original foil-led maps)
        height = np.zeros((3636, 6000), np.float32)
        for m in MARKS:
            if m["emboss"]:
                x, y, w = m["sq"]; h = w
                a = raster(w, tmp)[..., 3]
                height[y:y + h, x:x + w] = np.maximum(height[y:y + h, x:x + w], a * round(255 * m["emboss"] / 100))
        height[3100:3300, 4700:4900] = 255
        rel = out / "_relief"; rel.mkdir(exist_ok=True)
        import_svg.height_to_maps(Image.fromarray(height.astype(np.uint8)), rel)
    half = lambda im: im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
    n_new = np.asarray(half(Image.open(rel / "normal.png")).convert("RGB"))
    o_new = np.asarray(half(Image.open(rel / "orm.png")).convert("RGB"))
    normal = np.asarray(load(idx["normal"]).convert("RGB")).copy()
    orm = np.asarray(load(idx["mr"]).convert("RGB")).copy()
    k = normal.shape[1] / rgb.shape[1]           # 1500 / 6000
    for m in MARKS:
        if not m["emboss"]:
            continue
        sx, sy, sd = m["sq"]; ex0, ey0, ex1, ey1 = m["erase"]
        bx0, by0, bx1, by1 = min(sx, ex0), min(sy, ey0), max(sx + sd, ex1 + 1), max(sy + sd, ey1 + 1)
        x0, y0 = int((bx0 - 60) * k), int((by0 - 60) * k)
        x1, y1 = int(np.ceil((bx1 + 60) * k)), int(np.ceil((by1 + 60) * k))
        normal[y0:y1, x0:x1] = n_new[y0:y1, x0:x1]
        orm[y0:y1, x0:x1] = o_new[y0:y1, x0:x1]
    Image.fromarray(normal).save(out / "normal.png")
    Image.fromarray(orm).save(out / "orm.png")

    # rebuild the GLB: same JSON, geometry and samplers; only the image bytes change
    new_bytes = {idx["base"]: (out / "diffuse.png").read_bytes(), idx["normal"]: (out / "normal.png").read_bytes(),
                 idx["mr"]: (out / "orm.png").read_bytes(), idx["occ"]: (out / "orm.png").read_bytes()}
    parts, off = [], 0
    for i, bv in enumerate(g.bufferViews):
        img = next((k_ for k_, im in enumerate(g.images) if im.bufferView == i), None)
        data = new_bytes[img] if img in new_bytes else blob[bv.byteOffset:bv.byteOffset + bv.byteLength]
        pad = (-off) % 4
        parts.append(b"\0" * pad); off += pad
        bv.byteOffset, bv.byteLength = off, len(data)
        parts.append(data); off += len(data)
    g.buffers[0].byteLength = off
    g.set_binary_blob(b"".join(parts))
    g.save_binary(str(out / "box-lite.glb"))
    for p in out.glob("_src*.png"):
        p.unlink()
    print(f"GLB OK → {out / 'box-lite.glb'} ({(out / 'box-lite.glb').stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
