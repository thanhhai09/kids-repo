"""Outbound WSS transport. Run on A30s, never deploy this with private config."""
import asyncio,base64,json,sys,urllib.request,urllib.error,urllib.parse
from pathlib import Path
import websockets

EXACT={'/api/login','/api/devicev2','/api/devices/add','/api/fakeinfo','/api/fake-selection','/api/refresh_token','/api/refresh-token','/api/me','/api/validateinfo','/api/firmware-catalog'}
def forward(job):
    method=job.get('method');path=job.get('path','');parsed=urllib.parse.urlsplit(path)
    if method not in ('GET','POST') or parsed.scheme or parsed.netloc or not path.startswith('/') or path.startswith('//'):
        raise ValueError('invalid request')
    if not (parsed.path in EXACT or parsed.path.startswith('/api/ip-region/') or parsed.path.startswith('/api/enrollment/') or parsed.path.startswith('/api/device/')):
        raise ValueError('route denied')
    body=base64.b64decode(job.get('body',''),validate=True)
    if len(body)>2*1024*1024:raise ValueError('body too large')
    headers={k:v for k,v in job.get('headers',{}).items() if k.lower() in ('authorization','content-type','accept')}
    request=urllib.request.Request('http://127.0.0.1:8787'+path,data=body if method=='POST' else None,headers=headers,method=method)
    try:response=urllib.request.urlopen(request,timeout=90)
    except urllib.error.HTTPError as error:response=error
    with response:
        data=response.read(4*1024*1024+1)
        if len(data)>4*1024*1024:raise ValueError('response too large')
        return {'id':job['id'],'status':response.status,'headers':{k:v for k,v in response.headers.items() if k.lower() in ('content-type','content-encoding','cache-control','retry-after')},'body':base64.b64encode(data).decode()}

async def main(config):
    uri=config['gateway'].rstrip('/')
    parsed=urllib.parse.urlsplit(uri)
    if parsed.scheme!='https' or not parsed.hostname:raise ValueError('HTTPS gateway required')
    uri='wss://'+parsed.netloc+'/_a30/connect'
    limit=asyncio.Semaphore(8)
    async def handle(ws,job):
        async with limit:
            try:result=await asyncio.to_thread(forward,job)
            except Exception:result={'id':job.get('id'),'status':502,'headers':{'Content-Type':'application/json'},'body':base64.b64encode(b'{"ok":false,"error":"backend_unavailable"}').decode()}
            try:await ws.send(json.dumps(result))
            except Exception:pass
    while True:
        tasks=set()
        try:
            async with websockets.connect(uri,additional_headers={'X-A30-Key':config['key']},open_timeout=120,max_size=8*1024*1024,ping_interval=30,ping_timeout=60) as ws:
                print('A30s gateway connected',flush=True)
                async for raw in ws:
                    job=json.loads(raw)
                    task=asyncio.create_task(handle(ws,job));tasks.add(task);task.add_done_callback(tasks.discard)
        except Exception as error:print('A30s gateway reconnect:',type(error).__name__,flush=True)
        finally:
            for task in tasks:task.cancel()
            if tasks:await asyncio.gather(*tasks,return_exceptions=True)
        await asyncio.sleep(15)

if __name__=='__main__':
    config_path=Path(sys.argv[1]);asyncio.run(main(json.loads(config_path.read_text())))
