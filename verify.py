import json
import os
import types
import asyncio
from typing import Union

def ReadFile(filePath: str, defaultContents: Union[str, bytes, None] = None, binary: bool = False) -> Union[str, bytes]:
    filePath = os.path.realpath(filePath)
    if not os.path.exists(filePath):
        if defaultContents != None:
            return defaultContents
    with open(filePath, "rb" if binary else "r", encoding=(None if binary else "UTF-8")) as file:
        return file.read()
def DeserializeJson(jsonString: str, simple_namespace: bool = False) -> Union[dict, types.SimpleNamespace]:
    if simple_namespace:
        return json.loads(jsonString, object_hook=lambda obj: types.SimpleNamespace(**obj))
    else:
        return json.loads(jsonString)
ENV: types.SimpleNamespace = None
def LoadEnv() -> None:
    global ENV
    os.chdir(os.path.realpath(os.path.dirname(__file__)))
    ENV = DeserializeJson(ReadFile("./environment.json"), simple_namespace=True)
LoadEnv()

async def main():
    reader, writer = await asyncio.open_connection("127.0.0.1", ENV.local_listen_port)
    
    writer.write("Hello World\n".encode(encoding="UTF-8"))
    await writer.drain()
    
    response = (await reader.readline()).decode(encoding="UTF-8")
    print(f"Server says {response}")

    writer.close()
    await writer.wait_closed()
asyncio.run(main())