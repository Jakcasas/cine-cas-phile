"""Package the local project, excluding environments and personal runtime data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".venv", ".netlify", "node_modules", ".pytest_cache", "__pycache__", "runtime", "dist"}


def main():
    output = ROOT / "dist" / "Cine_Cas_Phile_v3.zip"
    output.parent.mkdir(exist_ok=True)
    files = sorted(p for p in ROOT.rglob("*") if p.is_file()
                   and not any(part in EXCLUDED or part.endswith(".egg-info")
                               for part in p.relative_to(ROOT).parts)
                   and p.suffix not in {".pyc", ".pyo"}
                   and p.name != ".env")
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, "Cine_Cas_Phile/" + path.relative_to(ROOT).as_posix())
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        entries = set(archive.namelist())
        for required in ["Start-CineCasPhile.cmd", "README.md", "artifacts/engine.npz",
                         "web/assets/brand-avatar.svg", "data/raw/ratings.csv", "data/raw/catalog_extra.csv",
                         "data/enrichment/editorial.json", "data/enrichment/ratings.json",
                         "artifacts/vision/image_index.npz", "artifacts/vision/clip-vit-b32-int8.onnx",
                         "web/assets/fonts/mirella/Mirella-CCP-Personal.ttf", "docs/DOMAIN.md"]:
            assert "Cine_Cas_Phile/" + required in entries, required
    print(f"Verified {len(files)} files, {output.stat().st_size:,} bytes: {output}")
    hosted = ROOT / 'dist/Cine_Cas_Phile_Netlify.zip'
    bundle = ROOT / 'dist/netlify'
    if bundle.exists():
        with ZipFile(hosted, 'w', compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(bundle.rglob('*')):
                if path.is_file(): archive.write(path, 'dist/netlify/' + path.relative_to(bundle).as_posix())
            for path in sorted((ROOT/'netlify/functions').rglob('*')):
                if path.is_file(): archive.write(path, path.relative_to(ROOT).as_posix())
            archive.write(ROOT/'netlify.toml','netlify.toml')
            archive.write(ROOT/'docs/DOMAIN.md','DEPLOY.md')
        with ZipFile(hosted) as archive: assert archive.testzip() is None
        print(f'Verified Netlify bundle, {hosted.stat().st_size:,} bytes: {hosted}')


if __name__ == "__main__":
    main()
