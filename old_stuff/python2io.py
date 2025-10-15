#!/usr/bin/env python

import os
import codecs

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