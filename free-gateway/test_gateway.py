import asyncio,base64,os,importlib.util
from pathlib import Path
os.environ['A30_TUNNEL_KEY']='synthetic-integration-key-for-tests-only-1234567890'
from aiohttp import web,ClientSession,ClientResponseError
import server

async def check():
    runner=web.AppRunner(server.app);await runner.setup()
    site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    port=site._server.sockets[0].getsockname()[1];base=f'http://127.0.0.1:{port}'
    try:
        async with ClientSession() as client:
            async with client.get(base+'/api/me') as r:assert r.status==503
            async with client.get(base+'/admin/api/state') as r:assert r.status==503
            async with client.get(base+'/',allow_redirects=False) as r:assert r.status==302 and r.headers['Location']=='/admin'
            for path in ['/admin/api/not-allowed','/admin/files','/etc/passwd']:
                async with client.get(base+path) as r:assert r.status==404,path
            try:
                await client.ws_connect(base+'/_a30/connect')
                raise AssertionError('Unauthenticated tunnel accepted')
            except ClientResponseError as error:assert error.status==401
            async with client.ws_connect(base+'/_a30/connect',headers={'X-A30-Key':os.environ['A30_TUNNEL_KEY']}) as ws:
                async with client.get(base+'/health') as r:assert (await r.json())['backend_connected']
                pending=asyncio.create_task(client.post(base+'/api/login',data=b'{"synthetic":true}',headers={'Authorization':'Bearer test-only'}))
                job=await ws.receive_json(timeout=3)
                assert job['path']=='/api/login' and job['method']=='POST'
                assert base64.b64decode(job['body'])==b'{"synthetic":true}'
                assert job['headers']['Authorization']=='Bearer test-only'
                await ws.send_json({'id':job['id'],'status':401,'headers':{'Content-Type':'application/json'},'body':base64.b64encode(b'{"ok":false}').decode()})
                r=await pending
                async with r:assert r.status==401 and await r.json()=={'ok':False}
                pending=asyncio.create_task(client.post(base+'/admin/api/login',data=b'{"synthetic":true}'))
                job=await ws.receive_json(timeout=3);assert job['path']=='/admin/api/login'
                await ws.send_json({'id':job['id'],'status':200,'headers':{'Content-Type':'application/json','Set-Cookie':'kids_admin=test-only; HttpOnly; SameSite=Strict; Path=/admin; Max-Age=3600','X-Content-Type-Options':'nosniff'},'body':base64.b64encode(b'{"ok":true}').decode()})
                r=await pending
                async with r:
                    assert r.status==200 and '; Secure' in r.headers['Set-Cookie'] and 'HttpOnly' in r.headers['Set-Cookie'] and 'SameSite=Strict' in r.headers['Set-Cookie']
                    assert r.headers['X-Content-Type-Options']=='nosniff'
                pending=asyncio.create_task(client.post(base+'/admin/api/grants',data=b'{"test":true}',headers={'Cookie':'kids_admin=test-only','X-CSRF-Token':'csrf-test-only'}))
                job=await ws.receive_json(timeout=3)
                assert job['headers']['Cookie']=='kids_admin=test-only' and job['headers']['X-CSRF-Token']=='csrf-test-only'
                await ws.send_json({'id':job['id'],'status':403,'headers':{'Content-Type':'application/json'},'body':base64.b64encode(b'{"ok":false}').decode()})
                r=await pending
                async with r:assert r.status==403
                pending=asyncio.create_task(client.get(base+'/api/me'))
                await ws.receive_json(timeout=3);await ws.close()
                r=await pending
                async with r:assert r.status==502
            async with client.get(base+'/api/me') as r:assert r.status==503
        import a30_agent
        for path in ['https://example.org/api/me','//example.org/api/me','/admin/files','/api/../admin']:
            try:a30_agent.forward({'id':'test','method':'GET','path':path,'body':''});raise AssertionError(path)
            except ValueError:pass
        print('PASS: exact admin allowlist; Secure/HttpOnly/SameSite cookies; CSRF forwarding and 403 preserved; secret tunnel authentication; offline/reconnect; bearer and POST body; external URL denial')
    finally:await runner.cleanup()

asyncio.run(check())
