import assert from "node:assert/strict";
import { loadEngine } from "../netlify/functions/lib/engine.mjs";
import { handler } from "../netlify/functions/api.mjs";
let input = "";
for await (const chunk of process.stdin) input += chunk;
const fixtures = JSON.parse(input),
  engine = loadEngine();
const report = [];
for (const fixture of fixtures) {
  const actual = engine.recommend(fixture.request);
  const expected = fixture.expected;
  assert.equal(actual.length, expected.length);
  const errors = [];
  let sameOrder = true;
  for (let i = 0; i < actual.length; i++) {
    sameOrder &&= actual[i].movie_id === expected[i].movie_id;
    errors.push(Math.abs(actual[i].score - expected[i].score));
  }
  assert.ok(Math.max(...errors) < 1e-4, `${fixture.name}: score mismatch`);
  // Equal-score ties may differ at Float32 rounding boundaries.
  if (!sameOrder) {
    const scores = new Map(expected.map((m) => [m.movie_id, m.score]));
    for (const m of actual)
      assert.ok(
        scores.has(m.movie_id) &&
          Math.abs(m.score - scores.get(m.movie_id)) < 1e-4,
      );
  }
  assert.equal(new Set(actual.map((m) => m.movie_id)).size, actual.length);
  report.push({
    case: fixture.name,
    same_order: sameOrder,
    max_score_error: Math.max(...errors),
  });
}
for (const path of ["/api/health", "/api/stats", "/api/movies?q="]) {
  const response = await handler({
    path: path.split("?")[0],
    httpMethod: "GET",
    queryStringParameters: {},
  });
  assert.equal(response.statusCode, 200);
}
const invalid = await handler({
  path: "/api/discover",
  httpMethod: "POST",
  body: JSON.stringify({ model: "wrong" }),
});
assert.equal(invalid.statusCode, 422);
for (const body of [
  { k: 2.5 },
  { k: "10" },
  { diversity: "bad" },
  { year_min: "bad" },
  { ratings: [] },
  { seed_ids: "bad" },
  { preferred_genres: "bad" },
]) {
  const result = await handler({
    path: "/api/discover",
    httpMethod: "POST",
    body: JSON.stringify(body),
  });
  assert.equal(result.statusCode, 422, JSON.stringify(body));
}
const missing = await handler({
  path: "/api/movies/99999999",
  httpMethod: "GET",
});
assert.equal(missing.statusCode, 404);
for (const body of [
  null,
  [],
  { preferred_genres: [null] },
  { exclude_ids: "wrong" },
  { q: {} },
  { user_id: 1.5 },
]) {
  const result = await handler({
    path: "/api/discover",
    httpMethod: "POST",
    body: JSON.stringify(body),
  });
  assert.equal(result.statusCode, 422);
}
assert.equal(
  (await handler({ path: "/api/discover", httpMethod: "POST", body: "{" }))
    .statusCode,
  400,
);
assert.equal(
  (await handler({ path: "/api/health", httpMethod: "POST" })).statusCode,
  405,
);
assert.equal(
  (
    await handler({
      path: "/api/movies",
      httpMethod: "GET",
      queryStringParameters: { page: "0" },
    })
  ).statusCode,
  422,
);
assert.ok(
  engine
    .catalog({ q: "la mesias" })
    .movies.some((m) => m.title === "La Mesías"),
);
assert.equal(
  JSON.parse((await handler({ path: "/api/health", httpMethod: "GET" })).body)
    .version,
  "1.0.0-netlify",
);
console.log(JSON.stringify({ passed: true, cases: report }));
