#!/usr/bin/env python3.5
# coding=utf-8
# vim: set ts=4 sw=4 expandtab syntax=python:
"""

rwatch.util
Rainwatch > Common utility functions

Copyright (c) 2016 J. Hipps / Neo-Retro Group
https://ycnrg.org/

@author     Jacob Hipps <jacob@ycnrg.org>
@repo       https://git.ycnrg.org/projects/YRW/repos/rainwatch

"""

import os
import re
import subprocess
import socket

import arrow

from rwatch import *
from rwatch.logthis import *


class XConfig(object):
    """
    Config management object; allow access via attributes or items
    """
    __data = {}

    def __init__(self, idata):
        self.__data = idata

    def __getattr__(self, aname):
        if aname in self.__data:
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
        return "<XConfig: srv.url=%s, srv.port=%s, core.tclient=%s, xmpp.user=%s, ...>" % \
               (self.__data['srv']['url'], self.__data['srv']['port'],
                self.__data['core']['tclient'], self.__data['xmpp']['user'])


def rexec(optlist, supout=False):
    """
    execute command; input a list of options; if `supout` is True, then suppress stderr
    """
    logthis("Executing:", suffix=optlist, loglevel=LL.DEBUG)
    try:
        if supout:
            fout = subprocess.check_output(optlist, stderr=subprocess.STDOUT)
        else:
            fout = subprocess.check_output(optlist)
    except subprocess.CalledProcessError as e:
        logthis("exec failed:", suffix=e, loglevel=LL.ERROR)
        fout = None
    return fout


def fmtsize(insize, rate=False, bits=False):
    """
    format human-readable file size and xfer rates
    """
    onx = float(abs(insize))
    for u in ['B', 'K', 'M', 'G', 'T', 'P']:
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
        ostr = "%3d %s%s" % (onx, tunit, suffix)
    else:
        ostr = "%3.01f %s%s" % (onx, tunit, suffix)
    return ostr


def libnotify_send(xconfig, msgText, hname=False, huser=False, msgTimeout=10000, msgHead=False, msgIcon=False):
    """
    send libnotify notification to another host via ssh
    """
    # use defaults
    if not hname: hname = xconfig.notify['hostname']
    if not huser: huser = xconfig.notify['user']

    # set up notification icon
    if msgIcon: xicon = "-i '%s'" % (msgIcon)
    elif msgIcon == False and xconfig.notify['icon']: xicon = "-i '%s'" % (xconfig.notify['icon'])
    else: xicon = ''

    # if no message header, then use our hostname
    if msgHead == False: msgHead = socket.gethostname()
    else: msgHead = [msgHead]

    # escape newlines and such
    msgText = "'%s'" % (msgText.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t"))

    # get dbus session address
    dbsout = rexec(['/usr/bin/ssh', hname, '--', 'ps', 'aux', '|', 'grep', huser])
    dbus_addr = re.search('dbus-daemon --fork --session --address=(.+)', dbsout, re.I|re.M).group(1)
    logthis("Got dbus session:", suffix=dbus_addr, loglevel=LL.VERBOSE)

    # send notification
    rexec(['/usr/bin/ssh', hname, '--', "DBUS_SESSION_BUS_ADDRESS=\'%s\'" % (dbus_addr),
           'notify-send', '-t', str(msgTimeout), xicon, msgHead, msgText])
    logthis("Sent libnotify message to remote host", loglevel=LL.VERBOSE)


def git_info():
    """
    retrieve git info
    """
    # change to directory of rainwatch
    lastpwd = os.getcwd()
    os.chdir(os.path.dirname(os.path.realpath(__main__.__file__)))

    # run `git show`
    ro = rexec(['/usr/bin/git', 'show'])

    # change back
    os.chdir(lastpwd)

    # set defaults
    rvx = { 'ref': None, 'sref': None, 'date': None }
    if ro:
        try:
            cref = re.search(r'^commit\s*(.+)$', ro, re.I|re.M).group(1)
            cdate = re.search(r'^Date:\s*(.+)$', ro, re.I|re.M).group(1)
            rvx = { 'ref': cref, 'sref': cref[:8], 'date': cdate }
        except Exception as e:
            logexc(e, "Unable to parse output from git")

    return rvx


def git_info_raw():
    """
    retrieve git info from local log (does not invoke git binary)
    """
    rvx = { 'ref': None, 'sref': None, 'date': None }

    rpath = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

    if os.path.exists(rpath + '/.git'):
        try:
            with open(rpath + '/.git/logs/HEAD', 'r') as f:
                last = f.readlines()[-1]
            last_info, last_msg = last.strip().split('\t', 1)
            infos = last_info.split()
            chgtype, msg = last_msg.split(':', 1)
            cdate = arrow.get(int(infos[4]))
            cdate.tzinfo = arrow.get(infos[5], 'Z').tzinfo
            rvx = {
                    'ref': infos[1],
                    'sref': infos[1][:8],
                    'date': cdate.format('ddd MMM DD YYYY HH:mm:SS Z')
                  }
        except:
            pass
    return rvx


def path_exists(fpath):
    """
    determine whether a file or directory exists
    workaround for os.stat, which doesn't properly allow Unicode filenames
    """
    try:
        with open(fpath, "rb") as f:
            f.close()
        return True
    except IOError as e:
        if e.errno == 21:
            # Is a directory
            return True
        else:
            return False

