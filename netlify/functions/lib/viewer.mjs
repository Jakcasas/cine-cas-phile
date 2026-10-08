import { ValidationError } from './engine.mjs';
export function viewerRecommendations(engine, p) {
  engine.validate({...p,ratings:Object.fromEntries(Object.entries(p.ratings || {}).map(([id,r])=>[id,Math.max(1,r)])),model:'content'});
  const survey=p.survey || {};
  const avoided=new Set(survey.avoid || []), preferred=new Set(p.preferred_genres || []);
  const exclude=new Set([...(p.exclude_ids || []),...Object.keys(p.ratings || {}).map(Number)]);
  const seeds=(p.seed_ids || []).map(id=>engine.movie(id));
  const weights=new Map([...preferred].map(g=>[g,3]));
  for(const [id,r] of Object.entries(p.ratings || {})) if(r>=4) for(const g of engine.movie(id).genres.split('|'))weights.set(g,(weights.get(g)||0)+1);
  for(const movie of seeds)for(const g of movie.genres.split('|'))weights.set(g,(weights.get(g)||0)+3);
  const moods={gentle:['Romance','Comedy',"Children's"],intense:['Thriller','Crime','Mystery'],wonder:['Sci-Fi','Fantasy','Adventure'],thoughtful:['Drama','Documentary']};
  for(const g of moods[survey.mood] || [])weights.set(g,(weights.get(g)||0)+2);
  const minimum=Number(p.minimum_rating || 0);
  if(!Number.isFinite(minimum)||minimum<0||minimum>5)throw new ValidationError('Invalid minimum rating');
  const rows=engine.d.movies.filter(m=>!exclude.has(m.movie_id)&&!seeds.some(s=>s.movie_id===m.movie_id)&&(!p.genre || m.genres.split('|').includes(p.genre))&&(!p.year_min || m.year>=p.year_min)&&(!p.year_max || m.year<=p.year_max)&&!m.genres.split('|').some(g=>avoided.has(g))&&(!minimum || m.rating!=null&&m.rating>=minimum)).map(m=>{
    const matching=m.genres.split('|').filter(g=>weights.has(g));
    const taste=matching.reduce((s,g)=>s+weights.get(g),0);
    const community=m.bayesian_rating || m.rating || 0;
    return {...m,score:taste+community*.3,reason:matching.length?'Hợp với thể loại bạn thích: '+matching.join(', '):m.rating_count?'Được khán giả yêu thích':'Một câu chuyện để khám phá',matching_genres:matching};
  }).sort((a,b)=>b.score-a.score||(b.rating_count||0)-(a.rating_count||0)||b.year-a.year);
  const maximum=rows[0]?.score || 1;
  const recommendations=rows.slice(0,p.k || 20).map(m=>({...m,score:m.score/maximum}));
  return {recommendations,count:recommendations.length,total:rows.length,notice:rows.length?'Gợi ý theo câu trả lời và phim bạn đã chấm sao.':'Không có phim khớp tất cả lựa chọn. Thử nới thời kỳ hoặc mức sao.'};
}
