"""Separate capability-limited service. Expose ONLY this port to the VM, never the owner API."""
import hmac
import os
import asyncio
from contextlib import asynccontextmanager, suppress
from uuid import UUID
from fastapi import FastAPI, Request, HTTPException, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from .api import ROOT
from .store import Store
from .meta import Meta
from .reader import create_reader
from .agent import Jobs
from .desktop import Desktop, WorkerEvent
from .stream import desktop_gateway

def create_worker_app():
    token=os.getenv('IRIS_WORKER_TOKEN','')
    if len(token)<32: raise RuntimeError('Set a random IRIS_WORKER_TOKEN of at least 32 characters before starting the worker gateway.')
    store=Store(os.getenv('IRIS_DB',str(ROOT/'iris.sqlite')))
    meta=Meta(store)
    reader=create_reader(store)
    jobs=Jobs(store)
    desktop=Desktop(store)
    @asynccontextmanager
    async def lifespan(app):
        async def sweep():
            while True:
                await asyncio.to_thread(jobs.recover)
                await asyncio.sleep(2)
        task=asyncio.create_task(sweep())
        try: yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError): await task
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    @app.middleware('http')
    async def authenticate(request,call_next):
        if not hmac.compare_digest(request.headers.get('authorization',''),f'Bearer {token}'):
            return JSONResponse({'detail':'Worker authentication required.'},status_code=401)
        if request.url.path == '/claim' or request.url.path.startswith('/jobs/'):
            try: request.state.worker_id=str(UUID(request.headers.get('x-iris-worker-id','')))
            except ValueError: return JSONResponse({'detail':'A worker session ID is required.'},status_code=400)
        return await call_next(request)
    @app.exception_handler(ValueError)
    async def error(request,exc): return JSONResponse({'detail':str(exc)},status_code=400)
    @app.get('/')
    def desk(): return FileResponse(ROOT/'web'/'worker.html')
    @app.websocket('/desktop/stream')
    async def stream(socket:WebSocket):
        if not hmac.compare_digest(socket.headers.get('authorization',''),f'Bearer {token}'):
            await socket.close(code=1008);return
        await desktop_gateway(socket)
    @app.get('/records')
    def records(): return store.records()
    @app.post('/claim')
    def claim(request:Request): return jobs.claim(request.state.worker_id)
    @app.post('/desktop/frame')
    async def frame(request:Request):
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>desktop.MAX_FRAME_BYTES: raise HTTPException(413,'Frame too large.')
        desktop.publish(bytes(data))
        return {'ok':True}
    @app.get('/jobs/{id}')
    def job(id:str): return jobs.get(id)
    @app.post('/jobs/{id}/events')
    def event(id:str, body:WorkerEvent):
        jobs.get(id)
        desktop.event(id,body.action,body.detail)
        return {'ok':True}
    @app.post('/jobs/{id}/step')
    async def step(id:str,request:Request): return await jobs.step(id,await request.json(),meta,request.state.worker_id)
    @app.post('/jobs/{id}/preflight')
    async def preflight(id:str,request:Request):
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>2_900_000: raise HTTPException(413,'Visual review is too large.')
        import json
        try: payload=json.loads(data)
        except (ValueError,UnicodeError): raise ValueError('Invalid visual review payload.') from None
        if not isinstance(payload,dict): raise ValueError('Visual review must be an object.')
        return await jobs.preflight(id,payload,reader,request.state.worker_id)
    @app.post('/jobs/{id}/write')
    async def write(id:str,request:Request): return await jobs.submit(id,await request.json(),reader,request.state.worker_id,channel=request.headers.get('x-iris-write-channel','http'))
    @app.post('/jobs/{id}/heartbeat')
    def heartbeat(id:str,request:Request): return jobs.heartbeat(id,request.state.worker_id)
    @app.post('/jobs/{id}/pause')
    async def pause(id:str,request:Request):
        jobs.heartbeat(id,request.state.worker_id)
        jobs.finish(id,'paused','Worker stopped. Permission revoked. Check the VM and lock a new permission to retry.')
        return {'ok':True}
    return app
