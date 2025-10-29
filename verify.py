#!/usr/bin/env python

import subprocess
import codecs
import sys

StartMarker = "##Begin ONIDbot Output##"
EndMarker = "##End ONIDbot Output##"

SSHHost = "flip4.engr.oregonstate.edu"
SSHUser = "christj"
SSHKeyPath = "~/.ssh/osu_ssh_private"
APIBrokerPath = "~/onid_bot/api_broker.py"

def Main():
    print("Content-Type: text/plain")
    print("")
    try:
        if len(sys.argv) != 2:
            print("Error: Incorrect number of arguments given to CGI endpoint.")
            return
        code = sys.argv[1].strip()
        if not set(code).issubset(set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")):
            print("Error: Illegal chars given to CGI endpoint.")
            return
        cmd = [ "ssh", "-i", SSHKeyPath, SSHUser + "@" + SSHHost, APIBrokerPath, code ]
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=False)
        except subprocess.CalledProcessError as e:
            output = e.output
        if isinstance(output, bytes):
            output = codecs.decode(output, "utf-8")
        output = output.strip().replace("\r\n", "\n")

        startPos = output.find(StartMarker)
        if startPos == -1:
            print("Error: No start marker returned by API broker.")
            return
        startPos += len(StartMarker)
        endPos = output.find(EndMarker, startPos)
        if endPos == -1:
            print("Error: No end marker returned by API broker.")
            return
        print(output[startPos:endPos].strip())
    except:
        print("Error: Unknown error in CGI endpoint.")
Main()
