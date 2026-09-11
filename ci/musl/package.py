import hashlib, json, re, shutil, subprocess, tarfile
from pathlib import Path

work, src = Path('/work'), Path('/src')
spec = json.loads((src/'ci/musl/project.json').read_text())
prefix = work/'prefix'
rows = []
runtime = work/'runtime'
runtime.mkdir(exist_ok=True)
for path in prefix.rglob('*'):
    if not path.is_file() or path.is_symlink():
        continue
    with path.open('rb') as stream:
        if stream.read(4) != b'\x7fELF':
            continue
    version = subprocess.check_output(['readelf','--version-info',str(path)],text=True)
    assert not re.search(r'\bGLIBC_[0-9]',version), path
    dynamic = subprocess.check_output(['readelf','-d',str(path)],text=True)
    needed = re.findall(r'\(NEEDED\).*?\[(.*?)\]',dynamic)
    rows.append({'path':str(path.relative_to(prefix)), 'needed':needed})
    if needed:
        result = subprocess.run(['ldd',str(path)],text=True,capture_output=True,
                                env={**__import__('os').environ,'LD_LIBRARY_PATH':str(prefix/'lib')},check=True)
        for name, loc in re.findall(r'^\s*(\S+) => (/\S+)',result.stdout,re.M):
            if not name.startswith('libc.musl-') and not Path(loc).resolve().is_relative_to(prefix):
                shutil.copyfile(loc,runtime/name)
assert rows, 'No ELF artifacts'
(work/'logs/elf-audit.json').write_text(json.dumps(rows,indent=2)+'\n')
licenses = work/'licenses'
licenses.mkdir(exist_ok=True)
for path in src.rglob('*'):
    if path.is_file() and '.git' not in path.parts and re.match(r'^(LICENSE|COPYING|COPYRIGHT|NOTICE)(\.|$)',path.name,re.I):
        dest=licenses/path.relative_to(src)
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,dest)
dist = work/'dist'
dist.mkdir(exist_ok=True)
manifest={**spec,'source_commit':subprocess.check_output(['git','-c','safe.directory=/src','-C','/src','rev-parse','HEAD'],text=True).strip(),
          'platform':'linux-musl-x86_64','artifact_kind':'source-built installed prefix; shared dependencies are separate',
          'base_image':'python:3.13-alpine3.23@sha256:75f27d686432419c9d42420b2b9ef605868c7a0682a6be10a6601fad46c2df01',
          'elf':rows,'apk_packages':(work/'logs/apk-packages.txt').read_text().splitlines(),
          'tests':(work/'logs/tests.log').read_text(errors='replace').splitlines()[-20:]}
(dist/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(dist/f"{spec['project']}-{spec['version']}-musl-x86_64-prefix.tar.gz",'w:gz') as tar:
    tar.add(prefix,arcname='prefix')
    tar.add(licenses,arcname='licenses')
    tar.add(dist/'build-manifest.json',arcname='build-manifest.json')
    tar.add(src/'ci/musl/README.md',arcname='README.md')
shutil.copyfile(src/'ci/musl/README.md',dist/'RELEASE_NOTES.md')
files=sorted(p for p in dist.iterdir() if p.name not in ('SHA256SUMS','RELEASE_NOTES.md'))
(dist/'SHA256SUMS').write_text(''.join(f'{hashlib.file_digest(p.open("rb"),"sha256").hexdigest()}  {p.name}\n' for p in files))
print(f'PASS: {len(rows)} ELF artifacts without GLIBC symbol requirements')
