#!/usr/bin/env python
# coding=utf-8
###############################################################################
#
# util - rwatch/util.py
# Rainwatch: Common utility functions
#
# @author   J. Hipps <jacob@ycnrg.org>
# @repo     https://bitbucket.org/yellowcrescent/rainwatch
#
# Copyright (c) 2016 J. Hipps / Neo-Retro Group
#
# https://ycnrg.org/
#
###############################################################################

import __main__
import sys
import os
import re
import json
import time
import subprocess
import socket
from datetime import datetime

from rwatch.logthis import *


class XConfig(object):
    """
    Config management object; allow access via attributes or items
    """
    __data = {}

    def __init__(self, idata):
        self.__data = idata

    def __getattr__(self, aname):
        if self.__data.has_key(aname):
            if isinstance(self.__data[aname], dict):
                return XConfig(self.__data[aname])
            else:
                return self.__data[aname]
        else:
            raise KeyError(aname)

    def __getitem__(self, aname):
        return self.__getattr__(aname)

    def __str__(self):
        return print_r(self.__data)

    def __repr__(self):
        return print_r(self.__data)


def rexec(optlist,supout=False):
    """
    execute command; input a list of options; if `supout` is True, then suppress stderr
    """
    logthis("Executing:",suffix=optlist,loglevel=LL.DEBUG)
    try:
        if supout:
            fout = subprocess.check_output(optlist,stderr=subprocess.STDOUT)
        else:
            fout = subprocess.check_output(optlist)
    except subprocess.CalledProcessError as e:
        logthis("exec failed:",suffix=e,loglevel=LL.ERROR)
        fout = None
    return fout


def fmtsize(insize,rate=False,bits=False):
    """
    format human-readable file size and xfer rates
    """
    onx = float(abs(insize))
    for u in ['B','K','M','G','T','P']:
        if onx < 1024.0:
            tunit = u
            break
        onx /= 1024.0
    suffix = ""
    if u != 'B': suffix = "iB"
    if rate:
        if bits:
            suffix = "bps"
            onx *= 8.0
        else:
            suffix += "/sec"
    if tunit == 'B':
        ostr = "%3d %s%s" % (onx,tunit,suffix)
    else:
        ostr = "%3.01f %s%s" % (onx,tunit,suffix)
    return ostr


def libnotify_send(msgText,hname=False,huser=False,msgTimeout=10000,msgHead=False,msgIcon=False):
    """
    send libnotify notification to another host via ssh
    """
    # use defaults
    if not hname: hname = xsetup.config['notify']['hostname']
    if not huser: huser = xsetup.config['notify']['user']

    # set up notification icon
    if msgIcon: xicon = "-i '%s'" % (msgIcon)
    elif msgIcon == False and xsetup.config['notify']['icon']: xicon = "-i '%s'" % (xsetup.config['notify']['icon'])
    else: xicon = ''

    # if no message header, then use our hostname
    if msgHead == False: msgHead = socket.gethostname()
    else: msgHead = [msgHead]

    # escape newlines and such
    msgText = "'%s'" % (msgText.replace("\n","\\n").replace("\r","\\r").replace("\t","\\t"))

    # get dbus session address
    dbsout = rexec(['/usr/bin/ssh',hname,'--','ps','aux','|','grep',huser])
    dbus_addr = re.search('dbus-daemon --fork --session --address=(.+)', dbsout, re.I|re.M).group(1)
    logthis("Got dbus session:",suffix=dbus_addr,loglevel=LL.VERBOSE)

    # send notification
    # TODO: we can probably make this use rwatch.ssh2.rainshell eventually...
    rexec(['/usr/bin/ssh',hname,'--',"DBUS_SESSION_BUS_ADDRESS=\'%s\'" % (dbus_addr),'notify-send','-t',str(msgTimeout),xicon,msgHead,msgText])
    logthis("Sent libnotify message to remote host",loglevel=LL.VERBOSE)


def git_info():
    """
    retrieve git info
    """
    # change to directory of rainwatch
    lastpwd = os.getcwd()
    os.chdir(os.path.dirname(os.path.realpath(__main__.__file__)))

    # run `git show`
    ro = rexec(['/usr/bin/git','show'])

    # change back
    os.chdir(lastpwd)

    # set defaults
    rvx = { 'ref': None, 'sref': None, 'date': None }
    if ro:
        try:
            cref = re.search('^commit\s*(.+)$',ro,re.I|re.M).group(1)
            cdate = re.search('^Date:\s*(.+)$',ro,re.I|re.M).group(1)
            rvx = { 'ref': cref, 'sref': cref[:8], 'date': cdate }
        except Exception as e:
            logexc(e, "Unable to parse output from git")

    return rvx


def path_exists(fpath):
    """
    determine whether a file or directory exists
    workaround for os.stat, which doesn't properly allow Unicode filenames
    """
    try:
        with open(fpath,"rb") as f:
            f.close()
        return True
    except IOError as e:
        if e.errno == 21:
            # Is a directory
            return True
        else:
            return False

def test_stat(tname, tfile):

    tpid = os.getpid()
    try:
        logthis(u"TEST: %s - os.stat(%s)" % (tname, tfile), prefix=tpid, loglevel=LL.WARNING)
    except Exception as e:
        logexc(e, "Failed to display log text")

    try:
        os.stat(tfile)
        #logthis(u"TEST: ✔ PASSED OK", prefix=tpid, loglevel=LL.WARNING)
        logthis(u"TEST: PASSED OK", prefix=tpid, loglevel=LL.WARNING)
        return True
    except Exception as e:
        logexc(e, "Failed to run test_stat()")
        return False
