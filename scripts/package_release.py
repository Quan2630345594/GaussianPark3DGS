"""Create a clean delivery folder and archive without datasets or browser caches."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile


def main():
    root=Path(__file__).resolve().parents[1]
    target=root/'release'/'GaussianPark3DGS'
    if target.exists(): raise SystemExit('Release exists; use a new directory to preserve the previous delivery.')
    target.mkdir(parents=True)
    for name in ['README.md','requirements.txt','LICENSE','THIRD_PARTY_NOTICES.md','.gitignore']:
        shutil.copy2(root/name,target/name)
    for name in ['configs','parking_gs','frontend','scripts','tests','docs']:
        shutil.copytree(root/name,target/name,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
    for name in ['data/raw/kitti360','data/raw/kitti_odometry','data/raw/site/images','data/raw/site/colmap_text','data/processed/site','outputs']:
        folder=target/name; folder.mkdir(parents=True,exist_ok=True); (folder/'.gitkeep').touch()
    for name in ['outputs/demo/scene.npz','outputs/evaluation.json','outputs/frontend-preview.png']:
        src=root/name
        if src.is_file():
            dest=target/name; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dest)
    manifest={str(p.relative_to(target)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(target.rglob('*')) if p.is_file()}
    (target/'MANIFEST.sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    archive=target.parent/'GaussianPark3DGS.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in target.rglob('*'):
            if p.is_file(): z.write(p,p.relative_to(target.parent))
    print(json.dumps(dict(folder=str(target),archive=str(archive),files=len(manifest)+1,bytes=archive.stat().st_size)))


if __name__=='__main__': main()
