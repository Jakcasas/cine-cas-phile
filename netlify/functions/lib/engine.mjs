import { readFileSync, existsSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { join } from "node:path";
import films from '../../../web/film-utils.js';

const dot = (a, b) => a.reduce((sum, x, i) => sum + x * b[i], 0);
const norm = (a) => Math.sqrt(dot(a, a));
const normalize = (a) => {
  const min = Math.min(...a),
    max = Math.max(...a);
  return a.map((x) => (max - min > 1e-12 ? (x - min) / (max - min) : 0.5));
};
const clamp = (x) => Math.max(1, Math.min(5, x));
export class ValidationError extends Error {}
export class Engine {
  constructor(data) {
    this.d = data;
    this.mi = new Map(data.movie_ids.map((id, i) => [id, i]));
    this.ui = new Map(data.user_ids.map((id, i) => [id, i]));
    this.gi = new Map(data.genres.map((g, i) => [g.toLowerCase(), i]));
  }
  movie(mid) {
    const i = this.mi.get(Number(mid));
    if (i === undefined) throw new ValidationError("Movie not found");
    return { ...this.d.movies[i] };
  }
  validate(p) {
    if (!p || typeof p !== "object" || Array.isArray(p))
      throw new ValidationError("Invalid request");
    if(p.release!=null && !['all','released','recent','upcoming','screening','vn-now','vn-upcoming'].includes(p.release))throw new ValidationError('Lịch phát hành chưa đúng.');
    if(p.release_region && !Object.hasOwn(films.regions,p.release_region))throw new ValidationError('Quốc gia phát hành chưa đúng.');
    for (const key of ["preferred_genres", "seed_ids", "exclude_ids"])
      if (p[key] != null && (!Array.isArray(p[key]) || p[key].length > 5000))
        throw new ValidationError("Invalid preferences");
    if (p.user_id != null && (!Number.isInteger(p.user_id) || p.user_id < 1))
      throw new ValidationError("Invalid MovieLens user");
    for (const key of ["genre", "q", "source", "sort"])
      if (p[key] != null && (typeof p[key] !== "string" || p[key].length > 500))
        throw new ValidationError("Invalid " + key);
    if (
      p.ratings != null &&
      (typeof p.ratings !== "object" || Array.isArray(p.ratings))
    )
      throw new ValidationError("Invalid ratings");
    for (const key of ["year_min", "year_max"])
      if (
        p[key] != null &&
        (!Number.isInteger(p[key]) || p[key] < 1800 || p[key] > 2200)
      )
        throw new ValidationError("Invalid years");
    if (!Number.isInteger(p.k ?? 12) || !Number.isFinite(p.diversity ?? 0.2))
      throw new ValidationError("Invalid k or diversity");
    if (
      p.model &&
      !["hybrid", "collaborative", "svd", "content", "popularity"].includes(
        p.model,
      )
    )
      throw new ValidationError("Unknown model");
    for (const g of [
      ...(p.preferred_genres || []),
      ...(p.genre ? [p.genre] : []),
    ])
      if (typeof g !== "string" || !this.gi.has(g.toLowerCase()))
        throw new ValidationError("Unknown genre");
    if (p.year_min != null && p.year_max != null && p.year_min > p.year_max)
      throw new ValidationError("Invalid years");
    if (
      (p.k ?? 12) < 1 ||
      (p.k ?? 12) > 50 ||
      (p.diversity ?? 0.2) < 0 ||
      (p.diversity ?? 0.2) > 1
    )
      throw new ValidationError("Invalid k or diversity");
    for (const id of p.seed_ids || [])
      if (!this.mi.has(Number(id)))
        throw new ValidationError("Unknown seed movie");
    if (Object.keys(p.ratings || {}).length > 5000)
      throw new ValidationError("Too many ratings");
    for (const [mid, value] of Object.entries(p.ratings || {}))
      if (
        !this.mi.has(Number(mid)) ||
        !Number.isFinite(value) ||
        value < 1 ||
        value > 5
      )
        throw new ValidationError("Invalid personal rating");
  }
  signals(p) {
    this.validate(p);
    const d = this.d;
    const known = this.ui.has(Number(p.user_id));
    const uid = this.ui.get(Number(p.user_id));
    const history = new Map();
    if (known)
      for (let t = d.history_indptr[uid]; t < d.history_indptr[uid + 1]; t++)
        history.set(d.history_indices[t], d.history_data[t]);
    for (const [mid, r] of Object.entries(p.ratings || {}))
      history.set(this.mi.get(Number(mid)), r);
    const seen = new Set(history.keys());
    const personal = Object.keys(p.ratings || {}).length > 0;
    let profile =
      known && !personal ? [...d.profiles[uid]] : d.genres.map(() => 0);
    if (history.size && (personal || !known))
      for (const [i, r] of history)
        for (let g = 0; g < profile.length; g++)
          profile[g] += Math.max(r - 3, 0) * d.features[i][g];
    for (const g of p.preferred_genres || [])
      profile[this.gi.get(g.toLowerCase())] += 1.5;
    for (const id of p.seed_ids || []) {
      const i = this.mi.get(Number(id));
      seen.add(i);
      for (let g = 0; g < profile.length; g++)
        profile[g] += d.features[i][g] * 2;
    }
    const length = norm(profile);
    profile = profile.map((x) => x / Math.max(length, 1e-8));
    const cf = [...d.popularity];
    const mean = history.size
      ? [...history.values()].reduce((a, b) => a + b, 0) / history.size
      : 0;
    if (history.size)
      for (let i = 0; i < d.movies.length; i++) {
        let den = 0,
          num = 0;
        for (
          let t = d.similarities_indptr[i];
          t < d.similarities_indptr[i + 1];
          t++
        ) {
          const j = d.similarities_indices[t];
          if (!history.has(j)) continue;
          const w = d.similarities_data[t];
          den += w;
          num += w * (history.get(j) - mean);
        }
        if (den > 1e-8) cf[i] = mean + num / den;
      }
    const signals = {
      popularity: d.popularity,
      content: d.features.map((f) => dot(f, profile)),
      collaborative: cf.map(clamp),
      svd: known
        ? d.item_factors.map((f, i) =>
            clamp(
              d.global_mean +
                d.user_bias[uid] +
                d.item_bias[i] +
                dot(f, d.user_factors[uid]),
            ),
          )
        : d.popularity,
    };
    return {
      signals,
      profile,
      seen,
      known,
      hasHistory: history.size > 0,
      hasContent: length > 0,
    };
  }
  recommend(p) {
    const d = this.d,
      { signals, profile, seen, known, hasHistory, hasContent } =
        this.signals(p);
    const model = p.model || "hybrid",
      k = p.k ?? 12,
      div = p.diversity ?? 0.2;
    for (const mid of p.exclude_ids || [])
      if (this.mi.has(Number(mid))) seen.add(this.mi.get(Number(mid)));
    const candidates = d.movies
      .map((_, i) => i)
      .filter(
        (i) =>
          !seen.has(i) &&
          (!p.genre || d.features[i][this.gi.get(p.genre.toLowerCase())] > 0) &&
          (p.year_min == null || d.movies[i].year >= p.year_min) &&
          (p.year_max == null || d.movies[i].year <= p.year_max),
      );
    if (!candidates.length) return [];
    const normalized = Object.fromEntries(
      Object.entries(signals).map(([key, values]) => [
        key,
        normalize(candidates.map((i) => values[i])),
      ]),
    );
    const weights = {
      collaborative: hasHistory ? 0.35 : 0,
      svd: known ? 0.25 : 0,
      content: hasContent ? 0.25 : 0,
      popularity: 0.15,
    };
    const total = Object.values(weights).reduce((a, b) => a + b, 0);
    const effective =
      (model === "svd" && !known) ||
      (model === "collaborative" && !hasHistory) ||
      (model === "content" && !hasContent)
        ? "popularity"
        : model;
    const scores =
      model === "hybrid"
        ? candidates.map(
            (_, i) =>
              Object.entries(weights).reduce(
                (sum, [key, w]) => sum + w * normalized[key][i],
                0,
              ) / total,
          )
        : normalized[effective];
    const pool = candidates
      .map((i, j) => ({ i, score: scores[j] }))
      .sort((a, b) => b.score - a.score || a.i - b.i)
      .slice(0, Math.max(200, k * 5));
    const penalties = pool.map(() => 0),
      selected = [],
      available = new Set(pool.map((_, i) => i));
    for (let n = 0; n < Math.min(k, pool.length); n++) {
      let choice = -1,
        best = -Infinity;
      for (const j of available) {
        const value = (1 - div) * pool[j].score - div * penalties[j];
        if (value > best) {
          best = value;
          choice = j;
        }
      }
      available.delete(choice);
      selected.push(choice);
      for (let j = 0; j < pool.length; j++)
        penalties[j] = Math.max(
          penalties[j],
          dot(d.features[pool[j].i], d.features[pool[choice].i]),
        );
    }
    return selected.map((j) => {
      const i = pool[j].i;
      const matches = d.movies[i].genres
        .split("|")
        .filter((g) => profile[this.gi.get(g.toLowerCase())] > 0.15);
      const reason =
        model === "content" || (model === "hybrid" && hasContent)
          ? matches.length
            ? `Hợp gu ${matches.slice(0, 3).join(", ")}`
            : "Kết hợp gu phim và điểm cộng đồng"
          : model === "collaborative" && hasHistory
            ? "Gợi ý từ mẫu đánh giá của cộng đồng"
            : model === "svd" && known
              ? "Phù hợp với nhân tố sở thích trong lịch sử MovieLens"
              : "Được cộng đồng đánh giá cao sau hiệu chỉnh Bayesian";
      return {
        ...d.movies[i],
        score: pool[j].score,
        reason,
        ...(["popularity", "collaborative", "svd"].includes(model)
          ? { predicted_rating: signals[model][i] }
          : {}),
      };
    });
  }
  similar(mid, k = 8) {
    const d = this.d,
      index = this.mi.get(Number(mid));
    if (index === undefined) throw new ValidationError("Movie not found");
    const co = d.movies.map(() => 0);
    for (
      let t = d.similarities_indptr[index];
      t < d.similarities_indptr[index + 1];
      t++
    )
      co[d.similarities_indices[t]] = d.similarities_data[t];
    const nc = normalize(co),
      np = normalize(d.popularity);
    return d.movies
      .map((m, i) => ({
        ...m,
        score:
          0.65 * dot(d.features[i], d.features[index]) +
          0.25 * nc[i] +
          0.1 * np[i],
        reason: "Gần nhau về thể loại và hành vi đánh giá",
      }))
      .filter((m) => m.movie_id !== Number(mid))
      .sort((a, b) => b.score - a.score || a.movie_id - b.movie_id)
      .slice(0, k);
  }
  catalog(p) {
    const page = Number(p.page ?? 1),
      size = Number(p.page_size ?? 24);
    if (
      !Number.isInteger(page) ||
      page < 1 ||
      !Number.isInteger(size) ||
      size < 1 ||
      size > 60
    )
      throw new ValidationError("Invalid page");
    this.validate(p);
    const day=undefined; // Shared helpers use the selected market's local calendar day.
    let candidates = this.d.movies.filter(
      (m) =>
        films.matchesRelease(m,p.release,day,p.release_region) &&
        (!p.genre ||
          m.genres
            .split("|")
            .some((g) => g.toLowerCase() === p.genre.toLowerCase())) &&
        (p.year_min == null || m.year >= p.year_min) &&
        (p.year_max == null || m.year <= p.year_max) &&
        (!p.source ||
          m.catalog_sources?.some(
            (s) => p.source === "editorial" || s === p.source,
          )),
    );
    let movies=candidates.filter(m=>films.matchesQuery(m,p.q));
    const sort = p.sort || "popular";
    if (sort === "popular")
      movies.sort((a, b) => b.rating_count - a.rating_count);
    else if (sort === "year") movies.sort((a, b) => b.year - a.year);
    else if (sort === "rating")
      movies.sort(
        (a, b) =>
          (films.audienceRating(b)?.normalized || 0) -
          (films.audienceRating(a)?.normalized || 0) || b.rating_count-a.rating_count,
      );
    else if (sort === "release-date") {
      const dates=new Map(movies.map(m=>[m.movie_id,films.releaseSortDate(m,p.release_region,p.release)]));
      movies.sort((a,b)=>{
        const left=dates.get(a.movie_id),right=dates.get(b.movie_id);
        if(!left || !right)return (left?0:1)-(right?0:1) || b.rating_count-a.rating_count;
        return (p.release==='upcoming'?left.localeCompare(right):right.localeCompare(left)) || b.rating_count-a.rating_count;
      });
    }
    else if (sort === "title")
      movies.sort((a, b) =>
        a.title.toLowerCase().localeCompare(b.title.toLowerCase(), "en"),
      );
    else throw new ValidationError("Invalid sort");
    return {
      total: movies.length,
      page,
      page_size: size,
      movies: movies.slice((page - 1) * size, page * size),
      suggestions: movies.length?[]:films.searchSuggestions(candidates,p.q),
    };
  }
}
let cached;
export function loadEngine() {
  if (cached) return cached;
  const root = process.env.LAMBDA_TASK_ROOT || process.cwd();
  const paths = [
    join(root, "netlify/functions/data/model.json.gz"),
    join(root, "data/model.json.gz"),
  ];
  const path = paths.find((p) => existsSync(p));
  if (!path) throw new Error("Model artifact missing");
  cached = new Engine(
    JSON.parse(gunzipSync(readFileSync(path)).toString("utf8")),
  );
  return cached;
}
