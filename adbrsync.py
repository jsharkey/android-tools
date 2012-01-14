#!/usr/bin/python

'''
    Copyright 2012, The Android Open Source Project

    Licensed under the Apache License, Version 2.0 (the "License"); 
    you may not use this file except in compliance with the License. 
    You may obtain a copy of the License at 

        http://www.apache.org/licenses/LICENSE-2.0 

    Unless required by applicable law or agreed to in writing, software 
    distributed under the License is distributed on an "AS IS" BASIS, 
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
    See the License for the specific language governing permissions and 
    limitations under the License.
'''

# simple rsync over adb; by jsharkey@
# usage:  adbrsync.py sourcedir destdir

import sys, os, re, pipes
import subprocess as subprocess

ADB = "/home/jsharkey/adb"
SOURCE = sys.argv[1]
DEST = sys.argv[2]



BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

def format(fg=None, bg=None, bright=False, bold=False, dim=False, reset=False):
	# manually derived from http://en.wikipedia.org/wiki/ANSI_escape_code#Codes
	codes = []
	if reset: codes.append("0")
	else:
		if not fg is None: codes.append("3%d" % (fg))
		if not bg is None:
			if not bright: codes.append("4%d" % (bg))
			else: codes.append("10%d" % (bg))
		if bold: codes.append("1")
		elif dim: codes.append("2")
		else: codes.append("22")
	return "\033[%sm" % (";".join(codes))



resafe = re.compile(r"[^A-Za-z0-9/\-_. ]")

def adb_escape(path):
	return resafe.sub('_', path)


def adb_getsize(path):
	output = subprocess.Popen([ADB, "shell", "ls", "-l", path], stdout=subprocess.PIPE, shell=False).communicate()[0]
	if output.find("No such file") != -1: return -1
	perms, uid, gid, size, date, time = output.split()[0:6]
	return int(size)

def adb_push(local, remote):
	output = subprocess.Popen([ADB, "push", local, remote], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False).communicate()

def adb_scan():
	subprocess.Popen([ADB, "shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_MOUNTED", "-d", "file:///data/media"], shell=False).communicate()
	subprocess.Popen([ADB, "shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_MOUNTED", "-d", "file:///mnt/sdcard"], shell=False).communicate()


RESET = format(reset=True)

for dirpath, dirnames, filenames in os.walk(SOURCE, followlinks=True):
	for filename in filenames:
		local = os.path.join(dirpath, filename)
		relpath = adb_escape(os.path.relpath(local, SOURCE))
		remote = os.path.join(DEST, relpath)
		
		localsize = os.path.getsize(local)
		remotesize = adb_getsize(remote)
		
		needpush = localsize != remotesize
		
		if needpush: color = format(fg=YELLOW)
		else: color = format(fg=GREEN)
		
		print " %s%skB%s %s" % (color, str(localsize/1024).rjust(8), RESET, relpath)
		
		if needpush:
			adb_push(local, remote)

print "rsync done, kicking off media scanner"
adb_scan()
