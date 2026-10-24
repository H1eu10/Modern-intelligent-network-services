import os,sys,tempfile,asyncio,json
from pathlib import Path
os.environ['DATABASE_PATH']=str(Path(tempfile.mkdtemp())/'test.db')
sys.path.insert(0,str(Path(__file__).resolve().parent));sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import main
import httpx
farm={'farm_id':'FARM-001','region':'Krasnodar','crop_type':'wheat','area_ha':100,'temperature_avg':20,'precipitation_mm':200,'payment_delay_days':10,'previous_defaults':0,'debt':10000}
results=[]
async def check(client,name,method,url,body,expected,headers=None):
 r=await client.request(method,url,json=body,headers=headers)
 results.append({'test':name,'expected':expected,'actual':r.status_code,'result':'PASS' if r.status_code in expected else 'FAIL','body':r.json() if r.headers.get('content-type','').startswith('application/json') else r.text,'headers':{'X-Request-ID':r.headers.get('X-Request-ID'),'X-Process-Time':r.headers.get('X-Process-Time')}})
 return r
async def run():
 async with main.lifespan(main.app):
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://testserver') as client:
   await check(client,'01 health','GET','/health',None,[200])
   pred=await check(client,'02 valid predict','POST','/predict',farm,[200],headers={'X-Request-ID':'qa-001'})
   await check(client,'03 negative area','POST','/predict',dict(farm,area_ha=-100),[422])
   await check(client,'04 unknown region','POST','/predict',dict(farm,region='Unknown'),[400])
   await check(client,'05 existing id','GET','/predictions/'+pred.json()['request_id'],None,[200])
   await check(client,'06 unknown id','GET','/predictions/nonexistent-id',None,[404])
   await check(client,'07 valid batch','POST','/batch-predict',{'items':[farm,dict(farm,farm_id='FARM-002')]},[200])
   await check(client,'08 oversized batch','POST','/batch-predict',{'items':[farm]*9},[422])
   await check(client,'09 queued prediction','POST','/predict-queued',farm,[200])
   original=main.inference_queue
   main.inference_queue=asyncio.Queue(maxsize=1)
   await main.inference_queue.put('occupied')
   await check(client,'10 full queue','POST','/predict-queued',farm,[429])
   main.inference_queue=original
   await check(client,'11 weekday pagination','GET','/predictions/by-weekday?weekday=saturday&page=1&per_page=5',None,[200])
   await check(client,'12 page -1','GET','/predictions/by-weekday?weekday=saturday&page=-1&per_page=5',None,[422])
   await check(client,'13 invalid weekday','GET','/predictions/by-weekday?weekday=holiday',None,[400])
   async def fake_post(url,headers=None,json=None):return httpx.Response(200,json={'model':'auto','choices':[{'message':{'content':'Проверка пройдена: результат модели не изменён.'},'finish_reason':'stop'}],'usage':{'total_tokens':42}},request=httpx.Request('POST',url))
   original_post=main.app.state.llm_client.post
   main.app.state.llm_client.post=fake_post
   await check(client,'14 llm/chat mocked','POST','/llm/chat',{'prompt':'Привет','model':'auto'},[200])
   async def bad_post(url,headers=None,json=None):raise httpx.ConnectError('simulated connection failure',request=httpx.Request('POST',url))
   main.app.state.llm_client.post=bad_post
   await check(client,'15 llm unavailable mocked','POST','/llm/chat',{'prompt':'Привет'},[503])
   main.app.state.llm_client.post=fake_post
   await check(client,'16 predict-with-llm mocked','POST','/predict-with-llm',farm,[200])
   main.app.state.llm_client.post=original_post
   await check(client,'17 queue status','GET','/queue-status',None,[200])
   await check(client,'18 OpenAPI','GET','/openapi.json',None,[200])
   await check(client,'19 seed weekdays','POST','/demo/seed-weekdays?count=70',None,[200])
   await check(client,'20 weekday seeded','GET','/predictions/by-weekday?weekday=monday&page=1&per_page=5',None,[200])
   rid=pred.json()['request_id']
   assert rid=='qa-001'
   assert results[1]['headers']['X-Request-ID']==rid
   assert all(x['result']=='PASS' for x in results)
  Path('/mnt/data/agro_lab2/qa_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
  print('PASS',len(results),'/',len(results))
asyncio.run(run())
