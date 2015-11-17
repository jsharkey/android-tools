#!/usr/bin/python

'''
    Copyright 2009, The Android Open Source Project

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

# script to highlight adb logcat output for console
# written by jeff sharkey, http://jsharkey.org/
# piping detection and popen() added by other android team members

import os, sys, re, StringIO
import fcntl, termios, struct

# List of tags to highlight (inverted)
HIGHLIGHT = [
    "ActivityManager",
    "MyApp",
]

# List of tags to ignore completely
IGNORED = [
    "SpammyApp"
]

# Width of various columns; set to -1 to hide
USER_WIDTH = 3
PROCESS_WIDTH = 8
TAG_WIDTH = 20
PRIORITY_WIDTH = 3

HEADER_SIZE = USER_WIDTH + PROCESS_WIDTH + TAG_WIDTH + PRIORITY_WIDTH + 4

# unpack the current terminal width/height
data = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, '1234')
HEIGHT, WIDTH = struct.unpack('hh',data)

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


def indent_wrap(message, indent=0, width=80):
    wrap_area = width - indent
    messagebuf = StringIO.StringIO()
    current = 0
    while current < len(message):
        next = min(current + wrap_area, len(message))
        messagebuf.write(message[current:next])
        if next < len(message):
            messagebuf.write("\n%s" % (" " * indent))
        current = next
    return messagebuf.getvalue()

USER_COLORS = [BLUE,YELLOW,RED,GREEN,MAGENTA,CYAN]
LAST_USED = [RED,GREEN,YELLOW,BLUE,MAGENTA,CYAN,WHITE]
KNOWN_TAGS = {
    "dalvikvm": BLUE,
    "art": BLUE,
    "Process": BLUE,
    "ActivityManager": CYAN,
    "ActivityThread": CYAN,
}

# map from known pid to uid
KNOWN_PIDS = {}

def get_user_id(uid):
    return uid / 100000

def allocate_color(tag):
    # this will allocate a unique format for the given tag
    # since we dont have very many colors, we always keep track of the LRU
    if not tag in KNOWN_TAGS:
        KNOWN_TAGS[tag] = LAST_USED[0]
    color = KNOWN_TAGS[tag]
    if color in LAST_USED:
        LAST_USED.remove(color)
        LAST_USED.append(color)
    return color

PRIORITIES = {
    "V": "%s%s%s " % (format(fg=WHITE, bg=BLACK), "V".center(PRIORITY_WIDTH), format(reset=True)),
    "D": "%s%s%s " % (format(fg=BLACK, bg=BLUE), "D".center(PRIORITY_WIDTH), format(reset=True)),
    "I": "%s%s%s " % (format(fg=BLACK, bg=GREEN), "I".center(PRIORITY_WIDTH), format(reset=True)),
    "W": "%s%s%s " % (format(fg=BLACK, bg=YELLOW), "W".center(PRIORITY_WIDTH), format(reset=True)),
    "E": "%s%s%s " % (format(fg=BLACK, bg=RED), "E".center(PRIORITY_WIDTH), format(reset=True)),
    "F": "%s%s%s " % (format(fg=BLACK, bg=RED), "F".center(PRIORITY_WIDTH), format(reset=True)),
}

retag = re.compile("^([A-Z])/([^\(]+)\(([^\)]+)\): (.*)$")
retime = re.compile("(?:(\d+)s)?([\d.]+)\dms")
reproc = re.compile(r"^I/ActivityManager.*?: Start proc .*?: pid=(\d+) uid=(\d+)")

def millis_color(match):
    # TODO: handle "19s214ms" formatting
    sec, millis = match.groups()
    millis = float(millis)
    if sec is not None:
        sec = int(sec)
        millis += sec * 1000
    style = format(reset=True)
    if millis > 640: style = format(fg=RED, bold=True)
    elif millis > 320: style = format(fg=RED)
    elif millis > 160: style = format(fg=YELLOW, bold=True)
    elif millis > 32: style = format(fg=YELLOW)
    elif millis > 16: style = format(fg=CYAN)
    return "%s%s%s" % (style, match.group(0), format(reset=True))

# to pick up -d or -e
adb_args = ' '.join(sys.argv[1:])

# if someone is piping in to us, use stdin as input.  if not, invoke adb logcat
if os.isatty(sys.stdin.fileno()):
    input = os.popen("adb %s logcat -v brief" % adb_args)
else:
    input = sys.stdin

while True:
    try:
        line = input.readline()
    except KeyboardInterrupt:
        break

    line = line.expandtabs(4)
    if len(line) == 0: break

    # watch for process-to-user mappings
    match = reproc.search(line)
    if match:
        KNOWN_PIDS[int(match.group(1))] = int(match.group(2))

    match = retag.match(line)
    if not match:
        print line
        continue

    priority, tag, process, message = match.groups()
    linebuf = StringIO.StringIO()

    tag = tag.strip()
    if tag in IGNORED: continue

    # center user info
    if USER_WIDTH > 0:
        pid = int(process)
        if pid in KNOWN_PIDS and KNOWN_PIDS[pid] >= 10000:
            user = get_user_id(KNOWN_PIDS[pid])
            color = USER_COLORS[user % len(USER_COLORS)]
            user = str(user).center(USER_WIDTH)
            linebuf.write("%s%s%s " % (format(fg=BLACK, bg=color, bright=False), user, format(reset=True)))
        else:
            linebuf.write(" " * (USER_WIDTH + 1))

    # center process info
    if PROCESS_WIDTH > 0:
        process = process.strip().center(PROCESS_WIDTH)
        linebuf.write("%s%s%s " % (format(fg=BLACK, bg=BLACK, bright=True), process, format(reset=True)))

    # right-align tag title and allocate color if needed
    tag = tag.strip()
    if "avc: denied" in message:
        tag = tag[-TAG_WIDTH:].rjust(TAG_WIDTH)
        linebuf.write("%s%s%s " % (format(fg=WHITE, bg=RED, dim=False), tag, format(reset=True)))
    elif tag in HIGHLIGHT:
        tag = tag[-TAG_WIDTH:].rjust(TAG_WIDTH)
        linebuf.write("%s%s%s " % (format(fg=BLACK, bg=WHITE, dim=False), tag, format(reset=True)))
    else:
        color = allocate_color(tag)
        tag = tag[-TAG_WIDTH:].rjust(TAG_WIDTH)
        linebuf.write("%s%s%s " % (format(fg=color, dim=False), tag, format(reset=True)))

    # write out tagtype colored edge
    if not priority in PRIORITIES:
        print line
        continue

    linebuf.write(PRIORITIES[priority])

    # color any high-millis operations
    message = retime.sub(millis_color, message)

    # insert line wrapping as needed
    message = indent_wrap(message, HEADER_SIZE, WIDTH)

    linebuf.write(message)
    print linebuf.getvalue()
