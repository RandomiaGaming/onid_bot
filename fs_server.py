#!/usr/bin/env python

import os
import fcntl

def RunServer(inputPath, outputPath, callback):
    # Start by deleting both input and output for a fresh start
    if os.path.exists(inputPath):
        os.unlink(inputPath)
    if os.path.exists(outputPath):
        os.unlink(outputPath)
    # Then run the main request processing loop
    print(f"Server is now waiting for input from \"{inputPath}\" and writting output to \"{outputPath}\".")
    while True:
        # Wait for input to be created
        while not os.path.exists(inputPath):
            continue
        # Wait for input to be size > 0
        while not os.stat(inputPath).st_size > 0:
            continue
        # Open input
        inputFD = os.open(inputPath, os.O_RDONLY, 0o644)
        # Wait for lock on input file
        fcntl.flock(inputFD, fcntl.LOCK_EX)
        # Wrap input in python stream
        inputFile = os.fdopen(inputFD, "r", encoding="UTF-8")
        # Read input
        inputStr = inputFile.read()
        # Call callback
        outputStr = callback(inputStr)
        print(f"Client said \"{inputStr}\" responding with \"{outputStr}\".")
        # Wait for output to be deleted
        while os.path.exists(outputPath):
            continue
        # Create output
        while True:
            try:
                outputFD = os.open(outputPath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
                break
            except:
                continue
        # Lock output
        fcntl.flock(outputFD, fcntl.LOCK_EX)
        # Wrap output in python stream
        outputFile = os.fdopen(outputFD, "w", encoding="UTF-8")
        # Write output
        outputFile.write(outputStr)
        outputFile.flush()
        # Unlock output
        fcntl.flock(outputFD, fcntl.LOCK_UN)
        # Close output
        outputFile.close()
        # Wait for output to be deleted for up to 10 seconds
        while os.path.exists(outputPath):
            continue
        # Unlock input
        fcntl.flock(inputFD, fcntl.LOCK_UN)
        # Close input
        inputFile.close()
        # Delete input
        os.unlink(inputPath)

def callback(inputStr):
    return f"You said {inputStr}"
RunServer("./input", "./output", callback)