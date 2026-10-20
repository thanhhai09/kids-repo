"""Stateless HTTPS gateway; account data remains on the user's A30s."""
import asyncio, base64, hmac, json, os, secrets
from aiohttp import web, WSMsgType

KEY = os.environ.get('A30_TUNNEL_KEY', '')
if len(KEY) < 40:
    raise RuntimeError('Set A30_TUNNEL_KEY to a randomly generated secret of at least 40 characters')
agent = None
pending = {}
EXACT = {'/api/login', '/api/devicev2', '/api/devices/add', '/api/fakeinfo',
         '/api/fake-selection', '/api/refresh_token', '/api/refresh-token',
         '/api/me', '/api/validateinfo', '/api/firmware-catalog'}

def allowed(path):
    return path in EXACT or path.startswith('/api/ip-region/') or path.startswith('/api/enrollment/') or path.startswith('/api/device/')

async def tunnel(request):
    global agent
    if not hmac.compare_digest(request.headers.get('X-A30-Key', ''), KEY):
        raise web.HTTPUnauthorized()
    ws = web.WebSocketResponse(max_msg_size=8*1024*1024, heartbeat=30)
    await ws.prepare(request)
    previous = agent
    agent = ws
    if previous is not None:
        await previous.close(code=1000, message=b'Agent reconnected')
    try:
        async for message in ws:
            if message.type == WSMsgType.TEXT:
                try:
                    data = json.loads(message.data)
                    job = pending.get(data.get('id'))
                    if job and job[0] is ws and not job[1].done():
                        job[1].set_result(data)
                except (ValueError, TypeError):
                    continue
    finally:
        if agent is ws:
            agent = None
        for owner, future in list(pending.values()):
            if owner is ws and not future.done():
                future.set_exception(ConnectionError('A30s disconnected'))
    return ws

async def health(request):
    return web.json_response({'ok': True, 'backend_connected': agent is not None and not agent.closed}, headers={'Cache-Control':'no-store'})

async def proxy(request):
    if request.method not in ('GET','POST') or not allowed(request.path):
        raise web.HTTPNotFound()
    current = agent
    if current is None or current.closed:
        return web.json_response({'ok':False,'error':'a30s_offline_retry'}, status=503, headers={'Retry-After':'10'})
    if len(pending)>=64:
        return web.json_response({'ok':False,'error':'busy_retry'},status=503,headers={'Retry-After':'5'})
    body = await request.read()
    identity = secrets.token_hex(16)
    future = asyncio.get_running_loop().create_future()
    pending[identity] = (current, future)
    headers = {k:v for k,v in request.headers.items() if k.lower() in ('authorization','content-type','accept')}
    try:
        await current.send_json({'id':identity,'method':request.method,'path':request.raw_path,'headers':headers,'body':base64.b64encode(body).decode()})
        answer = await asyncio.wait_for(future, 100)
        payload = base64.b64decode(answer.get('body',''), validate=True)
        status = int(answer.get('status',502))
        if status < 100 or status > 599:
            raise ValueError('invalid status')
        response_headers = {k:v for k,v in answer.get('headers',{}).items() if k.lower() in ('content-type','content-encoding','cache-control','retry-after')}
        response_headers['Cache-Control'] = 'no-store'
        return web.Response(status=status, body=payload, headers=response_headers)
    except (asyncio.TimeoutError, ConnectionError, ValueError, TypeError):
        return web.json_response({'ok':False,'error':'a30s_request_unavailable'},status=502)
    finally:
        pending.pop(identity, None)

app = web.Application(client_max_size=2*1024*1024)
app.router.add_get('/health',health)
app.router.add_get('/_a30/connect',tunnel)
app.router.add_route('*','/{tail:.*}',proxy)
if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=int(os.environ.get('PORT','10000')), access_log=None)
