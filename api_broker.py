#!/usr/bin/env python

import asyncio
import sys
import os
import io
import json

StartMarker = "##Begin ONIDbot Output##"
EndMarker = "##End ONIDbot Output##"

def WriteFile(filePath, contents, binary=False):
    filePath = os.path.realpath(os.path.expanduser(filePath))
    dirPath = os.path.dirname(filePath)
    if not os.path.exists(dirPath):
        os.makedirs(dirPath)
    with io.open(filePath, "wb" if binary else "w", encoding=None if binary else "utf-8") as f:
        f.write(contents)
def ReadFile(filePath, defaultContents=None, binary=False):
    filePath = os.path.realpath(os.path.expanduser(filePath))
    if defaultContents != None and not os.path.exists(filePath):
        return defaultContents
    with io.open(filePath, "rb" if binary else "r", encoding=None if binary else "utf-8") as f:
        return f.read()
def SerializeJson(obj):
    return json.dumps(obj)
def DeserializeJson(jsonString):
    return json.loads(jsonString)

ENV = None
def LoadEnv():
    global ENV
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    ENV = DeserializeJson(ReadFile("./environment.json"))

async def Main():
    print(StartMarker)
    try:
        LoadEnv()
        if len(sys.argv) != 2:
            print("Error: Incorrect number of arguments given to API broker.")
            return
        code = sys.argv[1]
        if not set(code).issubset(set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")):
            print("Error: Illegal chars given to API broker.")
            return

        reader, writer = await asyncio.open_connection("127.0.0.1", ENV["local_api_port"])
        writer.write((code + "\n").encode("utf-8"))
        response = (await reader.read()).decode("utf-8")
        writer.close()
        print(response)
    except ConnectionRefusedError:
        print("Error: Connection refused from API broker. Is the server running?")
    except:
        print("Error: Unknown error in API broker.")
    finally:
        print(EndMarker)
asyncio.run(Main())