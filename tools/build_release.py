"""Package the local project, excluding environments and personal runtime data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".venv", ".netlify", "node_modules", ".pytest_cache", "__pycache__", "runtime", "dist"}


def main():
    output = ROOT / "dist" / "Cine_Cas_Phile_v1.zip"
    output.parent.mkdir(exist_ok=True)
    files = sorted(p for p in ROOT.rglob("*") if p.is_file()
                   and not any(part in EXCLUDED or part.endswith(".egg-info")
                               for part in p.relative_to(ROOT).parts)
                   and p.suffix not in {".pyc", ".pyo"}
                   and (not p.name.startswith(".env") or p.name == ".env.example"))
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
            # Keep a build phase so Netlify applies the production env context.
            archive.writestr('netlify.toml', (ROOT/'netlify.toml').read_text(encoding='utf-8').replace(
                'command = "npm run build"', 'command = "node tools/verify_prebuilt.mjs"'))
            archive.writestr('tools/verify_prebuilt.mjs',
                "import {existsSync} from 'node:fs';\n"
                "for(const file of ['dist/netlify/index.html','netlify/functions/api.mjs','netlify/functions/club.mjs','netlify/functions/data/model.json.gz'])"
                "if(!existsSync(file))throw new Error('Missing prebuilt file: '+file);\n"
                "console.log('Prebuilt website and functions verified.');\n")
            archive.write(ROOT/'package.json','package.json')
            archive.write(ROOT/'package-lock.json','package-lock.json')
            archive.writestr('DEPLOY.md', '# Cine (cas) phile. â€” prebuilt Netlify bundle\n\n'
                'Extract this ZIP, run npm ci --omit=dev in its root, then sign in with Netlify CLI.\n\n'
                '```bash\nnetlify login\nnetlify deploy --prod --build --context production --site 00750758-f294-4229-bdd8-865b45c6382d --dir dist/netlify --functions netlify/functions\n```\n\n'
                'This bundle is already built; the Netlify build command only verifies packaged files. Do not run npm run build in it. Install function dependencies with npm ci --omit=dev. '
                'The site ID belongs to the original owner. Use your own site ID when deploying into another account. '
                'Use the CLI with functions; dropping only the static folder omits the recommendation API.\n\n'
                'Configure MongoDB and OAuth variables in the Netlify production context before deployment. Never put them in the ZIP or public files.\n\n'
                'Live: https://cinecasphile.netlify.app\nSource: https://github.com/Jakcasas/cine-cas-phile (public).\n'
                'Guest profiles stay in browser localStorage; configured online accounts sync to MongoDB. Image recognition runs in browser WASM. '
                'Official address: https://cinecasphile.netlify.app/.\n')
        with ZipFile(hosted) as archive: assert archive.testzip() is None
        print(f'Verified Netlify bundle, {hosted.stat().st_size:,} bytes: {hosted}')


if __name__ == "__main__":
    main()
