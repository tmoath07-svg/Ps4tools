import os, re, sys, shutil, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]).resolve()
NAME = re.sub(r'[^A-Za-z0-9_-]', '_', sys.argv[2]) or 'converted'
FORCE = (sys.argv[3] if len(sys.argv) > 3 else 'auto').strip() or 'auto'
OUT = Path(sys.argv[4]).resolve()
DRY = os.environ.get('DRY_RUN') == '1'
NAME_CHAR = NAME.replace('-', '_')

OUT.mkdir(parents=True, exist_ok=True)
log_lines = []
def log(msg):
    print(msg, flush=True)
    log_lines.append(msg)

def listing(root):
    return [p for p in Path(root).rglob('*') if p.is_file() and p.name != '.keep']

def exts(files):
    return {p.suffix.lower() for p in files}

def names(files):
    return {p.name.lower() for p in files}

def classify(files):
    e, n = exts(files), names(files)
    if '.ydd' in e or 'peds.meta' in n:
        return 'character'
    if '.yft' in e or 'vehicles.meta' in n or 'carvariations.meta' in n:
        return 'cars'
    if e & {'.ymap', '.ytyp', '.ybn', '.ynv'}:
        return 'map'
    return 'files'

def probe_rpf(rpf):
    tmp = Path(tempfile.mkdtemp(prefix='probe_'))
    ex = ROOT / 'RPFBuilder' / 'extract_rpf.py'
    log(f'[DETECT] Opening {rpf.name} to see what is inside...')
    subprocess.run([sys.executable, str(ex), str(rpf), str(tmp / 'x')],
                   cwd=str(ex.parent), input='A\n', text=True)
    inner = listing(tmp)
    log(f'[DETECT] {len(inner)} files inside the RPF')
    return inner

def clean(d):
    shutil.rmtree(d, ignore_errors=True)
    Path(d).mkdir(parents=True, exist_ok=True)

def run_tool(stdin_text):
    if DRY:
        log(f'[DRY] would send to menu: {stdin_text!r}')
        return 0
    env = dict(os.environ, WINEDEBUG='-all', PYTHONIOENCODING='utf-8')
    return subprocess.run(['xvfb-run', '-a', sys.executable, '7N-RL_One_IRAQ.py'],
                          cwd=str(ROOT), input=stdin_text, text=True, env=env).returncode

files = listing(SRC)
log(f'[INPUT] {len(files)} file(s):')
for p in files[:40]:
    log('   - ' + str(p.relative_to(SRC)))
if not files:
    log('[ERROR] No input files were found.')
    (OUT / 'info.txt').write_text('\n'.join(log_lines), encoding='utf-8')
    sys.exit(1)

rpfs = [p for p in files if p.suffix.lower() == '.rpf']
rpf_src = None
if rpfs:
    rpf_src = next((p for p in rpfs if p.name.lower() == 'dlc.rpf'), max(rpfs, key=lambda p: p.stat().st_size))

kind, stage_files = None, files
if FORCE in ('cars', 'map'):
    if not rpf_src:
        log('[ERROR] This mode needs an .rpf file in the input.')
        (OUT / 'info.txt').write_text('\n'.join(log_lines), encoding='utf-8')
        sys.exit(1)
    kind = FORCE
elif FORCE in ('vehicle', 'character', 'files'):
    kind = {'vehicle': 'cars_loose'}.get(FORCE, FORCE)
elif rpf_src:
    inner = [] if DRY else probe_rpf(rpf_src)
    k = classify(inner) if inner else 'cars'
    if k == 'files':
        log('[ERROR] Could not recognise this RPF (not a car, map or character).')
        (OUT / 'info.txt').write_text('\n'.join(log_lines), encoding='utf-8')
        sys.exit(1)
    kind = 'character_rpf' if k == 'character' else k
    stage_files = inner
else:
    k = classify(files)
    kind = 'cars_loose' if k == 'cars' else ('files' if k == 'map' else k)

log(f'[DETECT] Mod type: {kind}')
result_dirs = []

if kind == 'cars':
    d = ROOT / 'cars dlc.rpf One step'; clean(d)
    shutil.copy2(rpf_src, d / 'dlc.rpf')
    rc = run_tool('2\n'); result_dirs = [ROOT / 'Finish']
elif kind == 'map':
    d = ROOT / 'dlc.rpf map'; clean(d)
    shutil.copy2(rpf_src, d / 'dlc.rpf')
    rc = run_tool('3\n'); result_dirs = [ROOT / 'Finish']
elif kind in ('character', 'character_rpf'):
    d = ROOT / 'Characters One Click' / 'file_input'; clean(d)
    for p in stage_files:
        if p.suffix.lower().startswith('.y'):
            shutil.copy2(p, d / p.name)
    rc = run_tool(f'6\n{NAME_CHAR}\n'); result_dirs = [ROOT / 'Characters One Click' / 'Finish']
elif kind == 'cars_loose':
    groups = {}
    for p in files:
        if p.suffix.lower() in ('.yft', '.ytd'):
            groups.setdefault(p.parent, []).append(p)
    log(f'[DETECT] {len(groups)} vehicle folder(s) found')
    d = ROOT / 'vehicles to dlc.rpf'
    rc = 0
    done = []
    for folder, flist in sorted(groups.items(), key=lambda kv: str(kv[0])):
        spawn = NAME if len(groups) == 1 else (re.sub(r'[^A-Za-z0-9_-]', '_', folder.name) or NAME)
        log(f'[VEHICLE] Converting "{spawn}" ({len(flist)} files)')
        clean(d)
        for p in flist:
            shutil.copy2(p, d / p.name)
        r = run_tool(f'4\n{spawn}\n')
        rc = rc or r
        target = OUT / NAME if len(groups) == 1 else OUT / NAME / spawn
        got = [p for p in (d / 'Finish').rglob('*') if p.is_file() and p.name != '.keep'] if (d / 'Finish').is_dir() else []
        for p in got:
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target / p.name)
        log(f'[VEHICLE] {spawn}: {len(got)} output file(s)')
        done += got
    result_dirs = []
    found_preset = done
else:
    d = ROOT / 'file_input'; clean(d)
    for p in files:
        shutil.copy2(p, d / p.name)
    rc = run_tool(f'1\nN\nY\n{NAME}\n')
    result_dirs = [ROOT / 'Finish']

log(f'[TOOL] exit code: {rc}')
dest = OUT / NAME
found = list(globals().get('found_preset', []))
for rd in result_dirs:
    if rd.is_dir():
        found += [p for p in rd.rglob('*') if p.is_file() and p.name != '.keep']
if not found and kind == 'files':
    ai = ROOT / 'file_input' / 'archive_input'
    if ai.is_dir():
        for p in ai.rglob('*'):
            if p.is_file():
                t = dest / 'converted' / p.relative_to(ai)
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, t); found.append(t)
else:
    for p in found:
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest / p.name)

log(f'[RESULT] {len(found)} output file(s) saved in folder "{NAME}"')
(OUT / 'info.txt').write_text('\n'.join(log_lines), encoding='utf-8')
sys.exit(0 if found else 1)
