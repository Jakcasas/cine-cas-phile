/* Only loaded by the Netlify edition. Personal profiles stay in the browser. */
"use strict";
window.cineHosted = (() => {
  let referencesPromise, sessionPromise, memoryProfile;
  const references = () =>
    (referencesPromise ??= fetch("/static/vision/references.json")
      .then((r) => {
        if (!r.ok) throw new Error("Không tải được kho ảnh.");
        return r.json();
      })
      .catch((error) => {
        referencesPromise = null;
        throw error;
      }));
  const validProfile = (p) =>
    p &&
    typeof p.profile_id === "string" &&
    Array.isArray(p.watchlist) &&
    Array.isArray(p.genres) &&
    p.ratings &&
    typeof p.ratings === "object" &&
    !Array.isArray(p.ratings);
  const read = () => {
    try {
      const p = JSON.parse(
        localStorage.getItem("cine-hosted-profile") || "null",
      );
      return validProfile(p) ? p : memoryProfile || null;
    } catch {
      return memoryProfile || null;
    }
  };
  const write = (profile) => {
    memoryProfile = profile;
    try {
      localStorage.setItem("cine-hosted-profile", JSON.stringify(profile));
    } catch {}
    return profile;
  };
  async function remote(path, options = {}) {
    const response = await fetch("/api" + path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error("Máy chủ đang bận. Vui lòng thử lại sau.");
    }
    if (!response.ok) throw new Error(data.detail || "Không thể tải phim.");
    return data;
  }
  async function request(path, options = {}) {
    const method = options.method || "GET",
      body = options.body ? JSON.parse(options.body) : {};
    if (path === "/profiles" && method === "POST")
      return write({
        profile_id: crypto.randomUUID(),
        ratings: {},
        watchlist: [],
        genres: [],
      });
    if (path.startsWith("/profiles/")) {
      let profile = read();
      const [, root, id, kind, mid] = path.split("/");
      if (!profile || profile.profile_id !== id)
        throw new Error("Profile not found");
      if (method === "GET") {
        const ids = [
          ...new Set([
            ...profile.watchlist,
            ...Object.keys(profile.ratings).map(Number),
          ]),
        ];
        const data = ids.length
          ? await remote("/movie-batch", {
              method: "POST",
              body: JSON.stringify({ ids }),
            })
          : { movies: [] };
        const map = new Map(data.movies.map((m) => [m.movie_id, m]));
        return {
          ...profile,
          watchlist_movies: profile.watchlist
            .map((id) => map.get(id))
            .filter(Boolean),
          rated_movies: Object.entries(profile.ratings)
            .filter(([id]) => map.has(Number(id)))
            .map(([id, rating]) => ({
              ...map.get(Number(id)),
              my_rating: rating,
            })),
        };
      }
      if (kind === "preferences") {
        profile.genres = body.genres || [];
        write(profile);
        return request(`/profiles/${id}`);
      }
      if (kind === "ratings") {
        if (method === "DELETE") delete profile.ratings[mid];
        else profile.ratings[mid] = body.rating;
      } else if (kind === "watchlist") {
        profile.watchlist =
          method === "DELETE"
            ? profile.watchlist.filter((id) => id !== Number(mid))
            : [...new Set([...profile.watchlist, Number(mid)])];
      }
      write(profile);
      return { saved: Number(mid) };
    }
    if (path === "/discover") {
      const profile = read();
      return remote(path, {
        ...options,
        body: JSON.stringify({
          ...body,
          ratings: profile?.ratings || {},
          preferred_genres: body.preferred_genres?.length
            ? body.preferred_genres
            : profile?.genres || [],
        }),
      });
    }
    if (path === "/visual-search/status") {
      const refs = await references();
      return {
        ready: typeof WebAssembly !== "undefined",
        indexed_movies: new Set(refs.movie_ids).size,
        scene_images: refs.stills,
      };
    }
    return remote(path, options);
  }
  async function loadSession() {
    if (sessionPromise) return sessionPromise;
    sessionPromise = (async () => {
      const status = document.querySelector("#image-status");
      status.textContent =
        "Lần đầu cần tải mô hình nhận diện khoảng 110 MB. Ảnh của bạn vẫn ở trong trình duyệt.";
      if (!window.ort)
        await new Promise((resolve, reject) => {
          const script = document.createElement("script");
          script.src = "/static/ort/ort.wasm.min.js";
          script.onload = resolve;
          script.onerror = () =>
            reject(new Error("Không tải được bộ xử lý ảnh."));
          document.head.append(script);
        });
      ort.env.wasm.numThreads = 1;
      ort.env.wasm.wasmPaths = new URL("/static/ort/", location.href).href;
      const refs = await references();
      let downloaded = 0;
      const parts = await Promise.all(
        refs.model_parts.map(async (name) => {
          const r = await fetch("/static/vision/" + name);
          if (!r.ok) throw new Error("Không tải được mô hình ảnh.");
          const data = new Uint8Array(await r.arrayBuffer());
          downloaded += data.length;
          status.textContent = `Đang tải mô hình: ${Math.round((downloaded / refs.model_bytes) * 100)}%. Ảnh được xử lý trong trình duyệt.`;
          return data;
        }),
      );
      const bytes = new Uint8Array(refs.model_bytes);
      let offset = 0;
      for (const p of parts) {
        bytes.set(p, offset);
        offset += p.length;
      }
      status.textContent = "Đang khởi động mô hình nhận diện…";
      return ort.InferenceSession.create(bytes, {
        executionProviders: ["wasm"],
        graphOptimizationLevel: "all",
      });
    })();
    try {
      return await sessionPromise;
    } catch (error) {
      sessionPromise = null;
      throw error;
    }
  }
  async function imageEmbedding(file) {
    if (
      file.size > 8 * 1024 * 1024 ||
      !["image/jpeg", "image/png", "image/webp"].includes(file.type)
    )
      throw new Error("Chọn JPEG, PNG hoặc WebP dưới 8 MB.");
    const bitmap = await createImageBitmap(file);
    if (
      bitmap.width * bitmap.height > 20000000 ||
      Math.min(bitmap.width, bitmap.height) < 16
    ) {
      bitmap.close();
      throw new Error(
        "Ảnh phải có ít nhất 16 pixel mỗi chiều, không quá 20 megapixel.",
      );
    }
    const canvas = document.createElement("canvas");
    canvas.width = 224;
    canvas.height = 224;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    const size = Math.min(bitmap.width, bitmap.height);
    ctx.drawImage(
      bitmap,
      (bitmap.width - size) / 2,
      (bitmap.height - size) / 2,
      size,
      size,
      0,
      0,
      224,
      224,
    );
    bitmap.close();
    const pixels = ctx.getImageData(0, 0, 224, 224).data,
      plane = 224 * 224,
      input = new Float32Array(plane * 3),
      mean = [0.48145466, 0.4578275, 0.40821073],
      std = [0.26862954, 0.26130258, 0.27577711];
    for (let i = 0; i < plane; i++)
      for (let c = 0; c < 3; c++)
        input[c * plane + i] = (pixels[i * 4 + c] / 255 - mean[c]) / std[c];
    const session = await loadSession();
    document.querySelector("#image-status").textContent =
      "Đang đối chiếu cảnh phim trên thiết bị của bạn…";
    const output = await session.run({
      pixel_values: new ort.Tensor("float32", input, [1, 3, 224, 224]),
    });
    const vector = output.image_embeds.data;
    let norm = 0;
    for (const value of vector) norm += value * value;
    norm = Math.sqrt(norm);
    return Float32Array.from(vector, (x) => x / Math.max(norm, 1e-12));
  }
  async function searchImage(file, k = 8) {
    try {
      const [vector, refs] = await Promise.all([
        imageEmbedding(file),
        references(),
      ]);
      const response = await fetch("/static/vision/embeddings.bin");
      if (!response.ok) throw new Error("Không tải được chỉ mục ảnh.");
      const values = new Float32Array(await response.arrayBuffer());
      const order = refs.movie_ids
        .map((mid, i) => {
          let score = 0;
          for (let j = 0; j < refs.dim; j++)
            score += values[i * refs.dim + j] * vector[j];
          return {
            movie_id: mid,
            visual_similarity: score,
            matched_image_url: refs.urls[i],
            matched_image_kind: refs.kinds[i],
          };
        })
        .sort((a, b) => b.visual_similarity - a.visual_similarity);
      const seen = new Set(),
        matches = [];
      for (const m of order) {
        if (seen.has(m.movie_id)) continue;
        seen.add(m.movie_id);
        matches.push(m);
        if (matches.length >= k) break;
      }
      const data = await remote("/movie-batch", {
        method: "POST",
        body: JSON.stringify({ ids: matches.map((m) => m.movie_id) }),
      });
      const map = new Map(data.movies.map((m) => [m.movie_id, m]));
      return {
        ok: true,
        json: async () => ({
          matches: matches.map((m) => ({ ...map.get(m.movie_id), ...m })),
          notice:
            "Ứng viên gần giống trong kho tham chiếu; điểm tương đồng không phải xác suất nhận diện. Ảnh được xử lý trên thiết bị của bạn và không tải lên máy chủ.",
        }),
      };
    } catch (error) {
      return { ok: false, json: async () => ({ detail: error.message }) };
    }
  }
  return { request, searchImage };
})();
