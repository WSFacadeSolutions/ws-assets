#!/usr/bin/env python3
"""Loopback-only standalone backend for the WS Film Mini-Premiere.

The production editor is hosted by WST038. This server implements the editor's
film-specific API directly against this checkout, so macOS can edit and render
without the VPS or the wider Ops application.
"""

from __future__ import annotations

import base64
import glob
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_file


FILM_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = FILM_DIR / "projects"
LOCAL_DIR = FILM_DIR / ".local"
LOG_DIR = LOCAL_DIR / "logs"
HOST = os.environ.get("WS_FILM_HOST", "127.0.0.1")
PORT = int(os.environ.get("WS_FILM_PORT", "8126"))
THEME_STOCK = {"petrol": "#1E2F38", "deep": "#0f1a20", "off": "#F5F2F0",
               "orange": "#FF9D27", "lilac": "#A490FF", "violet": "#6040cc"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
FIELD_VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}
SAFE_COMP_EXTS = {".html", ".js", ".css", ".json", ".svg", ".png", ".jpg",
                  ".jpeg", ".woff2", ".woff", ".ttf", ".wav", ".mp3", ".m4a",
                  ".aac", ".ogg", ".flac", ".mp4", ".webm"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 180 * 1024 * 1024  # base64 overhead on the 100 MB field slot
app.json.sort_keys = False  # preserve timeline/object order across a load-save round trip
RUNS: dict[str, subprocess.Popen] = {}
PATCHES: dict[str, subprocess.Popen] = {}


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=1)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def projects():
    out = []
    for path in sorted(PROJECTS_DIR.glob("*.json")):
        try:
            reg = json.loads(path.read_text(encoding="utf-8"))
            if not reg.get("name") or not reg.get("compositions"):
                continue
            reg["_dir"] = str((PROJECTS_DIR / reg.get("dir", reg["name"])).resolve())
            out.append(reg)
        except (OSError, ValueError, TypeError):
            continue
    return out


def project(name: str | None):
    wanted = (name or "ecosystem").strip()
    reg = next((item for item in projects() if item["name"] == wanted), None)
    if not reg:
        raise ValueError(f"projeto de vídeo desconhecido: {wanted}")
    root = Path(reg["_dir"])
    if not (root == FILM_DIR or str(root).startswith(str(PROJECTS_DIR) + os.sep)):
        raise ValueError("diretório do projeto fora do rig")
    return reg


def timeline_path(reg) -> Path:
    return Path(reg["_dir"]) / reg.get("timeline", "timeline.json")


def content_path(reg) -> Path:
    return Path(reg["_dir"]) / reg.get("content", "content.json")


def regenerate(reg) -> None:
    subprocess.run([sys.executable, "figma_sync.py", "--project", reg["name"], "--local"],
                   cwd=FILM_DIR, check=True, capture_output=True, text=True, timeout=120)


def field_state(reg):
    root = Path(reg["_dir"])
    frames = sorted((root / "field").glob("f????.jpg"))
    if not frames:
        return {"present": False}
    meta = {}
    try:
        text = (root / "field" / "sheet.js").read_text(encoding="utf-8")
        match = re.search(r"=\s*(\{.*\})", text)
        meta = json.loads(match.group(1)) if match else {}
    except (OSError, ValueError):
        pass
    sources = sorted(root.glob("field-src.*"))
    return {"present": True, "count": len(frames), "fps": meta.get("fps"),
            "w": meta.get("w"), "h": meta.get("h"),
            "src": sources[0].name if sources else None,
            "mtime": datetime.fromtimestamp(frames[0].stat().st_mtime, timezone.utc).isoformat(timespec="seconds")}


def timeline_payload(reg):
    tlp = timeline_path(reg)
    timeline = json.loads(tlp.read_text(encoding="utf-8")) if tlp.exists() else {}
    tl_mtime = tlp.stat().st_mtime if tlp.exists() else None
    root = Path(reg["_dir"])
    stills = sorted(p.name for p in (root / "stills").glob("t*.png"))

    def stems(comp):
        out = {"tl_mtime": tl_mtime}
        source = comp.get("soundtrack") or ""
        base = source[:-4] if source.endswith(".wav") else source
        for key, rel in (("music", f"{base}-music.wav"), ("sfx", f"{base}-sfx.wav")):
            path = root / rel
            if base and path.is_file():
                out[key] = rel
                out[f"{key}_mtime"] = path.stat().st_mtime
        return out

    theme = {}
    try:
        theme = (json.loads(content_path(reg).read_text(encoding="utf-8")) or {}).get("theme") or {}
    except (OSError, ValueError):
        pass
    prefix = "film" if reg["name"] == "ecosystem" else f"film-{reg['name']}"
    return {"project": reg["name"], "title": reg.get("title", reg["name"]),
            "timeline": timeline, "theme": theme, "theme_stock": THEME_STOCK,
            "field": field_state(reg), "stills": stills,
            "projects": [item["name"] for item in projects()],
            "compositions": [{"id": comp["id"], "html": comp["html"],
                              "soundtrack": comp.get("soundtrack"),
                              "audio_preview": stems(comp)} for comp in reg["compositions"]],
            "triggers": {"stills": f"{prefix}-stills", "render": f"{prefix}-render"},
            "capabilities": {"standalone": True, "publish": False,
                             "ai_patch": bool(shutil.which(os.environ.get("WS_FILM_CLAUDE_BIN", "claude")))}}


def validate_timeline(reg, timeline) -> None:
    if not isinstance(timeline, dict) or not timeline:
        raise ValueError("timeline vazia")
    comp_ids = {c["id"] for c in reg["compositions"]}
    for cid, cut in timeline.items():
        if cid.startswith("_"):
            continue
        if cid not in comp_ids:
            raise ValueError(f"composição desconhecida na timeline: {cid}")
        scenes = cut.get("scenes") or []
        if not scenes:
            raise ValueError(f"{cid}: sem cenas")
        previous, live = None, 0
        for scene in scenes:
            start, end = float(scene["start"]), float(scene["end"])
            if end != start:
                if end - start < 0.5:
                    raise ValueError(f"{cid}/{scene['id']}: cena mais curta que 0,5 s")
                live += 1
            if previous is not None and abs(start - previous) > 0.001:
                raise ValueError(f"{cid}/{scene['id']}: cenas têm de ser contíguas")
            if previous is None and start != 0:
                raise ValueError(f"{cid}: a primeira cena tem de começar em 0")
            previous = end
        if not live:
            raise ValueError(f"{cid}: restaura pelo menos uma cena")
        duration = previous
        audio = cut.get("audio") or {}
        for marker in audio.get("risers") or []:
            if not 0 <= float(marker) <= duration:
                raise ValueError(f"{cid}: riser fora do corte")
        if audio.get("shimmer") is not None and not 0 <= float(audio["shimmer"]) <= duration + 5:
            raise ValueError(f"{cid}: shimmer fora do corte")
        if not 0.1 <= float(audio.get("volume", 0.9)) <= 2:
            raise ValueError(f"{cid}: volume fora do intervalo 0.1–2")
        for key in ("music_vol", "sfx_vol"):
            value = audio.get(key) if audio.get(key) is not None else 1
            if not 0 <= float(value) <= 2:
                raise ValueError(f"{cid}: {key} fora do intervalo 0–2")
        source = audio.get("music_src")
        if source is not None:
            if not re.fullmatch(r"music/[A-Za-z0-9._-]+", str(source)):
                raise ValueError(f"{cid}: music_src inválido")
            if not (Path(reg["_dir"]) / source).is_file():
                raise ValueError(f"{cid}: música não existe")


def decode_upload(body, limit: int) -> bytes:
    raw = (body.get("data") or "").strip()
    if raw.startswith("data:") and "," in raw[:200]:
        raw = raw.split(",", 1)[1]
    try:
        blob = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("dados do arquivo inválidos") from exc
    if not blob:
        raise ValueError("arquivo vazio")
    if len(blob) > limit:
        raise ValueError(f"arquivo grande demais (máx. {limit // 1_000_000} MB)")
    return blob


def safe_name(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(raw or ""))


def running_for(project_name: str) -> bool:
    return any(proc.poll() is None and key.startswith(project_name + ":") for key, proc in RUNS.items())


def start_trigger(name: str):
    matches = []
    for reg in projects():
        prefix = "film" if reg["name"] == "ecosystem" else f"film-{reg['name']}"
        for kind in ("stills", "render"):
            if name == f"{prefix}-{kind}":
                matches.append((reg, kind))
    if not matches:
        raise ValueError("trigger indisponível no modo standalone")
    reg, kind = matches[0]
    if running_for(reg["name"]):
        raise ValueError("já há um processo deste projeto a correr")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    key = f"{reg['name']}:{kind}"
    log = open(LOG_DIR / f"{reg['name']}-{kind}.log", "w", encoding="utf-8")
    args = [sys.executable, "figma_sync.py", "--project", reg["name"], "--local",
            "--stills" if kind == "stills" else "--render"]
    RUNS[key] = subprocess.Popen(args, cwd=FILM_DIR, stdout=log, stderr=subprocess.STDOUT)
    return {"ok": True, "name": name, "pid": RUNS[key].pid,
            "log": str(LOG_DIR / f"{reg['name']}-{kind}.log")}


@app.errorhandler(ValueError)
def bad_request(exc):
    return jsonify(error=str(exc)), 400


@app.get("/")
def home():
    return redirect("/film-editor")


@app.get("/film-editor")
def editor():
    return send_file(FILM_DIR / "editor.html", max_age=0)


@app.get("/api/health")
def health():
    return jsonify(ok=True, service="ws-film-mini-premiere", film_dir=str(FILM_DIR),
                   projects=len(projects()), host=HOST, port=PORT)


@app.get("/api/film-timeline")
def get_timeline():
    return jsonify(timeline_payload(project(request.args.get("project"))))


@app.post("/api/film-timeline")
def save_timeline():
    body = request.get_json(force=True, silent=False) or {}
    reg = project(body.get("project"))
    timeline = body.get("timeline")
    validate_timeline(reg, timeline)
    path = timeline_path(reg)
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    new = json.dumps(timeline, ensure_ascii=False, indent=1) + "\n"
    if old == new:
        return jsonify(ok=True, changed=False)
    atomic_json(path, timeline)
    regenerate(reg)
    return jsonify(ok=True, changed=True)


@app.get("/api/film-still")
def film_still():
    reg = project(request.args.get("project"))
    name = os.path.basename(request.args.get("f") or "")
    if not re.fullmatch(r"t[0-9_]+\.png", name):
        raise ValueError("still inválido")
    path = Path(reg["_dir"]) / "stills" / name
    if not path.is_file():
        raise ValueError("still não existe")
    return send_file(path, mimetype="image/png", max_age=0)


@app.get("/film-comp/<project_name>/<path:relative>")
def film_comp(project_name, relative):
    reg = project(project_name)
    root = Path(reg["_dir"]).resolve()
    path = (root / relative).resolve()
    rig = FILM_DIR.resolve()
    if not (path == root or str(path).startswith(str(root) + os.sep)
            or path == rig or str(path).startswith(str(rig) + os.sep)):
        raise ValueError("caminho fora do projeto")
    if path.suffix.lower() not in SAFE_COMP_EXTS or not path.is_file():
        raise ValueError("arquivo da composição indisponível")
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return send_file(path, mimetype=mime, conditional=True, max_age=0)


@app.post("/api/film-music")
def film_music():
    body = request.get_json(force=True) or {}
    reg = project(body.get("project"))
    comp = body.get("comp") or ""
    path = timeline_path(reg)
    timeline = json.loads(path.read_text(encoding="utf-8"))
    if comp not in timeline:
        raise ValueError("composição desconhecida")
    blob = decode_upload(body, 60_000_000)
    name = safe_name(body.get("name") or "music")
    if Path(name).suffix.lower() not in AUDIO_EXTS:
        raise ValueError("formato de áudio não suportado")
    target = Path(reg["_dir"]) / "music" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(blob)
    timeline[comp].setdefault("audio", {})["music_src"] = f"music/{name}"
    atomic_json(path, timeline)
    regenerate(reg)
    return jsonify(ok=True, music_src=f"music/{name}")


@app.post("/api/film-theme")
def film_theme():
    body = request.get_json(force=True) or {}
    reg = project(body.get("project"))
    theme = body.get("theme")
    if not isinstance(theme, dict) or not theme:
        raise ValueError("tema vazio")
    if set(theme) - set(THEME_STOCK):
        raise ValueError("chave de tema desconhecida")
    if any(not isinstance(v, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", v)
           for v in theme.values()):
        raise ValueError("cor inválida — usa #RRGGBB")
    path = content_path(reg)
    content = json.loads(path.read_text(encoding="utf-8"))
    current = dict(content.get("theme") or {})
    current.update(theme)
    if current == (content.get("theme") or {}):
        return jsonify(ok=True, changed=False, theme=current)
    content["theme"] = current
    atomic_json(path, content)
    regenerate(reg)
    return jsonify(ok=True, changed=True, theme=current)


@app.post("/api/film-clone")
def film_clone():
    body = request.get_json(force=True) or {}
    reg = project(body.get("project"))
    slug = (body.get("slug") or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,22}[a-z0-9])?", slug):
        raise ValueError("nome inválido — usa 2–24 caracteres, números e hífen")
    if (PROJECTS_DIR / f"{slug}.json").exists() or (PROJECTS_DIR / slug).exists():
        raise ValueError("já existe um projeto com esse nome")
    result = subprocess.run([sys.executable, "figma_sync.py", "--clone", reg["name"], slug],
                            cwd=FILM_DIR, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise ValueError("clone falhou: " + (result.stderr or result.stdout)[-300:])
    return jsonify(ok=True, project=slug, editor=f"/film-editor?project={slug}")


@app.post("/api/film-field")
def film_field():
    body = request.get_json(force=True) or {}
    reg = project(body.get("project"))
    root = Path(reg["_dir"])
    field = root / "field"
    if body.get("remove"):
        shutil.rmtree(field, ignore_errors=True)
        for source in root.glob("field-src.*"):
            source.unlink(missing_ok=True)
        return jsonify(ok=True, field=field_state(reg))
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ValueError("ffmpeg/ffprobe não encontrados — instala com Homebrew")
    blob = decode_upload(body, 100_000_000)
    name = safe_name(body.get("name") or "field.mp4")
    ext = Path(name).suffix.lower()
    if ext not in FIELD_VIDEO_EXTS:
        raise ValueError("formato de vídeo não suportado")
    for source in root.glob("field-src.*"):
        source.unlink(missing_ok=True)
    source = root / f"field-src{ext}"
    source.write_bytes(blob)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", source],
                           capture_output=True, text=True, timeout=60)
    try:
        duration = float(probe.stdout.strip().splitlines()[0])
    except (ValueError, IndexError) as exc:
        source.unlink(missing_ok=True)
        raise ValueError("ffprobe não conseguiu ler o vídeo") from exc
    if duration > 91:
        source.unlink(missing_ok=True)
        raise ValueError("o slot aceita vídeos de até 90 segundos")
    shutil.rmtree(field, ignore_errors=True)
    field.mkdir()
    result = subprocess.run(["ffmpeg", "-v", "error", "-i", source,
                             "-vf", "fps=30,scale='min(1080,iw)':-2:flags=lanczos", "-q:v", "3",
                             field / "f%04d.jpg"], capture_output=True, text=True, timeout=900)
    frames = sorted(field.glob("f????.jpg"))
    if result.returncode or not frames:
        shutil.rmtree(field, ignore_errors=True)
        raise ValueError("conversão falhou: " + (result.stderr[-300:] or "sem frames"))
    dims = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
                           "-of", "csv=p=0", frames[0]], capture_output=True, text=True, timeout=30)
    width, height = (dims.stdout.strip().split(",") + ["0", "0"])[:2]
    manifest = {"count": len(frames), "fps": 30, "w": int(width or 0), "h": int(height or 0),
                "pattern": "field/f%04d.jpg", "src": source.name}
    (field / "sheet.js").write_text("window.FIELD_FOOTAGE=" + json.dumps(manifest) + ";\n",
                                    encoding="utf-8")
    return jsonify(ok=True, field=field_state(reg))


@app.post("/api/trigger")
def trigger():
    body = request.get_json(force=True) or {}
    return jsonify(start_trigger(body.get("name") or ""))


def patch_state(key: str):
    if key and not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,60}", key):
        raise ValueError("chave de patch inválida")
    if not key:
        runs = []
        for path in sorted(LOG_DIR.glob("film-patch-*.log"), key=lambda p: p.stat().st_mtime, reverse=True):
            run_key = path.stem.removeprefix("film-patch-")
            proc = PATCHES.get(run_key)
            runs.append({"key": run_key, "running": bool(proc and proc.poll() is None)})
        return {"runs": runs}
    path = LOG_DIR / f"film-patch-{key}.log"
    text = path.read_text(encoding="utf-8", errors="replace")[-20000:] if path.exists() else ""
    proc = PATCHES.get(key)
    running = bool(proc and proc.poll() is None)
    cost_match = re.search(r"run cost: (US\$[\d.]+ \(≈ AUD [\d.]+\))", text)
    return {"key": key, "running": running,
            "exit": None if running or proc is None else proc.returncode,
            "cost": cost_match.group(1) if cost_match else None, "log": text}


@app.get("/api/film-patch-log")
def film_patch_log():
    return jsonify(patch_state(request.args.get("key") or ""))


@app.post("/api/film-patch")
def film_patch():
    body = request.get_json(force=True) or {}
    reg = project(body.get("project"))
    comp = (body.get("comp") or "").strip()
    if comp not in {c["id"] for c in reg["compositions"]}:
        raise ValueError("composição desconhecida")
    brief = (body.get("brief") or "").strip()
    if not 20 <= len(brief) <= 8000:
        raise ValueError("o briefing precisa ter entre 20 e 8000 caracteres")
    if any(proc.poll() is None for proc in PATCHES.values()):
        raise ValueError("já há um patch a correr")
    if not shutil.which(os.environ.get("WS_FILM_CLAUDE_BIN", "claude")):
        raise ValueError("Claude CLI não encontrado — o editor local funciona, mas o patch com IA precisa dele")
    timeline = json.loads(timeline_path(reg).read_text(encoding="utf-8"))
    scenes = (timeline.get(comp) or {}).get("scenes") or []
    target = reg["name"]
    scene = (body.get("scene") or "").strip()
    if scene:
        if not any(s["id"] == scene and float(s["end"]) > float(s["start"]) for s in scenes):
            raise ValueError("cena desconhecida ou cortada")
        mode_args = ["--scene", scene]
        suffix = "-sub"
        if body.get("clone"):
            base = re.sub(r"-v\d+$", "", target)
            version = 2
            while (PROJECTS_DIR / f"{base}-v{version}.json").exists() or (PROJECTS_DIR / f"{base}-v{version}").exists():
                version += 1
            clone = f"{base}-v{version}"
            result = subprocess.run([sys.executable, "figma_sync.py", "--clone", target, clone],
                                    cwd=FILM_DIR, capture_output=True, text=True, timeout=180)
            if result.returncode:
                raise ValueError("clone falhou: " + (result.stderr or result.stdout)[-300:])
            target = clone
    else:
        after = (body.get("after") or "").strip()
        if not any(s["id"] == after and float(s["end"]) > float(s["start"]) for s in scenes):
            raise ValueError("cena de referência desconhecida ou cortada")
        numbers = [int(match.group(1)) for cut in timeline.values() if isinstance(cut, dict)
                   for item in cut.get("scenes", [])
                   if (match := re.fullmatch(r"s(\d+)", str(item.get("id"))))]
        scene = f"s{max(numbers, default=0) + 1}"
        mode_args = ["--add", scene, "--after", after]
        suffix = ""
    key = f"{target}-{comp}-{scene}{suffix}"
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,60}", key):
        raise ValueError("chave de patch inválida")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"film-patch-{key}.log"
    log = open(log_path, "w", encoding="utf-8")
    PATCHES[key] = subprocess.Popen([sys.executable, "patch_scene.py", "--project", target,
                                     "--comp", comp, *mode_args, "--brief", brief],
                                    cwd=FILM_DIR, stdout=log, stderr=subprocess.STDOUT)
    return jsonify(ok=True, key=key, scene=scene, project=target, cloned=target != reg["name"])


if __name__ == "__main__":
    LOCAL_DIR.mkdir(exist_ok=True)
    print(f"WS Film Mini-Premiere: http://{HOST}:{PORT}/film-editor")
    app.run(host=HOST, port=PORT, threaded=True)
