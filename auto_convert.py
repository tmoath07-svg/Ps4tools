#!/usr/bin/env python3
import os
import re
import sys
import shutil
import hashlib
import subprocess
import tempfile
import time
from pathlib import Path
VERSION = "2.1"
ROOT = Path(__file__).resolve().parent
if len(sys.argv) < 3:
    print("Usage: auto_convert.py INPUT NAME [MODE] [OUT]")
    sys.exit(2)
SRC = Path(sys.argv[1]).resolve()
NAME = re.sub(r"[^A-Za-z0-9_-]", "_", sys.argv[2]).strip("_") or "converted"
FORCE = (sys.argv[3] if len(sys.argv) > 3 else "auto").strip().lower() or "auto"
OUT = Path(sys.argv[4] if len(sys.argv) > 4 else "../out").resolve()
NAME_CHAR = NAME.replace("-", "_")
DRY = os.environ.get("DRY_RUN") == "1"
TIMEOUT = int(os.environ.get("TOOL_TIMEOUT", "5400"))
OUT.mkdir(parents=True, exist_ok=True)
LOG = []
WARN = []
ERRORS = []
def log(msg=""):
    msg = str(msg)
    print(msg, flush=True)
    LOG.append(msg)
def warn(msg):
    WARN.append(str(msg))
    log("[WARN] " + str(msg))
def error(msg):
    ERRORS.append(str(msg))
    log("[ERROR] " + str(msg))
def finish(code):
    (OUT / "info.txt").write_text(
        "\n".join(LOG) + "\n",
        encoding="utf-8"
    )
    sys.exit(code)
JUNK_DIRS = {
    "__macosx",
    ".git",
    ".github",
    "__pycache__"
}
JUNK_FILES = {
    ".ds_store",
    "thumbs.db",
    "desktop.ini",
    ".keep"
}
def listing(root):
    root = Path(root)
    if not root.exists():
        return []
    result = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.lower() in JUNK_FILES:
            continue
        if any(x.lower() in JUNK_DIRS for x in p.parts):
            continue
        result.append(p)
    return sorted(result, key=lambda x: str(x).lower())
def ext(p):
    return Path(p).suffix.lower()
def classify(files):
    extensions = {ext(p) for p in files}
    names = {Path(p).name.lower() for p in files}
    if ".ydd" in extensions or "peds.meta" in names:
        return "character"
    if (
        ".yft" in extensions
        or "vehicles.meta" in names
        or "carvariations.meta" in names
    ):
        return "cars"
    if extensions & {
        ".ymap",
        ".ytyp",
        ".ybn",
        ".ynv",
        ".ymf"
    }:
        return "map"
    return "files"
def clean(directory):
    directory = Path(directory)
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)
def safe_id(value, fallback="converted"):
    value = re.sub(r"[^A-Za-z0-9_]", "_", str(value))
    return value.strip("_") or fallback
def probe_rpf(rpf):
    extractor = ROOT / "RPFBuilder" / "extract_rpf.py"
    if not extractor.is_file():
        warn("RPF extractor was not found.")
        return None
    tmp = Path(tempfile.mkdtemp(prefix="probe_"))
    log(f"[DETECT] Inspecting RPF: {rpf.name}")
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(extractor),
                str(rpf),
                str(tmp / "x")
            ],
            cwd=str(extractor.parent),
            input="A\n",
            text=True,
            capture_output=True,
            timeout=1800
        )
        if result.returncode != 0:
            warn(
                f"RPF extractor returned code "
                f"{result.returncode}: {rpf.name}"
            )
        if result.stderr.strip():
            log("[RPF] " + result.stderr[-1500:])
        inner = listing(tmp)
        log(f"[DETECT] {len(inner)} files found inside RPF")
        if not inner:
            return None
        return inner
    except subprocess.TimeoutExpired:
        warn(f"RPF extraction timed out: {rpf.name}")
        return None
    except Exception as exc:
        warn(f"RPF extraction failed: {exc}")
        return None
def run_tool(stdin_text):
    if DRY:
        log(f"[DRY] Menu input: {stdin_text!r}")
        return 0
    env = dict(
        os.environ,
        WINEDEBUG="-all",
        PYTHONIOENCODING="utf-8",
        TERM="dumb"
    )
    try:
        result = subprocess.run(
            [
                "xvfb-run",
                "-a",
                sys.executable,
                "7N-RL_One_IRAQ.py"
            ],
            cwd=str(ROOT),
            input=stdin_text,
            text=True,
            env=env,
            timeout=TIMEOUT
        )
        return result.returncode
    except subprocess.TimeoutExpired:
        error("Conversion timed out.")
        return 124
    except Exception as exc:
        error(f"Could not start converter: {exc}")
        return 1
def unique_target(directory, filename):
    directory = Path(directory)
    target = directory / filename
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    index = 2
    while True:
        candidate = directory / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1
def collect(directory):
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(
        [
            p for p in directory.rglob("*")
            if p.is_file() and p.name != ".keep"
        ],
        key=lambda p: str(p).lower()
    )
def save_results(files, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    saved = []
    for source in files:
        target = unique_target(destination, source.name)
        shutil.copy2(source, target)
        digest = hashlib.sha256(
            target.read_bytes()
        ).hexdigest()[:12]
        saved.append(target)
        log(
            f"[OUTPUT] {target.name} "
            f"({target.stat().st_size} bytes) "
            f"sha256:{digest}"
        )
    return saved
def run_rpf_job(rpf, mode):
    if mode == "cars":
        directory = ROOT / "cars dlc.rpf One step"
        menu = "2\n"
    else:
        directory = ROOT / "dlc.rpf map"
        menu = "3\n"
    clean(directory)
    shutil.copy2(
        rpf,
        directory / "dlc.rpf"
    )
    clean(ROOT / "Finish")
    rc = run_tool(menu)
    return rc, collect(ROOT / "Finish")
def run_character(files, spawn):
    directory = ROOT / "Characters One Click" / "file_input"
    finish_dir = ROOT / "Characters One Click" / "Finish"
    clean(directory)
    clean(finish_dir)
    for p in files:
        if ext(p).startswith(".y") or ext(p) == ".meta":
            target = directory / p.name
            if not target.exists():
                shutil.copy2(p, target)
    rc = run_tool(f"6\n{spawn}\n")
    return rc, collect(finish_dir)
def run_vehicle(files, spawn):
    directory = ROOT / "vehicles to dlc.rpf"
    clean(directory)
    for p in files:
        target = directory / p.name
        if not target.exists():
            shutil.copy2(p, target)
    rc = run_tool(f"4\n{spawn}\n")
    return rc, collect(directory / "Finish")
def run_files(files, name):
    directory = ROOT / "file_input"
    clean(directory)
    clean(ROOT / "Finish")
    for p in files:
        target = directory / p.name
        if not target.exists():
            shutil.copy2(p, target)
    rc = run_tool(
        f"1\nN\nY\n{name}\n"
    )
    return rc, collect(ROOT / "Finish")
def convert_job(kind, files, spawn=None):
    if kind == "cars":
        return run_rpf_job(files[0], "cars")
    if kind == "map":
        return run_rpf_job(files[0], "map")
    if kind == "character":
        return run_character(files, spawn or NAME_CHAR)
    if kind == "vehicle":
        return run_vehicle(files, spawn or NAME)
    if kind == "files":
        return run_files(files, NAME)
    raise ValueError(f"Unknown conversion type: {kind}")
# --------------------------------------------------
# MAIN
# --------------------------------------------------
log(f"GTA V PC -> PS4 Converter v{VERSION}")
log(f"[SETTINGS] Name={NAME} Mode={FORCE}")
if not SRC.is_dir():
    error("Input directory does not exist.")
    finish(1)
files = listing(SRC)
log(f"[INPUT] {len(files)} files found.")
for p in files[:60]:
    log(" - " + str(p.relative_to(SRC)))
if len(files) > 60:
    log(f"... and {len(files) - 60} more files")
if not files:
    error("No input files found.")
    finish(1)
if FORCE not in (
    "auto",
    "cars",
    "map",
    "vehicle",
    "character",
    "files"
):
    error(f"Unsupported mode: {FORCE}")
    finish(1)
jobs = []
rpfs = [
    p for p in files
    if ext(p) == ".rpf"
]
loose = [
    p for p in files
    if ext(p) != ".rpf"
]
# Forced RPF modes
if FORCE in ("cars", "map"):
    if not rpfs:
        error("This mode requires an RPF file.")
        finish(1)
    for rpf in rpfs:
        jobs.append({
            "kind": FORCE,
            "files": [rpf],
            "label": f"{FORCE}_{rpf.stem}"
        })
# Forced loose modes
elif FORCE == "vehicle":
    groups = {}
    for p in loose:
        if ext(p) in (".yft", ".ytd"):
            groups.setdefault(p.parent, []).append(p)
    for folder, group in sorted(groups.items()):
        jobs.append({
            "kind": "vehicle",
            "files": group,
            "spawn": safe_id(folder.name, NAME),
            "label": f"car_{safe_id(folder.name, NAME)}"
        })
elif FORCE == "character":
    jobs.append({
        "kind": "character",
        "files": loose,
        "spawn": NAME_CHAR,
        "label": "character"
    })
elif FORCE == "files":
    jobs.append({
        "kind": "files",
        "files": loose,
        "label": "files"
    })
# Automatic detection
else:
    for rpf in rpfs:
        inner = probe_rpf(rpf)
        if not inner:
            warn(f"Skipped unreadable RPF: {rpf.name}")
            continue
        detected = classify(inner)
        if detected == "files":
            warn(f"Unrecognised RPF: {rpf.name}")
            continue
        jobs.append({
            "kind": detected,
            "files": [rpf] if detected in ("cars", "map") else inner,
            "spawn": NAME_CHAR,
            "label": f"{detected}_{rpf.stem}"
        })
    groups = {}
    for p in loose:
        groups.setdefault(p.parent, []).append(p)
    for folder, group in sorted(groups.items()):
        detected = classify(group)
        if detected == "cars":
            vehicle_files = [
                p for p in group
                if ext(p) in (".yft", ".ytd")
            ]
            if vehicle_files:
                jobs.append({
                    "kind": "vehicle",
                    "files": vehicle_files,
                    "spawn": safe_id(folder.name, NAME),
                    "label": f"car_{safe_id(folder.name, NAME)}"
                })
        elif detected == "character":
            jobs.append({
                "kind": "character",
                "files": group,
                "spawn": NAME_CHAR,
                "label": f"character_{safe_id(folder.name)}"
            })
        elif detected == "map":
            jobs.append({
                "kind": "files",
                "files": group,
                "label": f"map_files_{safe_id(folder.name)}"
            })
if not jobs:
    error("No supported conversion jobs were detected.")
    finish(1)
log(f"[PLAN] {len(jobs)} conversion job(s)")
results = []
total = 0
for index, job in enumerate(jobs, 1):
    kind = job["kind"]
    log("")
    log(
        f"===== JOB {index}/{len(jobs)} "
        f"{kind} ({job['label']}) ====="
    )
    start = time.time()
    try:
        rc, outputs = convert_job(
            kind,
            job["files"],
            job.get("spawn")
        )
    except Exception as exc:
        error(f"Job failed: {exc}")
        rc, outputs = 1, []
    if outputs:
        destination = (
            OUT / NAME
            if len(jobs) == 1
            else OUT / NAME / safe_id(job["label"])
        )
        saved = save_results(
            outputs,
            destination
        )
    else:
        saved = []
    elapsed = int(time.time() - start)
    total += len(saved)
    results.append({
        "job": job,
        "rc": rc,
        "saved": saved
    })
    log(
        f"[JOB] exit={rc} "
        f"outputs={len(saved)} "
        f"time={elapsed}s"
    )
    if not saved:
        warn(f"{job['label']} produced no output.")
    elif rc != 0:
        warn(
            f"{job['label']} produced output "
            f"but exited with code {rc}."
        )
# --------------------------------------------------
# SUMMARY
# --------------------------------------------------
successful = sum(
    1 for result in results
    if result["saved"]
)
log("")
log("========== SUMMARY ==========")
log(f"Jobs: {len(results)}")
log(f"Successful: {successful}")
log(f"Failed: {len(results) - successful}")
log(f"Output files: {total}")
log(f"Output directory: {OUT / NAME}")
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    lines = [
        f"## GTA V PC -> PS4 Converter v{VERSION}",
        "",
        f"Folder: **{NAME}**",
        "",
        "| Job | Status | Files |",
        "|---|---|---:|"
    ]
    for result in results:
        job = result["job"]
        status = (
            "OK"
            if result["saved"]
            else "FAILED"
        )
        lines.append(
            f"| {job['label']} | {status} | "
            f"{len(result['saved'])} |"
        )
    if WARN:
        lines += ["", "### Warnings"]
        for message in WARN:
            lines.append(f"- {message}")
    with open(summary, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
finish(
    0 if total > 0 or DRY else 1
)
