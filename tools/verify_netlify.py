import json
import shutil
import subprocess
from src import settings
from src.api.service import RecommendationService

service=RecommendationService();service.initialize();engine=service.engine
fixtures=[]
for model in ['hybrid','collaborative','svd','content','popularity']:
    for name,fields in [('known',{'user_id':1}),('personal',{'ratings':{2571:5,2858:4},'preferred_genres':['Sci-Fi']})]:
        request={'model':model,'k':10,'diversity':.2,**fields}
        fixtures.append({'name':model+'-'+name,'request':request,'expected':engine.recommend(**request)})
result=subprocess.run([shutil.which('node'),'tools/verify_netlify.mjs'],input=json.dumps(fixtures),text=True,capture_output=True,cwd=settings.ROOT)
if result.returncode:print(result.stderr);raise SystemExit(result.returncode)
report=json.loads(result.stdout);(settings.ROOT/'reports/netlify_parity.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(result.stdout)
