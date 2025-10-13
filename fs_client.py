#!/usr/bin/env python

import sys
import os
import fcntl
import random

def SendMessage(inputPath, outputPath, inputStr):
    # Wait for input to be deleted
    while os.path.exists(inputPath):
        continue
    # Create input
    while True:
        try:
            inputFD = os.open(inputPath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            break
        except:
            continue
    # Lock input
    fcntl.flock(inputFD, fcntl.LOCK_EX)
    # Wrap input in python stream
    inputFile = os.fdopen(inputFD, "w", encoding="UTF-8")
    # Write input
    inputFile.write(inputStr)
    inputFile.flush()
    # Unlock input
    fcntl.flock(inputFD, fcntl.LOCK_UN)
    # Close input
    inputFile.close()
    # Wait for output to be created
    while not os.path.exists(outputPath):
        continue
    # Wait for output to be size > 0
    while not os.stat(outputPath).st_size > 0:
        continue
    # Open output
    outputFD = os.open(outputPath, os.O_RDONLY, 0o644)
    # Wait for lock on output file
    fcntl.flock(outputFD, fcntl.LOCK_EX)
    # Wrap output in python stream
    outputFile = os.fdopen(outputFD, "r", encoding="UTF-8")
    # Read output
    outputStr = outputFile.read()
    # Unlock output
    fcntl.flock(outputFD, fcntl.LOCK_UN)
    # Close output
    outputFile.close()
    # Delete output
    os.unlink(outputPath)
    # Return output
    return outputStr

def Main():
    if len(sys.argv) < 2:
        print("Error: No value provided for required argument message.")
        return
    inputStr = " ".join(sys.argv[1:])
    i = 0
    while True:
        inputStr = str(random.randint(1, 1000))
        outputStr = SendMessage("./input", "./output", inputStr)
        if outputStr != f"You said {inputStr}":
            print("VIOLATION bad output")
        if i % 1000 == 0:
            print("Getting shi done")
Main()