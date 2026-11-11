```yaml
name: Convert GTA V mod to PS4

on:
  workflow_dispatch:
    inputs:
      name:
        description: "اسم المجلد (انجليزي بدون مسافات)"
        default: converted
      release_tag:
        description: "اسم الـ Release (Tag) اللي رفعت فيه الملفات"
        required: false
        default: ""
      mode:
        description: "النوع (خله auto ويكتشفه بنفسه)"
        type: choice
        default: auto
        options:
          - auto
          - cars
          - map
          - vehicle
          - character
          - files
      url:
        description: "رابط تحميل مباشر (اختياري)"
        required: false
        default: ""

jobs:
  convert:
    runs-on: ubuntu-22.04
    timeout-minutes: 120
    steps:
      - uses: actions/checkout@v4

      - name: Install tools
        run: |
          sudo apt-get update -y
          sudo apt-get install -y wine wine64 xvfb unzip python3
          sudo apt-get install -y p7zip-full unrar || true
          sudo apt-get install -y p7zip-rar || true
          python3 -m pip install pycryptodome watchdog

      - name: Unpack tool
        run: |
          unzip -q ps4tool.zip
          mkdir -p ps4tool/file_input ps4tool/Finish

      - name: Gather input files
        env:
          URL: ${{ inputs.url }}
          TAG: ${{ inputs.release_tag }}
          GH_TOKEN: ${{ github.token }}
        run: |
          mkdir -p input
          if [ -n "$TAG" ]; then
            gh release download "$TAG" --repo "${{ github.repository }}" --dir input --clobber
          fi
          if [ -n "$URL" ]; then
            curl -L --fail -o /tmp/download "$URL"
            if 7z t /tmp/download >/dev/null 2>&1; then
              mv /tmp/download input/download.7z
            else
              cp /tmp/download input/dlc.rpf
            fi
          fi
          for pass in 1 2; do
            for a in input/*.zip input/*.rar input/*.7z; do
              [ -f "$a" ] || continue
              case "$a" in
                *.zip) unzip -q -o "$a" -d input ;;
                *) 7z x -y -oinput "$a" || unrar x -o+ -y "$a" input/ ;;
              esac
              rm -f "$a"
            done
          done
          echo "== input files =="
          find input -type f ! -name ".keep" | head -50

      - name: Detect and convert
        env:
          NAME: ${{ inputs.name }}
          MODE: ${{ inputs.mode }}
        run: |
          cat > ps4tool/auto_convert.py <<'PYEOF'
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
              d = ROOT / 'vehicles to dlc.rpf'; clean(d)
              for p in files:
                  if p.suffix.lower() in ('.yft', '.ytd'):
                      shutil.copy2(p, d / p.name)
              rc = run_tool(f'4\n{NAME}\n'); result_dirs = [d / 'Finish']
          else:
              d = ROOT / 'file_input'; clean(d)
              for p in files:
                  shutil.copy2(p, d / p.name)
              rc = run_tool(f'1\nN\nY\n{NAME}\n')
              result_dirs = [ROOT / 'Finish']

          log(f'[TOOL] exit code: {rc}')
          dest = OUT / NAME
          found = []
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
          PYEOF
          cd ps4tool
          python3 auto_convert.py ../input "$NAME" "$MODE" ../out

      - name: Check output
        run: |
          find out -type f ! -name info.txt | tee /tmp/out.txt
          test -s /tmp/out.txt

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ps4-result
          path: out
          if-no-files-found: warn
```