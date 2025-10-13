#!/usr/bin/env python

import sys
import os
import codecs
import fcntl

def WriteFile(filePath, contents, binary):
    filePath = os.path.realpath(filePath)
    if binary:
        with open(filePath, "wb") as f:
            f.write(contents)
    else:
        with codecs.open(filePath, "w", "utf-8") as f:
            f.write(contents)
def ReadFile(filePath, defaultContents=None, binary=False):
    filePath = os.path.realpath(filePath)
    if not os.path.exists(filePath):
        if defaultContents != None:
            return defaultContents
    if binary:
        with open(filePath, "rb") as f:
            return f.read()
    else:
        with codecs.open(filePath, "r", "utf-8") as f:
            return f.read()

def FS_SendMessage(inputFile, outputFile, message):
    while True:
        fd = os.open(inputFile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)

# Wrap the raw fd in a Python file object
with os.fdopen(fd, "wb") as f:
    # Take an exclusive lock so no one (including the server) can read it yet
    fcntl.flock(f, fcntl.LOCK_EX)
    try:
        # Write safely under the lock
        f.write(content)
        f.flush()
        os.fsync(f.fileno())  # ensure contents hit disk
        print("Client wrote and locked file.")
    finally:
        # Release lock automatically when file is closed
        fcntl.flock(f, fcntl.LOCK_UN)
print("Client released lock and closed file.")


def Main():
    ONIDBOT_DIR = "/nfs/stak/users/christj/ONIDbot"
    API_IN_FILE_PATH = os.path.join(ONIDBOT_DIR, "api_in_file")
    API_OUT_FILE_PATH = os.path.join(ONIDBOT_DIR, "api_out_file")

    if (len(sys.argv) < 2):
        print("Error: The code given was blank. Please try clicking the link again.")
        return 0

    code = " ".join(sys.argv[1:])
    print("Code: " + code)

    raise Exception("noimpla")

    input_path = os.path.join(INPUT_DIR, code)
    output_path = os.path.join(OUTPUT_DIR, code)

    WriteFile(input_path, code, False)

    while not os.path.exists(output_path):
        pass # spin

    print(ReadFile(output_path, "Output file does not exist!", False))

print("Content-Type: text/plain")
print("")
try:
    sys.exit(Main())
except Exception as ex:
    print("Error: An internal exception occured please try again.")