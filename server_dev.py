#!/usr/bin/env python

import asyncio

PORT = 35568

async def HandleClient(reader, writer):
    try:
        code = (await reader.readline()).decode("utf-8").strip()
        response = f"I am the server and I got \"{code}\" as the code."
        writer.write(response.encode("utf-8"))
        writer.close()
    except:
        pass
async def Main():
    server = await asyncio.start_server(HandleClient, "127.0.0.1", PORT)
    async with server:
        await server.serve_forever()
asyncio.run(Main())