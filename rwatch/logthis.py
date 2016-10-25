#!/usr/bin/env python3.5
# coding=utf-8
# vim: set ts=4 sw=4 expandtab syntax=python:
"""

rwatch.logthis
Rainwatch > Logging & output control facilities

Copyright (c) 2016 J. Hipps / Neo-Retro Group
https://ycnrg.org/

@author     Jacob Hipps <jacob@ycnrg.org>
@repo       https://git.ycnrg.org/projects/YRW/repos/rainwatch

"""

import os
import sys
import traceback
import inspect
import json
import re
import codecs
from datetime import datetime

class C:
    """ANSI Colors"""
    OFF = '\033[m'
    HI = '\033[1m'
    BLK = '\033[30m'
    RED = '\033[31m'
    GRN = '\033[32m'
    YEL = '\033[33m'
    BLU = '\033[34m'
    MAG = '\033[35m'
    CYN = '\033[36m'
    WHT = '\033[37m'
    B4 = '\033[4D'
    CLRSCR = '\033[2J'
    CLRLINE = '\033[K'
    HOME = '\033[0;0f'
    XCLEAR = '\033[2J\033[K\033[K'

    def nocolor(self):
        self.OFF = ''
        self.HI = ''
        self.BLK = ''
        self.RED = ''
        self.GRN = ''
        self.YEL = ''
        self.BLU = ''
        self.MAG = ''
        self.CYN = ''
        self.WHT = ''
        self.B4 = ''
        self.CLRSCR = ''
        self.CLRLINE = ''
        self.HOME = ''
        self.XCLEAR = ''

class ER:
    OPT_MISSING = 1
    OPT_BAD     = 2
    CONF_BAD    = 3
    PROCFAIL    = 4
    NOTFOUND    = 5
    UNSUPPORTED = 6
    DEPMISSING  = 7
    NOTIMPL      = 8
    lname = {
                0: 'none',
                1: 'opt_missing',
                2: 'opt_bad',
                3: 'conf_bad',
                4: 'procfail',
                5: 'notfound',
                6: 'unsupported',
                7: 'depmissing',
                8: 'notimpl',
            }

class xbError(Exception):
    def __init__(self, etype):
        self.etype = etype
    def __str__(self):
        return ER.lname[self.etype]

class LL:
    SILENT   = 0
    CRITICAL = 2
    ERROR    = 3
    WARNING  = 4
    PROMPT   = 5
    INFO     = 6
    VERBOSE  = 7
    DEBUG    = 8
    DEBUG2   = 9
    lname = {
                0: 'silent',
                2: 'critical',
                3: 'error',
                4: 'warning',
                5: 'prompt',
                6: 'info',
                7: 'verbose',
                8: 'debug',
                9: 'debug2'
            }

# set default loglevel
g_loglevel = LL.INFO

# logfile handle
loghand = None

def logthis(logline, loglevel=LL.DEBUG, prefix=None, suffix=None, ccode=None):
    global g_loglevel

    try:
        zline = ''
        if not ccode:
            if loglevel == LL.ERROR: ccode = C.RED
            elif loglevel == LL.WARNING: ccode = C.YEL
            elif loglevel == LL.PROMPT: ccode = C.WHT
            else: ccode = ""
        if prefix: zline += C.WHT + str(prefix) + ": " + C.OFF
        zline += ccode + str(logline) + C.OFF
        if suffix: zline += " " + C.CYN + str(suffix) + C.OFF

        # get traceback info
        lframe = inspect.stack()[1][0]
        lfunc = inspect.stack()[1][3]
        mod = inspect.getmodule(lframe)
        lline = inspect.getlineno(lframe)
        lfile = inspect.getsourcefile(lframe)
        try:
            lfile = os.path.splitext(os.path.basename(lfile))[0]
        except:
            lfile = '(error)'

        if mod:
            lmodname = str(mod.__name__)
            xmessage = " "
        else:
            lmodname = str(__name__)
            xmessage = str(data)
        if lmodname == "__main__":
            lmodname = "rainwatch"
            lfunc = "(main)"

        if g_loglevel > LL.INFO:
            dbxmod = '%s[%s:%s%s%s:%s] ' % (C.WHT, lmodname, C.YEL, lfunc, C.WHT, lline)
        else:
            dbxmod = ''

        finline = '%s%s<%s>%s %s%s\n' % (dbxmod, C.RED, LL.lname[loglevel], C.WHT, zline, C.OFF)

    except Exception as e:
        finline = C.RED + "Exception thrown in logthis(): " + \
                  C.WHT + "[" + C.YEL + str(e.__class__.__name__) + C.WHT + "] " + \
                  C.YEL + str(e) + C.OFF + "\n"

    # write log message
    if g_loglevel >= loglevel:
        sys.stdout.write(finline)

    # write to logfile
    writelog(finline)


def logexc(e, msg, prefix=None):
    """log exception"""
    if msg: msg += ": "
    suffix = C.WHT + "[" + C.YEL + str(e.__class__.__name__) + C.WHT + "] " + C.YEL + str(e)
    logthis(msg, LL.ERROR, prefix, suffix)
    log_traceback()

def openlog(fname="rainwatch.log"):
    """open log file"""
    from rwatch import __version__, __date__, gitinfo
    global loghand
    prxname = os.path.basename(sys.argv[0])
    try:
        loghand = codecs.open(fname, 'a', 'utf-8')
        writelog("Logging started.\n")
        writelog("%s - Version %s (%s)\n" % (prxname, __version__, __date__))
        return True
    except Exception as e:
        logthis("Failed to open logfile '%s' for writing:" % (fname), suffix=e, loglevel=LL.ERROR)
        return False

def closelog():
    global loghand
    if loghand:
        try:
            loghand.close()
            return True
        except:
            return False
    else:
        return True

def writelog(logmsg):
    global loghand
    if loghand:
        loghand.write("[ %s ] %s" % (datetime.now().strftime("%d/%b/%Y %H:%M:%S.%f"), decolor(logmsg)))
        loghand.flush()

def log_traceback():
    traceback.print_exc(file=loghand)

def decolor(instr):
    return re.sub(r'\033\[(3[0-9]m|1?m|4D|2J|K|0;0f)', '', instr)

def loglevel(newlvl=None):
    global g_loglevel
    if newlvl:
        g_loglevel = newlvl
    return g_loglevel

def failwith(etype, errmsg):
    logthis(errmsg, loglevel=LL.ERROR)

    raise xbError(etype)

def exceptionHandler(exception_type, exception, traceback):
    print("%s: %s" % (exception_type.__name__, exception))

def print_r(ind):
    return json.dumps(ind, indent=4, separators=(',', ': '))
