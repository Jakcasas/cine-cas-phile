import { readFileSync } from 'node:fs';
import { MongoClient } from 'mongodb';
process.loadEnvFile('.env');
const uri=process.env.MONGODB_URI || `mongodb+srv://${encodeURIComponent(process.env.MONGODB_USER)}:${encodeURIComponent(process.env.MONGODB_PASSWORD)}@${process.env.MONGODB_HOST}/${process.env.MONGODB_DB || 'cinecasphile'}?retryWrites=true&w=majority&appName=CineCasPhile`;
const client=new MongoClient(uri,{maxPoolSize:3,serverSelectionTimeoutMS:12000});
try{
  await client.connect();const db=client.db(process.env.MONGODB_DB || 'cinecasphile');
  const schemas=JSON.parse(readFileSync('netlify/functions/data/club-schema.json','utf8'));
  for(const [name,schema]of Object.entries(schemas)){
    try{await db.createCollection(name,{validator:{$jsonSchema:schema}});}
    catch(error){if(error.code!==48)throw error;await db.command({collMod:name,validator:{$jsonSchema:schema}});}
  }
  await db.collection('films').createIndex({movie_id:1},{unique:true});
  const movies=JSON.parse(readFileSync('data/catalog/movies.json','utf8'));
  for(let i=0;i<movies.length;i+=250)await db.collection('films').bulkWrite(movies.slice(i,i+250).map(movie=>({replaceOne:{filter:{movie_id:movie.movie_id},replacement:movie,upsert:true}})));
  console.log(`MongoDB: imported ${movies.length} film JSON documents; applied ${Object.keys(schemas).length} collection schemas. No credentials printed.`);
}catch(error){console.error('MongoDB import failed: '+error.name+' / '+(error.code || 'unknown'));process.exitCode=1;}finally{await client.close();}
