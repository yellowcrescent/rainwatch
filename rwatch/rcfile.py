#!/usr/bin/env python3.5
# coding=utf-8
# vim: set ts=4 sw=4 expandtab syntax=python:
"""

rwatch.rcfile
Rainwatch > RC file & config builder functions

Copyright (c) 2016 J. Hipps / Neo-Retro Group
https://ycnrg.org/

@author     Jacob Hipps <jacob@ycnrg.org>
@repo       https://git.ycnrg.org/projects/YRW/repos/rainwatch

"""

import os
import re
import codecs
import configparser

from rwatch import *
from rwatch.logthis import *
from rwatch.util import *

# RCfile list
rcfiles = [ './rainwatch.conf', '~/.rainwatch/rainwatch.conf', '~/.rainwatch', '/etc/rainwatch.conf' ]

# Parser object
rcpar = None

def rcList(xtraConf=None):
    global rcfiles
    rcc = []

    if xtraConf:
        xcf = os.path.expanduser(xtraConf)
        if os.path.exists(xcf):
            rcc.append(xcf)
            logthis("Added rcfile candidate (from command line):", suffix=xcf, loglevel=LL.DEBUG)
        else:
            logthis("Specified rcfile does not exist:", suffix=xcf, loglevel=LL.ERROR)

    for tf in rcfiles:
        ttf = os.path.expanduser(tf)
        logthis("Checking for rcfile candidate", suffix=ttf, loglevel=LL.DEBUG2)
        if os.path.exists(ttf):
            rcc.append(ttf)
            logthis("Got rcfile candidate", suffix=ttf, loglevel=LL.DEBUG2)

    return rcc


def parse(xtraConf=None):
    """
    Parse rcfile (rainwatch.conf)
    Output: (rcfile, rcdata)
    """
    global rcpar
    # get rcfile list
    rcl = rcList(xtraConf)
    logthis("Parsing any local, user, or system RC files...", loglevel=LL.DEBUG)

    # use ConfigParser to parse the rcfiles
    rcpar = configparser.RawConfigParser()
    rcfile = None
    if len(rcl):
        rcfile = os.path.realpath(rcl[0])
        logthis("Parsing config file:", suffix=rcfile, loglevel=LL.VERBOSE)
        try:
            # use ConfigParser.readfp() so that we can correctly parse UTF-8 stuffs
            # ...damn you python 2 and your shitty unicode bodgery
            with codecs.open(rcfile, 'r', encoding='utf-8') as f:
                rcpar.readfp(f)
        except configparser.ParsingError as e:
            logthis("Error parsing config file: %s" % e, loglevel=LL.ERROR)
            return False

    # build a dict
    rcdict = {}
    rsecs = rcpar.sections()
    logthis("Config sections:", suffix=rsecs, loglevel=LL.DEBUG2)
    for ss in rsecs:
        isecs = rcpar.items(ss)
        rcdict[ss] = {}
        for ii in isecs:
            logthis(">> %s" % ii[0], suffix=ii[1], loglevel=LL.DEBUG2)
            rcdict[ss][ii[0]] = ii[1]

    # return loaded filename and rcdata
    return (rcfile, rcdict)

def parseFile(fpath):
    """
    Parse rcfile fpath
    Output: rcdata
    """
    logthis("Parsing RC file:", suffix=fpath, loglevel=LL.DEBUG)

    # use ConfigParser to parse the rcfiles
    rcpar = configparser.SafeConfigParser()
    rcfile = None
    if os.path.exists(os.path.expanduser(fpath)):
        rcfile = os.path.realpath(os.path.expanduser(fpath))
        logthis("Parsing config file:", suffix=rcfile, loglevel=LL.VERBOSE)
        try:
            # use ConfigParser.readfp() so that we can correctly parse UTF-8 stuffs
            # ...damn you python 2 and your shitty unicode bodgery
            with codecs.open(rcfile, 'r', encoding='utf-8') as f:
                rcpar.readfp(f)
        except configparser.ParsingError as e:
            logthis("Error parsing config file: %s" % e, loglevel=LL.ERROR)
            return False
    else:
        logthis("File does not exist, skipping", loglevel=LL.WARNING)

    # build a dict
    rcdict = {}
    rsecs = rcpar.sections()
    logthis("Config sections:", suffix=rsecs, loglevel=LL.DEBUG2)
    for ss in rsecs:
        isecs = rcpar.items(ss)
        rcdict[ss] = {}
        for ii in isecs:
            logthis(">> %s" % ii[0], suffix=ii[1], loglevel=LL.DEBUG2)
            rcdict[ss][ii[0]] = qstrip(ii[1])

    # return loaded filename and rcdata
    return rcdict

def merge(inrc, cops):
    """
    Merge options from loaded rcfile with defaults; strip quotes and perform type-conversion.
    Any defined value set in the config will override the default value.
    """
    outrc = {}
    # set defaults first
    for dsec in defaults:
        # create sub dict for this section, if not exist
        if dsec not in outrc:
            outrc[dsec] = {}
        # loop through the keys
        for dkey in defaults[dsec]:
            logthis("** Option:", prefix="defaults", suffix="%s => %s => '%s'" % (dsec, dkey, defaults[dsec][dkey]),
                    loglevel=LL.DEBUG2)
            outrc[dsec][dkey] = defaults[dsec][dkey]

    # set options defined in rcfile, overriding defaults
    for dsec in inrc:
        # create sub dict for this section, if not exist
        if dsec not in outrc:
            outrc[dsec] = {}
        # loop through the keys
        for dkey in inrc[dsec]:
            # check if key exists in defaults
            try:
                type(outrc[dsec][dkey])
                keyok = True
            except KeyError:
                keyok = False

            # Strip quotes and perform type-conversion for ints and floats
            # only perform conversion if key exists in defaults
            if keyok:
                if isinstance(outrc[dsec][dkey], int):
                    try:
                        tkval = int(qstrip(inrc[dsec][dkey]))
                    except ValueError as e:
                        logthis("Unable to convert value to integer. Check config option value. Value:",
                                prefix="%s:%s" % (dsec, dkey), suffix=qstrip(inrc[dsec][dkey]), loglevel=LL.ERROR)
                        continue
                elif isinstance(outrc[dsec][dkey], float):
                    try:
                        tkval = float(qstrip(inrc[dsec][dkey]))
                    except ValueError as e:
                        logthis("Unable to convert value to float. Check config option value. Value:",
                                prefix="%s:%s" % (dsec, dkey), suffix=qstrip(inrc[dsec][dkey]), loglevel=LL.ERROR)
                        continue
                else:
                    tkval = qstrip(inrc[dsec][dkey])
            else:
                tkval = qstrip(inrc[dsec][dkey])

            logthis("** Option set:", prefix="rcfile", suffix="%s => %s => '%s'" % (dsec, dkey, tkval),
                    loglevel=LL.DEBUG2)
            outrc[dsec][dkey] = tkval

    # add in cli options
    for dsec in cops:
        # create sub dict for this section, if not exist
        if dsec not in outrc:
            outrc[dsec] = {}
        # loop through the keys
        for dkey in cops[dsec]:
            # only if the value has actually been set (eg. non-false)
            if cops[dsec][dkey]:
                logthis("** Option:", prefix="cliopts", suffix="%s => %s => '%s'" % (dsec, dkey, cops[dsec][dkey]),
                        loglevel=LL.DEBUG2)
                outrc[dsec][dkey] = cops[dsec][dkey]

    return outrc


def qstrip(inval):
    # Strip quotes from quote-delimited strings
    rxm = re.match('^([\"\'])(.+)(\\1)$', inval)
    if rxm:
        return rxm.groups()[1]
    else:
        return inval

def optexpand(iop):
    # expand CLI options like "xcode.scale" from 1D to 2D array/dict (like [xcode][scale])
    outrc = {}
    for i in iop:
        dsec, dkey = i.split(".")
        if dsec not in outrc:
            outrc[dsec] = {}
        outrc[dsec][dkey] = iop[i]
    logthis("Expanded cli optdex:", suffix=outrc, loglevel=LL.DEBUG2)
    return outrc

def loadConfig(xtraConf=None, cliopts=None):
    """
    Top-level class for loading configuration from rainwatch.conf
    """
    rcfile, rci = parse(xtraConf)
    cxopt = optexpand(cliopts)
    optrc = merge(rci, cxopt)
    return XConfig(optrc)
