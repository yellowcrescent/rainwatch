#!/usr/bin/env python
# coding=utf-8
###############################################################################
#
# logthis - rwatch/logthis.py
# Rainwatch: Logging functions
#
# @author   J. Hipps <jacob@ycnrg.org>
# @repo     https://bitbucket.org/yellowcrescent/rainwatch
#
# Copyright (c) 2013-2016 J. Hipps / Neo-Retro Group
#
# https://ycnrg.org/
#
###############################################################################

import os
import sys
import __main__
import traceback
import inspect
import logging
import logging.handlers
import signal
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
    def __init__(self,etype):
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

def logthis(logline,loglevel=LL.DEBUG,prefix=None,suffix=None,ccode=None):
    global g_loglevel

    try:
        zline = u''
        if not ccode:
            if loglevel == LL.ERROR: ccode = C.RED
            elif loglevel == LL.WARNING: ccode = C.YEL
            elif loglevel == LL.PROMPT: ccode = C.WHT
            else: ccode = u""
        if prefix: zline += C.WHT + unify(prefix) + u": " + C.OFF
        zline += ccode + unify(logline) + C.OFF
        if suffix: zline += u" " + C.CYN + unify(suffix) + C.OFF

        # get traceback info
        lframe = inspect.stack()[1][0]
        lfunc = inspect.stack()[1][3]
        mod = inspect.getmodule(lframe)
        lline = inspect.getlineno(lframe)
        lfile = inspect.getsourcefile(lframe)
        try:
            lfile = os.path.splitext(os.path.basename(lfile))[0]
        except:
            lfile = u'(error)'

        if mod:
            lmodname = unicode(mod.__name__)
            xmessage = u" "
        else:
            lmodname = unicode(__name__)
            xmessage = unicode(data)
        if lmodname == u"__main__":
            lmodname = u"rainwatch"
            lfunc = u"(main)"

        if g_loglevel > LL.INFO:
            dbxmod = u'%s[%s:%s%s%s:%s] ' % (C.WHT,lmodname,C.YEL,lfunc,C.WHT,lline)
        else:
            dbxmod = ''

        finline = u'%s%s<%s>%s %s%s\n' % (dbxmod,C.RED,LL.lname[loglevel],C.WHT,zline,C.OFF)

    except Exception as e:
        finline = C.RED + u"Exception thrown in logthis(): " + C.WHT + u"[" + C.YEL + str(e.__class__.__name__) + C.WHT + u"] " + C.YEL + str(e) + C.OFF + u"\n"

    # write log message
    # TODO: add syslog (/dev/log) functionality

    if g_loglevel >= loglevel:
        sys.stdout.write(finline)

    # write to logfile
    writelog(finline)

def unify(indata):
    """coerce input data to unicode string"""
    if isinstance(indata, str):
        indata_str = str(indata).decode('utf-8')
    else:
        indata_str = unicode(indata)

    return indata_str

def logexc(e,msg,prefix=None):
    """log exception"""
    if msg: msg += ": "
    suffix = C.WHT + u"[" + C.YEL + str(e.__class__.__name__) + C.WHT + u"] " + C.YEL + str(e)
    logthis(msg,LL.ERROR,prefix,suffix)

def openlog(fname="rainwatch.log"):
    global loghand
    prxname = os.path.basename(sys.argv[0])
    try:
        loghand = codecs.open(fname,'a','utf-8')
        writelog("Logging started.\n")
        writelog("%s - Version %s (%s)\n" % (prxname,__main__.xsetup.version,__main__.xsetup.vdate))
        return True
    except Exception as e:
        logthis("Failed to open logfile '%s' for writing:" % (fname),suffix=e,loglevel=LL.ERROR)
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
        loghand.write(u"[ %s ] %s" % (datetime.now().strftime("%d/%b/%Y %H:%M:%S.%f"),decolor(logmsg)))
        loghand.flush()

def decolor(instr):
    return re.sub(u'\033\[(3[0-9]m|1?m|4D|2J|K|0;0f)',u'',instr)

def loglevel(newlvl=None):
    global g_loglevel
    if newlvl:
        g_loglevel = newlvl
    return g_loglevel

def failwith(etype,errmsg):
    logthis(errmsg,loglevel=LL.ERROR)

    raise xbError(etype)

def exceptionHandler(exception_type, exception, traceback):
    print u"%s: %s" % (exception_type.__name__, exception)

def print_r(ind):
    return json.dumps(ind,indent=4,separators=(',', ': '))
