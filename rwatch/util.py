#!/usr/bin/env python
# coding=utf-8
###############################################################################
#
# jabber - rwatch/util.py
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

import sys
import os
import re
import json
import time
import subprocess
import socket
from datetime import datetime

from rwatch.logthis import C,LL,logthis,ER,failwith,loglevel,print_r,exceptionHandler

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
