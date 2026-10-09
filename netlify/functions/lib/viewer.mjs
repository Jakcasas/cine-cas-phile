import { ValidationError } from './engine.mjs';
import films from '../../../web/film-utils.js';

const moods={gentle:['Romance','Comedy',"Children's"],intense:['Thriller','Crime','Mystery'],wonder:['Sci-Fi','Fantasy','Adventure'],thoughtful:['Drama','Documentary']};
const moodNames={gentle:'nhẹ nhàng, ấm áp',intense:'hồi hộp, bí ẩn',wonder:'kỳ thú, khác lạ',thoughtful:'suy ngẫm, sâu lắng'};

export function viewerRecommendations(engine, p) {
  if (!p || typeof p!=='object' || Array.isArray(p)) throw new ValidationError('Khảo sát không hợp lệ.');
  const ratings=p.ratings ?? {};
  if (typeof ratings!=='object' || Array.isArray(ratings) || Object.values(ratings).some(r=>!Number.isFinite(r)||r<.5||r>5||r*2%1)) throw new ValidationError('Điểm của bạn cần từ 0,5 đến 5 sao.');
  const survey=p.survey ?? {};
  if (typeof survey!=='object' || Array.isArray(survey) || !Array.isArray(survey.avoid || []) || (survey.avoid || []).length>18 || survey.mood && !moods[survey.mood]) throw new ValidationError('Khảo sát không hợp lệ.');
  const canonical=new Map(engine.d.genres.map(g=>[g.toLowerCase(),g]));
  if(!Array.isArray(p.preferred_genres || []))throw new ValidationError('Thể loại cần là một danh sách.');
  const genre=value=>{if(typeof value!=='string' || !canonical.has(value.toLowerCase()))throw new ValidationError('Thể loại chưa đúng.');return canonical.get(value.toLowerCase());};
  const preferred=new Set((p.preferred_genres || []).map(genre)), avoided=new Set((survey.avoid || []).map(genre));
  if ([...preferred].some(g=>avoided.has(g))) throw new ValidationError('Một thể loại đang được chọn cả yêu thích và muốn tránh. Hãy điều chỉnh khảo sát.');
  const filters={...p,seed_ids:p.seed_ids ?? survey.seed_ids ?? []};
  if (survey.era) {
    if (typeof survey.era!=='string' || !/^\d{4}:\d{4}$/.test(survey.era)) throw new ValidationError('Thời kỳ chưa đúng.');
    const [start,end]=survey.era.split(':').map(Number);
    if(start<1800 || end>2200 || start>end)throw new ValidationError('Thời kỳ chưa đúng.');
    if(p.year_min===undefined && p.year_max===undefined){filters.year_min=start;filters.year_max=end;}
  }
  engine.validate({...filters,ratings:Object.fromEntries(Object.entries(ratings).map(([id,r])=>[id,Math.max(1,r)])),model:'content'});
  const excluded=new Set([...(p.exclude_ids || []).map(Number),...Object.keys(ratings).map(Number)]);
  const seeds=filters.seed_ids.map(id=>engine.movie(id));
  const seedGenres=new Set(seeds.flatMap(m=>m.genres.split('|')));
  const likedGenres=new Set(Object.entries(ratings).filter(([,r])=>r>=4).flatMap(([id])=>engine.movie(id).genres.split('|')));
  const moodGenres=new Set(moods[survey.mood] || []);
  const minimum=Number(p.minimum_rating || 0);
  if(!Number.isFinite(minimum)||minimum<0||minimum>5)throw new ValidationError('Mức sao cần từ 0 đến 5.');
  const chosen=p.genre?genre(p.genre):null;
  const rows=[];
  const day=undefined; // Compare releases in the selected market's timezone.
  for (const movie of engine.d.movies) {
    const genres=movie.genres.split('|'), matching=genres.filter(g=>preferred.has(g));
    const audience=films.audienceRating(movie);
    if(!films.matchesRelease(movie,p.release,day,p.release_region) || !['upcoming','vn-upcoming'].includes(p.release) && films.unreleased(movie,day,p.release_region))continue;
    if(excluded.has(movie.movie_id)||seeds.some(s=>s.movie_id===movie.movie_id)||chosen&&!genres.includes(chosen)||filters.year_min!=null&&movie.year<filters.year_min||filters.year_max!=null&&movie.year>filters.year_max||genres.some(g=>avoided.has(g))||preferred.size&&!matching.length||minimum&&(!audience||audience.normalized<minimum)||!films.matchesQuery(movie,p.q))continue;
    // Explicit genres lead; additional genre labels alone do not inflate a film's score.
    const overlap=set=>set.size?genres.filter(g=>set.has(g)).length/set.size:0;
    const quality=movie.rating!=null?(movie.bayesian_rating || movie.rating):(audience?.normalized || 0);
    const score=overlap(preferred)*4+overlap(seedGenres)*2+overlap(moodGenres)+overlap(likedGenres)+quality*.5;
    const reasons=[];
    if(matching.length)reasons.push('Hợp gu '+matching.map(g=>films.genreNames[g] || g).join(', '));
    const similarSeed=seeds.find(s=>s.genres.split('|').some(g=>genres.includes(g)));
    if(similarSeed)reasons.push('cùng thể loại với '+films.displayTitle(similarSeed.title));
    if(moodGenres.size && genres.some(g=>moodGenres.has(g)))reasons.push('cho tâm trạng '+moodNames[survey.mood]);
    if(!reasons.length && likedGenres.size && genres.some(g=>likedGenres.has(g)))reasons.push('Cùng thể loại với phim bạn chấm từ 4 sao');
    if(!reasons.length)reasons.push(audience?'Được chọn theo điểm khán giả từ '+audience.provider:'Một phim chưa có điểm khán giả để khám phá');
    rows.push({...movie,score,reason:reasons.slice(0,2).join(' · '),matching_genres:matching,audience_rating:audience});
  }
  rows.sort((a,b)=>b.score-a.score||(b.audience_rating?.normalized || 0)-(a.audience_rating?.normalized || 0)||(b.rating_count || 0)-(a.rating_count || 0)||a.movie_id-b.movie_id);
  const maximum=rows[0]?.score || 1;
  const recommendations=rows.slice(0,p.k || 20).map(m=>({...m,score:m.score/maximum}));
  return {recommendations,count:recommendations.length,total:rows.length,notice:rows.length?'Gợi ý theo gu phim của bạn. Bộ lọc sao dùng điểm khán giả; nguồn và thang điểm được ghi trên từng phim.':'Không có phim khớp tất cả lựa chọn. Thử bỏ bộ lọc thời kỳ, mức sao hoặc sửa khảo sát.'};
}
