"""Direct desktop transport. Frames never pass through SQLite or an event queue."""
import asyncio
from contextlib import suppress
from fastapi import WebSocket
from websockets.asyncio.client import connect


async def together(*coroutines):
    tasks=[asyncio.create_task(c) for c in coroutines]
    try:
        done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
        for task in done: task.result()
    finally:
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)


async def desktop_gateway(socket:WebSocket):
    await socket.accept()
    writer=None
    try:
        reader,writer=await asyncio.wait_for(asyncio.open_connection('browser',5900),timeout=5)
        async def upstream():
            while True:
                data=await socket.receive_bytes()
                writer.write(data);await writer.drain()
        async def downstream():
            while data:=await reader.read(262144): await socket.send_bytes(data)
        await together(upstream(),downstream())
    except Exception:
        with suppress(Exception): await socket.close(code=1011)
    finally:
        if writer:
            writer.close()
            with suppress(Exception): await writer.wait_closed()


async def desktop_owner(socket:WebSocket,token:str):
    # Same-origin websocket protection is separate from HTTP middleware.
    origin=socket.headers.get('origin','')
    expected=f"http://{socket.headers.get('host','')}"
    if origin!=expected or not token:
        await socket.close(code=1008);return
    await socket.accept()
    try:
        async with connect('ws://gateway:8766/desktop/stream',additional_headers={'Authorization':f'Bearer {token}'},max_size=4_000_000,compression=None) as remote:
            async def upstream():
                while True: await remote.send(await socket.receive_bytes())
            async def downstream():
                async for data in remote: await socket.send_bytes(data)
            await together(upstream(),downstream())
    except Exception:
        with suppress(Exception): await socket.close(code=1011)
