"use strict";
const $ = (selector) => document.querySelector(selector);
const state = {
  view: "discover",
  genre: "",
  page: 1,
  total: 0,
  seed: null,
  profile: null,
  stats: null,
  request: 0,
  detail: null,
};
const labels = {
  discover: "Khám phá",
  curated: "MUBI & Letterboxd",
  foryou: "Dành cho bạn",
  watchlist: "Danh sách xem",
  ratings: "Đã đánh giá",
  insights: "Phòng dữ liệu",
};
const genreNames = {
  Action: "Hành động",
  Adventure: "Phiêu lưu",
  Animation: "Hoạt hình",
  "Children's": "Gia đình",
  Comedy: "Hài",
  Crime: "Tội phạm",
  Documentary: "Tài liệu",
  Drama: "Chính kịch",
  Fantasy: "Kỳ ảo",
  "Film-Noir": "Film Noir",
  Horror: "Kinh dị",
  Musical: "Nhạc kịch",
  Mystery: "Bí ẩn",
  Romance: "Lãng mạn",
  "Sci-Fi": "Khoa học viễn tưởng",
  Thriller: "Giật gân",
  War: "Chiến tranh",
  Western: "Cao bồi",
};
const palettes = [
  ["#65303c", "#25121a"],
  ["#91674e", "#3a2022"],
  ["#6b4347", "#25171f"],
  ["#796242", "#32221d"],
  ["#704556", "#2b1622"],
  ["#775953", "#311a24"],
  ["#803f48", "#30171e"],
];
const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const format = (value) => new Intl.NumberFormat("vi-VN").format(value);
const genreLabel = (genre) => genreNames[genre] || genre;
// User selected panels 2, 3 and 4 only. CSS clips the original contact sheet.
function artPosition(movie) {
  const genres = movie.genres.split("|");
  if (genres.includes("Sci-Fi")) return "50% 0%";
  if (
    genres.some((g) =>
      ["Crime", "Thriller", "Horror", "Mystery", "Film-Noir"].includes(g),
    )
  )
    return "100% 0%";
  if (genres.some((g) => ["Adventure", "Western", "Romance"].includes(g)))
    return "0% 100%";
  return ["50% 0%", "100% 0%", "0% 100%"][movie.movie_id % 3];
}
async function api(path, options = {}) {
  if (window.cineHosted) return window.cineHosted.request(path, options);
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("Máy chủ trả về dữ liệu không hợp lệ.");
  }
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Dữ liệu không hợp lệ. Hãy kiểm tra bộ lọc và thử lại.",
    );
  return data;
}
const send = (path, method, body) =>
  api(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
let toastTimer;
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#toast").classList.remove("show"), 3000);
}
function poster(movie) {
  const colors = palettes[movie.movie_id % palettes.length];
  const image = movie.poster_urls?.length
    ? `<img class="movie-poster" src="${escapeHtml(movie.poster_urls[0])}" data-poster-urls="${escapeHtml(JSON.stringify(movie.poster_urls))}" data-poster-index="0" alt="Poster ${escapeHtml(movie.title)} (${movie.year ?? ""})" loading="lazy" decoding="async" referrerpolicy="no-referrer">`
    : "";
  return `<span class="film-art" style="background-position:${artPosition(movie)}"></span>${image}<span class="edition">Cine (cas) phile. / ${String(movie.movie_id).padStart(4, "0")}</span><span class="poster-title">${escapeHtml(movie.title)}</span><span class="poster-year">${movie.year ?? "CINEMA"}</span>`;
}
document.addEventListener(
  "error",
  (event) => {
    const image = event.target;
    if (
      !(image instanceof HTMLImageElement) ||
      !image.classList.contains("movie-poster")
    )
      return;
    const urls = JSON.parse(image.dataset.posterUrls || "[]");
    const index = Number(image.dataset.posterIndex || 0) + 1;
    image.dataset.posterIndex = String(index);
    if (index < urls.length) image.src = urls[index];
    else image.hidden = true;
  },
  true,
);
function card(movie) {
  const colors = palettes[movie.movie_id % palettes.length];
  const saved = state.profile?.watchlist.includes(movie.movie_id);
  return `<article class="movie-card"><button class="poster alt-${movie.movie_id % 4}" data-movie="${movie.movie_id}" style="--cover-bg:linear-gradient(145deg,${colors[0]},${colors[1]})" aria-label="Xem chi tiết ${escapeHtml(movie.title)}">${poster(movie)}</button><button class="save-button ${saved ? "saved" : ""}" data-save="${movie.movie_id}" aria-label="${saved ? "Bỏ lưu" : "Lưu"} ${escapeHtml(movie.title)}" aria-pressed="${!!saved}">${saved ? "✓" : "+"}</button><div class="movie-meta"><div class="movie-top"><h3>${escapeHtml(movie.title)}</h3><span class="rating">★ ${movie.rating === null ? "—" : Number(movie.rating).toFixed(1)}</span></div><div class="meta-line">${movie.year ?? "—"} ${movie.media_type === "series" ? " · SERIES" : ""} <span>·</span> ${escapeHtml(movie.genres.split("|").slice(0, 2).map(genreLabel).join(" / "))}</div>${movie.reason ? `<div class="reason">✧ ${escapeHtml(movie.reason)} <span title="Điểm xếp hạng tương đối, không phải xác suất">· ${Math.round(movie.score * 100)}/100</span></div>` : ""}${movie.my_rating ? `<div class="my-rating">Bạn đã chấm ${movie.my_rating} / 5 ★</div>` : ""}</div></article>`;
}
function empty(title, description) {
  return `<div class="empty" style="grid-column:1/-1"><span class="small-spark">✧</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(description)}</p><button class="primary" data-go="discover">Khám phá kho phim ↗</button></div>`;
}
function renderChips() {
  $("#genre-chips").innerHTML = [
    ["", "Tất cả"],
    ...state.stats.genres.map((g) => [g, genreLabel(g)]),
  ]
    .map(
      ([value, title]) =>
        `<button class="chip ${state.genre === value ? "active" : ""}" data-genre="${escapeHtml(value)}" aria-pressed="${state.genre === value}">${escapeHtml(title)}</button>`,
    )
    .join("");
}
function renderProfile() {
  $("#saved-count").textContent = state.profile.watchlist.length;
}
function years() {
  const value = $("#era").value;
  return value ? value.split(":").map(Number) : [null, null];
}
function setView(view) {
  state.view = view;
  state.page = 1;
  $(".nav.active")?.classList.remove("active");
  $(`.nav[data-view="${view}"]`).classList.add("active");
  $("#crumb").textContent = labels[view];
  $("#hero").hidden = view !== "discover";
  $("#recommend-controls").hidden = view !== "foryou";
  $("#insights").hidden = view !== "insights";
  $("#collections").hidden = view !== "discover";
  $("#cinema-note").hidden = view !== "discover";
  $(".club-strip").hidden = view !== "discover";
  $("#grid").hidden = view === "insights";
  $("#toolbar").hidden = view === "insights";
  $("#genre-chips").hidden = view === "insights";
  $("#sort").disabled = !["discover", "curated"].includes(view);
  const copy = {
    curated: [
      "THE EDITORIAL SHELF",
      "Những góc nhìn điện ảnh khác.",
      "Phim và poster từ MUBI, Letterboxd — gồm cả La Mesías và các tác phẩm mới.",
    ],
    discover: [
      "THE DISCOVERY ROOM",
      "Một thế giới đáng để khám phá.",
      "Những câu chuyện hay luôn chờ được tìm thấy.",
    ],
    foryou: [
      "CURATED FOR YOU",
      "Đúng gu. Đúng cảm xúc.",
      "Gợi ý từ thể loại yêu thích và các phim bạn đã đánh giá.",
    ],
    watchlist: [
      "YOUR NEXT GREAT WATCH",
      "Để dành một câu chuyện hay.",
      "Những bộ phim bạn muốn dành thời gian khám phá.",
    ],
    ratings: [
      "YOUR CINEMA DIARY",
      "Những dấu ấn điện ảnh.",
      "Mỗi đánh giá giúp chúng mình hiểu gu của bạn hơn.",
    ],
    insights: [
      "BEHIND THE RECOMMENDATIONS",
      "Điện ảnh, nhìn từ dữ liệu.",
      "Dữ liệu thực, thuật toán rõ ràng, kết quả có thể kiểm chứng.",
    ],
  };
  $("#section-kicker").textContent = copy[view][0];
  $("#section-title").textContent = copy[view][1];
  $("#section-description").textContent = copy[view][2];
  loadView();
}
async function loadView() {
  if (!state.stats || !state.profile) return;
  const token = ++state.request;
  $("#status").textContent = "";
  $("#pagination").hidden = true;
  $("#seed-bar").hidden = !(state.view === "foryou" && state.seed);
  if (state.seed)
    $("#seed-bar").innerHTML =
      `<span>✧ Lấy cảm hứng từ: ${escapeHtml(state.seed.title)}</span><button data-clear-seed aria-label="Bỏ phim gợi ý">×</button>`;
  $("#grid").innerHTML = Array.from(
    { length: 10 },
    () => '<div class="loading" aria-hidden="true"></div>',
  ).join("");
  try {
    if (state.view === "insights") {
      await renderInsights(token);
      return;
    }
    let movies = [],
      info = "";
    const [yearMin, yearMax] = years();
    if (["discover", "curated"].includes(state.view)) {
      const params = new URLSearchParams({
        q: $("#search").value,
        sort: $("#sort").value,
        page: state.page,
        page_size: 20,
      });
      if (state.view === "curated") params.set("source", "editorial");
      if (state.genre) params.set("genre", state.genre);
      if (yearMin !== null) {
        params.set("year_min", yearMin);
        params.set("year_max", yearMax);
      }
      const data = await api(`/movies?${params}`);
      movies = data.movies;
      state.total = data.total;
      info = `${format(data.total)} bộ phim · Chọn một câu chuyện cho hôm nay`;
    } else if (state.view === "foryou") {
      const demo = $("#demo-user").value;
      if (demo && (!Number.isInteger(Number(demo)) || Number(demo) < 1))
        throw new Error("ID MovieLens phải là một số nguyên dương.");
      const data = await send("/discover", "POST", {
        profile_id: state.profile.profile_id,
        user_id: demo ? Number(demo) : null,
        model: $("#model").value,
        genre: state.genre || null,
        year_min: yearMin,
        year_max: yearMax,
        k: 20,
        diversity: Number($("#diversity").value),
        seed_ids: state.seed ? [state.seed.movie_id] : [],
      });
      movies = data.recommendations;
      info = `${data.count} gợi ý · ${data.latency_ms} ms · Điểm xếp hạng 0–100`;
      if (data.is_fallback)
        $("#status").textContent =
          data.fallback_reason ||
          "Bắt đầu với những phim được cộng đồng yêu thích. Chọn gu phim hoặc chấm điểm vài phim để cá nhân hóa gợi ý.";
    } else {
      const profile = await api(`/profiles/${state.profile.profile_id}`);
      state.profile = profile;
      renderProfile();
      movies =
        state.view === "watchlist"
          ? profile.watchlist_movies
          : profile.rated_movies;
      movies = movies.filter(
        (m) =>
          (!state.genre || m.genres.split("|").includes(state.genre)) &&
          (yearMin === null || (m.year >= yearMin && m.year <= yearMax)),
      );
      info = `${movies.length} bộ phim ${state.view === "watchlist" ? "đã lưu" : "đã đánh giá"}`;
    }
    if (token !== state.request) return;
    $("#result-count").textContent = info;
    $("#grid").innerHTML = movies.length
      ? movies.map(card).join("")
      : empty(
          state.view === "watchlist"
            ? "Danh sách của bạn còn trống"
            : state.view === "ratings"
              ? "Chưa có đánh giá"
              : "Không tìm thấy phim phù hợp",
          state.view === "watchlist"
            ? "Nhấn dấu + trên một phim để lưu vào danh sách."
            : state.view === "ratings"
              ? "Mở chi tiết một phim và chấm từ 1 đến 5 sao."
              : "Thử một thể loại hoặc thời kỳ khác.",
        );
    if (["discover", "curated"].includes(state.view) && state.total > 20) {
      $("#pagination").hidden = false;
      $("#page-label").textContent =
        `${state.page} / ${Math.ceil(state.total / 20)}`;
      $("#previous").disabled = state.page <= 1;
      $("#next").disabled = state.page >= Math.ceil(state.total / 20);
    }
  } catch (error) {
    if (token !== state.request) return;
    $("#grid").innerHTML = "";
    $("#status").textContent = `Không thể tải phim: ${error.message}`;
    $("#result-count").textContent = "Hãy thử lại";
  }
}
async function toggleSave(movieId) {
  const saved = state.profile.watchlist.includes(movieId);
  await send(
    `/profiles/${state.profile.profile_id}/watchlist/${movieId}`,
    saved ? "DELETE" : "PUT",
  );
  if (saved)
    state.profile.watchlist = state.profile.watchlist.filter(
      (id) => id !== movieId,
    );
  else state.profile.watchlist.push(movieId);
  renderProfile();
  document.querySelectorAll(`[data-save="${movieId}"]`).forEach((button) => {
    button.classList.toggle("saved", !saved);
    button.setAttribute("aria-pressed", String(!saved));
    button.setAttribute("aria-label", saved ? "Lưu phim" : "Bỏ lưu phim");
    button.textContent =
      (saved ? "+" : "✓") +
      (button.classList.contains("save-button-detail") ? " Danh sách xem" : "");
  });
  toast(saved ? "Đã bỏ phim khỏi danh sách" : "Đã thêm vào danh sách xem");
  if (state.view === "watchlist") loadView();
}
async function showDetail(movieId) {
  state.detail = movieId;
  const dialog = $("#movie-dialog");
  $("#movie-detail").textContent = "Đang mở câu chuyện…";
  if (!dialog.open) dialog.showModal();
  try {
    const movie = await api(`/movies/${movieId}`);
    if (state.detail !== movieId || !dialog.open) return;
    const colors = palettes[movie.movie_id % palettes.length];
    const rating = Number(state.profile.ratings[movieId] || 0);
    $("#movie-detail").innerHTML =
      `<div class="eyebrow muted">Cine (cas) phile. / COLLECTION</div><div class="detail-head"><div class="poster alt-${movieId % 4}" style="--cover-bg:linear-gradient(145deg,${colors[0]},${colors[1]})">${poster(movie)}</div><div><h2>${escapeHtml(movie.title)}</h2><div class="detail-badges">${movie.year ?? "—"} · ${escapeHtml(movie.genres.split("|").map(genreLabel).join(" / "))}</div><p>★ ${movie.rating ?? "—"} / 5 từ ${format(movie.rating_count)} đánh giá trong tập huấn luyện Điểm Bayesian: ${movie.bayesian_rating} / 5</p><div class="rating-panel">Đánh giá của bạn <div class="stars" aria-label="Chấm điểm phim">${[1, 2, 3, 4, 5].map((value) => `<button class="${value <= rating ? "rated" : ""}" data-rate="${value}" data-id="${movieId}" aria-label="${value} sao" aria-pressed="${value === rating}">★</button>`).join("")}</div>${rating ? `<button class="remove-rating" data-unrate="${movieId}">Xóa đánh giá (${rating} sao)</button>` : ""}</div></div></div>${externalRatings(movie)}<div class="detail-actions"><button class="primary" data-seed="${movieId}">Tìm phim cùng gu ↗</button><button class="secondary save-button-detail" data-save="${movieId}" aria-pressed="${state.profile.watchlist.includes(movieId)}">${state.profile.watchlist.includes(movieId) ? "✓" : "+"} Danh sách xem</button></div><p class="poster-source">${movie.poster_sources?.length ? `Ảnh phim: ${movie.poster_sources.map((source) => `<a href="${escapeHtml(source.page_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.name)}</a>`).join(" · ")}.` : "Bìa minh họa Cine (cas) phile."} Điểm MovieLens là dữ liệu lịch sử; điểm nguồn bên ngoài hiển thị riêng ở trên.</p><h3 style="font-size:16px;font-weight:500;margin-top:24px">Nếu bạn thích câu chuyện này…</h3><div class="similar-grid">${movie.similar_movies.slice(0, 4).map(card).join("")}</div>`;
  } catch (error) {
    if (state.detail === movieId && dialog.open)
      $("#movie-detail").textContent = error.message;
  }
}
function openTaste() {
  if (!state.stats) {
    toast("Kho phim đang khởi động.");
    return;
  }
  $("#taste-options").innerHTML = state.stats.genres
    .map(
      (g) =>
        `<label class="taste-option"><input type="checkbox" name="genre" value="${escapeHtml(g)}" ${state.profile.genres.some((selected) => selected.toLowerCase() === g.toLowerCase()) ? "checked" : ""}><span>${escapeHtml(genreLabel(g))}</span></label>`,
    )
    .join("");
  $("#taste-dialog").showModal();
}
function externalRatings(movie) {
  const slots = [
    ["Letterboxd", "audience", "Khán giả", 5],
    ["IMDb", "audience", "Khán giả", 10],
    ["Rotten Tomatoes", "critics", "Tomatometer", 100],
    ["Rotten Tomatoes", "audience", "Popcornmeter", 100],
    ["Metacritic", "critics", "Metascore", 100],
    ["Metacritic", "audience", "Khán giả", 10],
  ];
  const extra = (movie.external_ratings || []).find(
    (r) => r.provider === "MUBI",
  );
  if (extra) slots.push(["MUBI", "audience", "Khán giả", 5]);
  return `<section class="external-ratings"><h3>Những góc nhìn về bộ phim</h3><div class="rating-grid">${slots
    .map(([provider, audience, label, scale]) => {
      const r = (movie.external_ratings || []).find(
        (r) => r.provider === provider && r.audience === audience,
      );
      return `<div class="source-rating"><span>${escapeHtml(provider)} · ${label}</span><strong>${r ? `${r.value}${provider === "Rotten Tomatoes" ? "%" : `<small> / ${r.scale}</small>`}` : "—"}</strong>${r ? `<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer">${r.count ? `${typeof r.count === "number" ? format(r.count) + " lượt" : escapeHtml(r.count)} · ` : ""}Xem nguồn ↗</a><small>Kiểm tra ${escapeHtml(r.checked_at?.slice(0, 10) || "—")}${r.via ? ` · qua ${escapeHtml(r.via)}` : ""}</small>` : "<small>Chưa có dữ liệu đã xác minh</small>"}</div>`;
    })
    .join(
      "",
    )}</div><p>Tomatometer và Popcornmeter là tỷ lệ đánh giá tích cực. Metascore là điểm /100. Các thang điểm giữ riêng; dữ liệu là bản chụp theo ngày cập nhật.</p></section>`;
}
let imagePreviewUrl;
$("#image-search-open").addEventListener("click", async () => {
  $("#image-dialog").showModal();
  try {
    const data = await api("/visual-search/status");
    $("#image-coverage").textContent = data.ready
      ? `Kho tham chiếu: ${format(data.indexed_movies)} phim, ${format(data.scene_images)} ảnh cảnh phim, cùng poster. Cảnh chưa có trong kho có thể chưa nhận diện đúng. Ảnh tải lên được xử lý trên máy, không lưu lại.`
      : "Kho ảnh đang được chuẩn bị.";
  } catch (error) {
    $("#image-status").textContent = error.message;
  }
});
$("#scene-file").addEventListener("change", () => {
  if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
  const file = $("#scene-file").files[0];
  $("#scene-preview").hidden = !file;
  if (file) {
    imagePreviewUrl = URL.createObjectURL(file);
    $("#scene-preview").src = imagePreviewUrl;
  }
  $("#image-results").innerHTML = "";
  $("#image-status").textContent = window.cineHosted
    ? "Tìm ảnh lần đầu cần tải khoảng 110 MB mô hình và bộ xử lý; ảnh của bạn không rời trình duyệt."
    : "";
});
$("#image-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#image-submit");
  button.disabled = true;
  $("#image-status").textContent = "Đang đối chiếu khung hình…";
  $("#image-results").innerHTML = "";
  try {
    const file = $("#scene-file").files[0];
    if (!file || file.size > 8 * 1024 * 1024)
      throw new Error("Chọn ảnh JPEG, PNG hoặc WebP nhỏ hơn 8 MB.");
    const body = new FormData();
    body.append("image", file);
    const response = window.cineHosted
      ? await window.cineHosted.searchImage(file, 8)
      : await fetch("/visual-search?k=8", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Không thể đọc ảnh.");
    $("#image-status").textContent = data.notice;
    $("#image-results").innerHTML = data.matches
      .map(
        (movie) =>
          `<div>${card(movie)}<p class="match-score">Tương đồng hình ảnh: ${movie.visual_similarity.toFixed(3)} · ${movie.matched_image_kind === "still" ? "Cảnh phim" : "Poster"} tham chiếu</p><img class="reference-preview" src="${escapeHtml(movie.matched_image_url)}" loading="lazy" referrerpolicy="no-referrer" alt="Ảnh tham chiếu của ${escapeHtml(movie.title)}"></div>`,
      )
      .join("");
  } catch (error) {
    $("#image-status").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
async function renderInsights(token) {
  const stats = state.stats;
  const split = stats.split;
  let report;
  try {
    report = await api("/benchmark");
  } catch {
    report = null;
  }
  if (token !== state.request) return;
  $("#insights").innerHTML = `<div class="stat-grid">${[
    [stats.catalog_size, "Phim trong catalog"],
    [stats.users_count, "Người dùng MovieLens"],
    [split.n_total, "Đánh giá đã làm sạch"],
    [stats.loaded_models.length, "Chế độ gợi ý"],
  ]
    .map(
      ([value, label]) =>
        `<div class="stat"><strong>${format(value)}</strong><span>${label}</span></div>`,
    )
    .join(
      "",
    )}</div><div class="insight-panel"><h3>Học từ quá khứ, kiểm tra trên tương lai.</h3><div class="split-bar">${["train", "val", "test"].map((name) => `<span style="width:${(split["n_" + name] / split.n_total) * 100}%"></span>`).join("")}</div><div class="split-legend">${[
    ["train", "Train"],
    ["val", "Validation"],
    ["test", "Test"],
  ]
    .map(
      ([key, title]) =>
        `<span>${title}: ${format(split["n_" + key])} (${((split["n_" + key] / split.n_total) * 100).toFixed(1)}%)</span>`,
    )
    .join(
      "",
    )}</div><p>Chia theo thời gian từng người dùng; các đánh giá cùng timestamp nằm trong một tập. Toàn bộ điểm cộng đồng và mô hình chỉ học từ train. Validation được dành riêng; benchmark dùng test.</p><p>Đây là kiểm định theo lịch sử từng người dùng, chưa mô phỏng một mốc thời gian toàn cục. Lịch sử đánh giá MovieLens chủ yếu thuộc các phim đến năm 2000; catalog bổ sung có phim đến ${stats.year_max}. Phim mới dùng tín hiệu thể loại khi chưa có lịch sử đánh giá.</p></div><div class="insight-panel"><h3>Benchmark có thể kiểm chứng</h3>${report ? `<p>${report.ranking_users} người dùng có phim test ≥ 4 sao, ứng viên toàn catalog trừ phim train và validation. Cùng tập ứng viên cho mọi thuật toán; độ khám phá bằng 0. Coverage phụ thuộc số người dùng được lấy mẫu.</p><div class="table-scroll"><table><thead><tr><th>Thuật toán</th><th>RMSE</th><th>Precision@10</th><th>Recall@10</th><th>NDCG@10</th><th>p95 (ms)</th></tr></thead><tbody>${report.results.map((row) => `<tr><td>${escapeHtml(row.model)}</td><td>${row.rmse === null ? "—" : row.rmse.toFixed(4)}</td><td>${row.precision.toFixed(4)}</td><td>${row.recall.toFixed(4)}</td><td>${row.ndcg.toFixed(4)}</td><td>${row.latency_p95_ms.toFixed(2)}</td></tr>`).join("")}</tbody></table></div><p>${report.runtime_note ? escapeHtml(report.runtime_note) : ""}</p><p>Đo trên ${format(report.rating_pairs)} cặp đánh giá test với seed ${report.seed}. Điểm xếp hạng không phải xác suất thích phim. Content chỉ được đo ranking vì không có rating calibration.</p>` : "<p>Chưa có báo cáo. Chạy python -m src.cli benchmark để tạo kết quả thực trên dữ liệu của bạn.</p>"}</div><div class="insight-panel"><h3>5 cách tìm một bộ phim hay</h3><p>Bayesian popularity giảm ảnh hưởng của phim có quá ít lượt đánh giá. Content dùng TF-IDF thể loại và hồ sơ sở thích có suy giảm theo thời gian. Item-based CF dùng tương đồng đánh giá giữa phim. Truncated SVD học nhân tố ẩn từ phần dư đánh giá. Hybrid kết hợp tín hiệu còn khả dụng; MMR tái xếp hạng để thêm lựa chọn khác biệt.</p></div>`;
}
document.addEventListener("click", async (event) => {
  const target = event.target.closest("button");
  if (!target) return;
  try {
    if (target.dataset.view) {
      setView(target.dataset.view);
      return;
    }
    if (target.dataset.collection) {
      state.genre = target.dataset.collection;
      renderChips();
      setView("discover");
      $("#section-title").scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      return;
    }
    if (target.dataset.go) {
      setView(target.dataset.go);
      return;
    }
    if (target.dataset.close) {
      $("#" + target.dataset.close).close();
      return;
    }
    if (target.dataset.genre !== undefined) {
      state.genre = target.dataset.genre;
      state.page = 1;
      renderChips();
      loadView();
      return;
    }
    if (target.dataset.movie) {
      showDetail(Number(target.dataset.movie));
      return;
    }
    if (target.dataset.save) {
      target.disabled = true;
      await toggleSave(Number(target.dataset.save));
      target.disabled = false;
      return;
    }
    if (target.dataset.rate) {
      await send(
        `/profiles/${state.profile.profile_id}/ratings/${target.dataset.id}`,
        "PUT",
        { rating: Number(target.dataset.rate) },
      );
      state.profile.ratings[target.dataset.id] = Number(target.dataset.rate);
      if ($("#movie-dialog").open && state.detail === Number(target.dataset.id))
        await showDetail(Number(target.dataset.id));
      if (["foryou", "ratings"].includes(state.view)) loadView();
      toast("Đã lưu đánh giá. Gu phim được cập nhật.");
      return;
    }
    if (target.dataset.unrate) {
      await send(
        `/profiles/${state.profile.profile_id}/ratings/${target.dataset.unrate}`,
        "DELETE",
      );
      delete state.profile.ratings[target.dataset.unrate];
      if (
        $("#movie-dialog").open &&
        state.detail === Number(target.dataset.unrate)
      )
        showDetail(Number(target.dataset.unrate));
      if (["foryou", "ratings"].includes(state.view)) loadView();
      return;
    }
    if (target.dataset.seed) {
      const movie = await api(`/movies/${target.dataset.seed}`);
      state.seed = movie;
      $("#movie-dialog").close();
      setView("foryou");
      return;
    }
    if (target.hasAttribute("data-clear-seed")) {
      state.seed = null;
      loadView();
      return;
    }
  } catch (error) {
    target.disabled = false;
    toast(error.message);
  }
});
["#taste-side", "#taste-top", "#taste-hero"].forEach((id) =>
  $(id).addEventListener("click", openTaste),
);
$("#taste-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.submitter;
  button.disabled = true;
  try {
    const genres = [...new FormData(event.currentTarget).getAll("genre")];
    state.profile = await send(
      `/profiles/${state.profile.profile_id}/preferences`,
      "PUT",
      { genres },
    );
    $("#taste-dialog").close();
    setView("foryou");
    toast("Đã lưu gu phim của bạn");
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
  }
});
$("#era").addEventListener("change", () => {
  state.page = 1;
  loadView();
});
$("#sort").addEventListener("change", () => {
  state.page = 1;
  loadView();
});
$("#model").addEventListener("change", loadView);
$("#refresh").addEventListener("click", loadView);
$("#diversity").addEventListener(
  "input",
  () =>
    ($("#diversity-value").textContent =
      Math.round(Number($("#diversity").value) * 100) + "%"),
);
$("#diversity").addEventListener("change", loadView);
$("#previous").addEventListener("click", () => {
  state.page--;
  loadView();
});
$("#next").addEventListener("click", () => {
  state.page++;
  loadView();
});
let searchTimer;
$("#search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.page = 1;
    if (!["discover", "curated"].includes(state.view)) setView("discover");
    else loadView();
  }, 250);
});
document.addEventListener("keydown", (event) => {
  if (
    event.key === "/" &&
    !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName) &&
    !$("dialog[open]")
  ) {
    event.preventDefault();
    $("#search").focus();
  }
});
$("#movie-dialog").addEventListener("close", () => {
  state.detail = null;
});
async function boot() {
  try {
    const statsPromise = api("/stats");
    statsPromise.catch(() => {});
    let profileId;
    try {
      profileId = localStorage.getItem("cine-profile");
    } catch {}
    if (profileId) {
      try {
        state.profile = await api(`/profiles/${profileId}`);
      } catch (error) {
        if (!error.message.includes("Profile not found")) throw error;
      }
    }
    if (!state.profile) state.profile = await send("/profiles", "POST");
    try {
      localStorage.setItem("cine-profile", state.profile.profile_id);
    } catch {
      toast(
        "Trình duyệt không cho phép lưu hồ sơ. Hồ sơ vẫn dùng được trong phiên này.",
      );
    }
    state.stats = await statsPromise;
    renderProfile();
    renderChips();
    $("#catalog-stat").textContent = format(state.stats.catalog_size);
    $("#genre-stat").textContent = state.stats.genres.length;
    loadView();
  } catch (error) {
    $("#status").textContent =
      `Không thể kết nối: ${error.message}. Hãy khởi động máy chủ rồi tải lại trang.`;
    $("#result-count").textContent = "Kết nối chưa sẵn sàng";
  }
}
boot();
