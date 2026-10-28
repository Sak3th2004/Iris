"""Separate capability-limited service. Expose ONLY this port to the VM, never the owner API."""
import hmac
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from .api import ROOT
from .store import Store
from .meta import Meta
from .agent import Jobs
from .desktop import Desktop, WorkerEvent

def create_worker_app():
    token=os.getenv('IRIS_WORKER_TOKEN','')
    if len(token)<32: raise RuntimeError('Set a random IRIS_WORKER_TOKEN of at least 32 characters before starting the worker gateway.')
    store=Store(os.getenv('IRIS_DB',str(ROOT/'iris.sqlite')))
    meta=Meta(store)
    jobs=Jobs(store)
    desktop=Desktop(store)
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    @app.middleware('http')
    async def authenticate(request,call_next):
        if not hmac.compare_digest(request.headers.get('authorization',''),f'Bearer {token}'):
            return JSONResponse({'detail':'Worker authentication required.'},status_code=401)
        return await call_next(request)
    @app.exception_handler(ValueError)
    async def error(request,exc): return JSONResponse({'detail':str(exc)},status_code=400)
    @app.get('/')
    def desk(): return FileResponse(ROOT/'web'/'worker.html')
    @app.get('/records')
    def records(): return store.records()
    @app.post('/claim')
    def claim(): return jobs.claim()
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
    async def step(id:str,request:Request): return await jobs.step(id,await request.json(),meta)
    @app.post('/jobs/{id}/write')
    async def write(id:str,request:Request): return await jobs.submit(id,await request.json(),meta)
    @app.post('/jobs/{id}/pause')
    async def pause(id:str): jobs.finish(id,'paused','Worker stopped. Check the VM and lock a new permission to retry.'); return {'ok':True}
    return app
