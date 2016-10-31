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
import inspect
import json
import re
import time
import socket
import syslog
from urllib.parse import urlparse

import arrow
import zmq

from rwatch.db import mongo, redis

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
    ALERT    = 1
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
                1: 'alert',
                2: 'critical',
                3: 'error',
                4: 'warning',
                5: 'prompt',
                6: 'info',
                7: 'verbose',
                8: 'debug',
                9: 'debug2'
            }
    syslog = {
                0: syslog.LOG_EMERG,
                1: syslog.LOG_ALERT,
                2: syslog.LOG_CRIT,
                3: syslog.LOG_ERR,
                4: syslog.LOG_WARNING,
                5: syslog.LOG_NOTICE,
                6: syslog.LOG_NOTICE,
                7: syslog.LOG_INFO,
                8: syslog.LOG_DEBUG,
                9: syslog.LOG_DEBUG
            }


class loggerMaster():
    ready = False
    loglevel = LL.VERBOSE
    log_pid = True
    log_level = True
    log_time = True

    def log(self, msg, loglevel, mname=None, fname=None, linenum=None, **kwargs):
        if self.loglevel >= loglevel:
            nmsg = decolor(msg)
            tepoch = time.time()
            lpid = os.getpid()
            spid = ""
            slevel = ""
            tformat = ""
            if self.log_pid:
                spid = "(%d) " % (lpid)
            if self.log_time:
                tformat = arrow.get(tepoch).format("YYYY-MM-DD HH:mm:ss.SSS") + " "
            if self.log_level:
                slevel = "%s: " % (LL.lname[loglevel].upper())
            logline = "%s%s[%s:%s:%s] %s%s" % \
                      (tformat, spid, mname, fname, linenum, slevel, nmsg)
            self.write(logline, timestamp=tepoch, level=LL.lname[loglevel], rmsg=nmsg, rmodule=mname,
                       rfunction=fname, rline=linenum, rpid=lpid, rlevel=loglevel, **kwargs)

    def startup(self):
        from rwatch import __version__, __date__, gitinfo
        prxname = os.path.basename(sys.argv[0])
        self.log("Logging started: %s - Version %s (%s)\n" % (prxname, __version__, __date__), LL.INFO)
        self.ready = True

    def shutdown(self):
        self.ready = False
        self.log("Closing log target", LL.INFO)

class loggerFile(loggerMaster):
    logtype = 'file'
    __handle = None
    fastflush = True

    def __init__(self, path, loglevel=None, fastflush=True):
        self.fastflush = fastflush
        if loglevel is not None:
            self.loglevel = loglevel
        prxname = os.path.basename(sys.argv[0])
        try:
            self.__handle = open(path, 'a')
        except FileNotFoundError:
            logexc(e, "Unable to open file: %s" % (path))
            failwith(ER.CONF_BAD, "Invalid logfile path. Update core.logfile in config and try again.")
        except PermissionError:
            logexc(e, "Insufficient permission to open file: %s" % (path))
            failwith(ER.CONF_BAD, "Invalid logfile path or perms. Update core.logfile in config and try again.")
        self.startup()

    def write(self, msg, **kwargs):
        self.__handle.write(msg + '\n')
        if self.fastflush:
            self.__handle.flush()

    def __del__(self):
        if self.__handle is not None:
            try:
                self.shutdown()
                __handle.close()
            except:
                pass

class loggerMongo(loggerMaster):
    logtype = 'mongo'
    __mon = None
    collection = 'log'

    def __init__(self, uri, loglevel=None, collection='log', use_capped=True, capsize=1000000):
        self.__mon = mongo(uri)
        self.collection = collection
        if loglevel is not None:
            self.loglevel = loglevel
        if self.collection not in self.__mon.get_collections():
            logthis("Creating new collection (use_capped=%s, capsize=%d):" % (use_capped, capsize),
                    suffix=self.collection, loglevel=LL.VERBOSE)
            # create new collection
            if use_capped:
                self.__mon.create_collection(self.collection, capped=True, size=capsize)
            else:
                self.__mon.create_collection(self.collection)
        self.startup()

    def write(self, msg, **kwargs):
        xout = {}
        xout.update(kwargs)
        xout.update({'message': msg})
        self.__mon.insert(self.collection, xout)

    def __del__(self):
        self.shutdown()
        self.__mon.close()

class loggerZMQ(loggerMaster):
    logtype = 'zeromq'
    __context = None
    __socket = None

    def __init__(self, uri, loglevel=None):
        uri = uri.replace('zmq+', '')
        if loglevel is not None:
            self.loglevel = loglevel
        try:
            self.__context = zmq.Context()
            self.__socket = self.__context.socket(zmq.REQ)
            self.__socket.connect(uri)
        except zmq.ZMQError as e:
            logexc(e, "Failed to establish ZeroMQ connection to host")
            failwith(ER.CONF_BAD, "Check local logfile configuration and ensure remote host is ready")
        self.startup()

    def write(self, msg, **kwargs):
        xout = {}
        xout.update(kwargs)
        xout.update({'message': msg, 'type': "yclogthis", 'app': os.path.basename(sys.argv[0]), 'host': socket.gethostname()})
        if 'timestamp' in xout:
            xout['@timestamp'] = xout['timestamp']
            del(xout['timestamp'])
        self.__socket.send_string(json.dumps(xout))
        self.__socket.recv()

    def __del__(self):
        try:
            self.__socket.close()
        except:
            pass

class loggerJStream(loggerMaster):
    logtype = 'json_stream'
    __socket = None
    host = None
    port = None
    socktype = None

    def __init__(self, uri, loglevel=None):
        uparse = urlparse(uri)
        self.host = uparse.hostname
        self.port = uparse.port
        if uparse.scheme == 'udp':
            self.socktype = socket.SOCK_DGRAM
        elif uparse.scheme == 'tcp':
            self.socktype = socket.SOCK_STREAM
        else:
            logthis("URI containing an invalid scheme was specified. Only udp:// and tcp:// are allowed.", loglevel=LL.ERROR)
            failwith(ER.CONF_BAD, "Invalid URI. Check logfile configuration and try again.")
        if self.port is None:
            logthis("URI containing both a hostname and port is required (eg. 'udp://server.example.com:8901')", loglevel=LL.ERROR)
            failwith(ER.CONF_BAD, "Invalid URI. Check logfile configuration and try again.")
        if loglevel is not None:
            self.loglevel = loglevel

        for res in socket.getaddrinfo(self.host, self.port, socket.AF_UNSPEC, self.socktype):
            af, socktype, proto, canonname, sa = res
            try:
                self.__socket = socket.socket(af, socktype, proto)
            except OSError:
                logthis("Socket creation failed:", suffix=str(e), loglevel=LL.VERBOSE)
                self.__socket = None
                continue
            try:
                self.__socket.connect(sa)
                self.__socket.setblocking(False)
            except OSError:
                logthis("Connection attempt failed:", suffix=str(e), loglevel=LL.VERBOSE)
                self.__socket.close()
                continue
            break
        if self.__socket is None:
            logthis("Unable to connect to establish connection to", suffix=uri, loglevel=LL.ERROR)
            failwith(ER.CONF_BAD, "Check logfile configuration and ensure remote host is ready")
        self.startup()

    def write(self, msg, **kwargs):
        xout = {}
        xout.update(kwargs)
        xout.update({'message': msg, 'type': "yclogthis", 'app': os.path.basename(sys.argv[0]), 'host': socket.gethostname()})
        if 'timestamp' in xout:
            xout['timestamp_f'] = xout['timestamp']
            xout['timestamp'] = isotime(xout['timestamp'])
        self.__socket.sendall(bytes(json.dumps(xout)+"\n", 'utf-8'))
        try:
            resp = self.__socket.recv(4096)
        except BlockingIOError:
            pass

    def __del__(self):
        if self.__socket is not None:
            try:
                self.__socket.close()
            except:
                pass

class loggerSyslog(loggerMaster):
    logtype = 'syslog'

    def __init__(self, loglevel=None):
        if loglevel is not None:
            self.loglevel = loglevel
        self.log_pid = False
        #self.log_level = False
        self.log_time = False
        syslog.openlog(ident=os.path.basename(sys.argv[0]), logoption=syslog.LOG_PID, facility=syslog.LOG_DAEMON)
        self.startup()

    def write(self, msg, **kwargs):
        if 'rlevel' in kwargs:
            syslog.syslog(LL.syslog[kwargs['rlevel']], msg)
        else:
            syslog.syslog(msg)

    def __del__(self):
        try:
            syslog.closelog()
        except:
            pass


# set default loglevel
g_loglevel = LL.INFO

# logfile handle
loghand = None
handler = None

def logthis(logline, loglevel=LL.DEBUG, prefix=None, suffix=None, ccode=None):
    global g_loglevel, handler

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

    # write to log target
    if handler is not None:
        if handler.ready is True:
            handler.log(zline, loglevel, mname=lmodname, fname=lfunc, linenum=lline)


def logexc(e, msg, prefix=None):
    """log exception"""
    if msg: msg += ": "
    suffix = C.WHT + "[" + C.YEL + str(e.__class__.__name__) + C.WHT + "] " + C.YEL + str(e)
    logthis(msg, LL.ERROR, prefix, suffix)

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

def isotimenow():
    return arrow.utcnow().format(r"YYYY-MM-DDTHH:mm:ss.SSS")+"Z"

def isotime(tstamp):
    return arrow.get(tstamp).format(r"YYYY-MM-DDTHH:mm:ss.SSS")+"Z"

def configure_logger(xconfig):
    """
    Configure logging to filesystem, MongoDB, or Redis
    """
    global handler
    handler = None
    hset = False
    if isinstance(xconfig.core['logfile'], str):
        if len(xconfig.core['logfile'].strip()) > 0:
            larg = urlparse(xconfig.core['logfile'])
            if larg.scheme.lower() == 'mongodb':
                handler = loggerMongo(xconfig.core['logfile'], loglevel=xconfig.core['logfile_level'])
                hset = True
            elif larg.scheme.lower().startswith('zmq+'):
                handler = loggerZMQ(xconfig.core['logfile'], loglevel=xconfig.core['logfile_level'])
                hset = True
            elif larg.scheme.lower() == 'udp' or larg.scheme.lower() == 'tcp':
                handler = loggerJStream(xconfig.core['logfile'], loglevel=xconfig.core['logfile_level'])
                hset = True
            elif larg.scheme.lower() == 'syslog':
                handler = loggerSyslog(loglevel=xconfig.core['logfile_level'])
                hset = True
            elif larg.scheme.lower() == '':
                handler = loggerFile(xconfig.core['logfile'], loglevel=xconfig.core['logfile_level'])
                hset = True
            elif re.match(r'^(null|none)(://)?$', xconfig.core['logfile'].strip(), re.I):
                pass
            else:
                failwith(ER.CONF_BAD, "Invalid log target: %s" % (xconfig.core['logfile']))

    if hset is False:
        logthis("External logging disabled", loglevel=LL.VERBOSE)
        return None
    else:
        return handler.logtype
