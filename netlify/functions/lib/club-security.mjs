import { randomBytes, scryptSync, timingSafeEqual, createHash } from 'node:crypto';
export const token = () => randomBytes(32).toString('base64url');
export const digest = value => createHash('sha256').update(value).digest('hex');
export class ClubError extends Error { constructor(status, message) { super(message); this.status = status; } }
export function text(value, min, max, label = 'Nội dung') {
  if (typeof value !== 'string') throw new ClubError(422, `${label} không hợp lệ.`);
  const result = value.normalize('NFC').trim();
  if (result.length < min || result.length > max) throw new ClubError(422, `${label} cần từ ${min} đến ${max} ký tự.`);
  return result;
}
export function email(value) {
  const result = text(value, 3, 254, 'Email').toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(result)) throw new ClubError(422, 'Email không hợp lệ.');
  return result;
}
export function passwordHash(value) {
  text(value, 12, 128, 'Mật khẩu');
  const salt = randomBytes(16).toString('hex');
  return `${salt}:${scryptSync(value, salt, 64).toString('hex')}`;
}
export function passwordMatches(value, encoded) {
  if (typeof value !== 'string' || value.length > 128) return false;
  const [salt, hash] = encoded.split(':');
  const actual = scryptSync(value, salt, 64), expected = Buffer.from(hash, 'hex');
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}
export function safeProfile(p, engine) {
  if(!Array.isArray(p.genres || []))throw new ClubError(422,'Thể loại cần là một danh sách.');
  if(!p.ratings || typeof p.ratings!=='object' || Array.isArray(p.ratings))throw new ClubError(422,'Đánh giá không hợp lệ.');
  const ids = values => [...new Set(values)].filter(id => Number.isInteger(id) && engine.mi.has(id)).slice(0, 5000);
  const watchlist = ids(Array.isArray(p.watchlist) ? p.watchlist : []);
  const seen = ids(Array.isArray(p.seen) ? p.seen : []);
  const ratings = {};
  for (const [id, score] of Object.entries(p.ratings || {})) {
    if (!engine.mi.has(Number(id)) || !Number.isFinite(score) || score < .5 || score > 5 || score * 2 % 1)
      throw new ClubError(422, 'Điểm phim phải từ 0,5 đến 5 sao, mỗi bước 0,5.');
    ratings[id] = score;
  }
  const genres = [...new Set(p.genres || [])];
  if (genres.length > 18 || genres.some(g => !engine.d.genres.includes(g))) throw new ClubError(422, 'Thể loại không hợp lệ.');
  const survey = p.survey || {};
  if(typeof survey!=='object' || Array.isArray(survey) || !Array.isArray(survey.avoid || []) || (survey.avoid || []).some(g=>!engine.d.genres.includes(g)))throw new ClubError(422,'Khảo sát không hợp lệ.');
  if(genres.some(g=>(survey.avoid || []).includes(g)))throw new ClubError(422,'Một thể loại đang được chọn cả yêu thích và muốn tránh. Hãy điều chỉnh khảo sát.');
  if(!Array.isArray(survey.seed_ids || []) || (survey.seed_ids || []).length>5 || (survey.seed_ids || []).some(id=>!engine.mi.has(id)))throw new ClubError(422,'Phim tham chiếu không hợp lệ.');
  if (JSON.stringify(survey).length > 8000) throw new ClubError(422, 'Khảo sát quá dài.');
  return {watchlist, seen, ratings, genres, survey};
}
export function publicUser(user) { return {id: user.id, name: user.name, guest: user.provider === 'guest', role: user.role || 'member'}; }
