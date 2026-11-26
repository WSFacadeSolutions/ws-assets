#!/usr/bin/env python3
"""WS Film — swap the old «WS» mark on a VibeCAD box GLB for the official WS·TECH mark.

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

Usage: patch_box_mark.py <source box-lite.glb> <out dir>
Writes <out dir>/box-lite.glb plus the four maps it built, for checking.
"""
import subprocess, sys, tempfile
from pathlib import Path

import numpy as np
import pygltflib
from PIL import Image

sys.path.insert(0, "/root/ws-vibecad")
import import_svg  # noqa: E402  (VibeCAD's own relief → normal/ORM maths)

LOGOS = Path("/root/ws-assets/logos/svg")
S = 12                      # diffuse px per mm
GRID = 8 * S                # board grid period in px
FACES = {                   # atlas faces in diffuse px (gen_art.py REGIONS x 12)
    "spine": (0, 0, 720, 2916), "front": (720, 0, 3000, 2916),
    "right": (3000, 0, 3720, 2916), "back": (3720, 0, 6000, 2916),
    "top": (0, 2916, 2280, 3636), "bottom": (2280, 2916, 4560, 3636),
}
# Old «WS» mark ink boxes (x, y, width in diffuse px, measured on the variant's atlas),
# the face they sit on, which official file suits the board, and emboss strength.
MARKS = [
    dict(name="spine",       face="spine",  x=72,   y=96,   w=162, file="ws-tech-white.svg", emboss=73),
    dict(name="right",       face="right",  x=3072, y=96,   w=162, file="ws-tech-white.svg", emboss=73),
    dict(name="front band",  face="front",  x=840,  y=2670, w=180, file="ws-tech-dark.svg",  emboss=None),
    dict(name="back band",   face="back",   x=5640, y=2670, w=180, file="ws-tech-dark.svg",  emboss=None),
    dict(name="top",         face="top",    x=72,   y=3240, w=228, file="ws-tech-white.svg", emboss=None),
    dict(name="bottom",      face="bottom", x=4248, y=3132, w=168, file="ws-tech-white.svg", emboss=None),
]
OLD_ASPECT = 294 / 430      # WS_SQUARE_*.svg viewBox
NEW_ASPECT = 81 / 77        # ws-tech-*.svg viewBox
PAD = 8                     # anti-aliasing margin around the old ink


def raster(svg, w, h, tmp):
    out = Path(tmp) / f"{svg}-{w}x{h}.png"
    subprocess.run(["rsvg-convert", str(LOGOS / svg), "-w", str(w), "-h", str(h), "-o", str(out)], check=True)
    return np.asarray(Image.open(out).convert("RGBA")).astype(np.float32) / 255.0


def erase(rgb, m):
    """Fill the old ink box with clean board from the same face, whole grid periods away."""
    fx0, fy0, fx1, fy1 = FACES[m["face"]]
    h = round(m["w"] * OLD_ASPECT)
    x0, y0, x1, y1 = m["x"] - PAD, m["y"] - PAD, m["x"] + m["w"] + PAD, m["y"] + h + PAD
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
            rgb[y0:y1, x0:x1] = src
            return (dx, dy)
    raise SystemExit(f"no clean board found for the {m['name']} mark")


def place(rgb, m, tmp):
    w = m["w"]
    h = round(w * NEW_ASPECT)
    art = raster(m["file"], w, h, tmp)
    a = art[..., 3:4]
    reg = rgb[m["y"]:m["y"] + h, m["x"]:m["x"] + w]
    rgb[m["y"]:m["y"] + h, m["x"]:m["x"] + w] = reg * (1 - a) + art[..., :3] * 255.0 * a
    return w, h


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
            print(f"{m['name']:<11} erased from ({dx:+d},{dy:+d}) grid periods · WS·TECH {w}x{h}px "
                  f"({w / S:.1f} x {h / S:.1f} mm) at {m['x'] / S:.1f},{m['y'] / S:.1f} mm · {m['file']}")
        Image.fromarray(np.clip(rgb + 0.5, 0, 255).astype(np.uint8)).save(out / "diffuse.png")

        # relief: height map with the embossed marks only (+ one full-height block outside
        # every face so the AO edge normalisation matches the original foil-led maps)
        height = np.zeros((3636, 6000), np.float32)
        for m in MARKS:
            if m["emboss"]:
                w = m["w"]; h = round(w * NEW_ASPECT)
                a = raster(m["file"], w, h, tmp)[..., 3]
                height[m["y"]:m["y"] + h, m["x"]:m["x"] + w] = np.maximum(
                    height[m["y"]:m["y"] + h, m["x"]:m["x"] + w], a * round(255 * m["emboss"] / 100))
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
        h = round(m["w"] * NEW_ASPECT)
        x0, y0 = int((m["x"] - 60) * k), int((m["y"] - 60) * k)
        x1, y1 = int(np.ceil((m["x"] + m["w"] + 60) * k)), int(np.ceil((m["y"] + h + 60) * k))
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
