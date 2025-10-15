#!/usr/bin/env python

import asyncio
import sys

StartMarker = "##Begin ONIDbot Output##"
EndMarker = "##End ONIDbot Output##"
PORT = 35568

async def Main():
    print(StartMarker)
    try:
        if len(sys.argv) != 2:
            print("Error: Incorrect number of arguments given to API broker.")
            return
        code = sys.argv[1]
        if not set(code).issubset(set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")):
            print("Error: Illegal chars given to API broker.")
            return

        reader, writer = await asyncio.open_connection("127.0.0.1", PORT)
        writer.write((code + "\n").encode("utf-8"))
        response = (await reader.read()).decode("utf-8")
        writer.close()
        print(response)
    except:
        print("Error: Unknown error in API broker.")
    finally:
        print(EndMarker)
asyncio.run(Main())