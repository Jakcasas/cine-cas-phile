import {
  mkdirSync,
  cpSync,
  readFileSync,
  writeFileSync,
  copyFileSync,
  existsSync,
} from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
const root = process.cwd(),
  out = path.join(root, "dist/netlify");
const require = createRequire(import.meta.url),
  ort = path.dirname(require.resolve("onnxruntime-web"));
mkdirSync(out, { recursive: true });
cpSync(path.join(root, "web"), path.join(out, "static"), { recursive: true });
let html = readFileSync("web/index.html", "utf8").replace(
  '<script src="/static/app.js"',
  '<script src="/static/hosted-adapter.js"></script><script src="/static/app.js"',
);
html = html
  .replace("Hồ sơ được lưu trên máy.", "Hồ sơ được lưu trong trình duyệt.")
  .replace('href="/docs"', 'href="/static/hosted-docs.html"');
writeFileSync(path.join(out, "index.html"), html);
for (const name of ["robots.txt", "sitemap.xml"])
  copyFileSync(path.join(root, "web", name), path.join(out, name));
const target = path.join(out, "static/ort");
mkdirSync(target, { recursive: true });
for (const name of [
  "ort.wasm.min.js",
  "ort-wasm-simd-threaded.mjs",
  "ort-wasm-simd-threaded.wasm",
])
  copyFileSync(path.join(ort, name), path.join(target, name));
copyFileSync("docs/ONNX_RUNTIME_LICENSE.txt", path.join(target, "LICENSE.txt"));
const vision = path.join(out, "static/vision");
mkdirSync(vision, { recursive: true });
const bytes = readFileSync("artifacts/vision/clip-vit-b32-int8.onnx"),
  refs = JSON.parse(
    readFileSync("artifacts/vision/web-references.json", "utf8"),
  );
refs.model_parts = [];
refs.model_bytes = bytes.length;
for (
  let i = 0, start = 0;
  start < bytes.length;
  i++, start += 8 * 1024 * 1024
) {
  const name = `clip-${String(i).padStart(2, "0")}.bin`;
  writeFileSync(
    path.join(vision, name),
    bytes.subarray(start, start + 8 * 1024 * 1024),
  );
  refs.model_parts.push(name);
}
writeFileSync(path.join(vision, "references.json"), JSON.stringify(refs));
copyFileSync(
  "artifacts/vision/web-embeddings.bin",
  path.join(vision, "embeddings.bin"),
);
copyFileSync("docs/CLIP_LICENSE.txt", path.join(vision, "LICENSE.txt"));
if (!existsSync("netlify/functions/data/model.json.gz"))
  throw new Error(
    "Missing private recommendation artifact; run tools/build_netlify.py first.",
  );
writeFileSync(
  path.join(out, "_redirects"),
  "/api/* /.netlify/functions/api/:splat 200\n/docs /static/hosted-docs.html 302\n",
);
console.log(
  `Netlify web built: ${new Set(refs.movie_ids).size} indexed films. Recommendation model stays inside functions.`,
);
