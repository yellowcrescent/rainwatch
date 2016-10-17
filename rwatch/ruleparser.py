#!/usr/bin/env python3.5
# coding=utf-8
# vim: set ts=4 sw=4 expandtab syntax=python:
"""

rwatch.ruleparser
Rainwatch > Rule Parser

Copyright (c) 2016 J. Hipps / Neo-Retro Group
https://ycnrg.org/

@author     Jacob Hipps <jacob@ycnrg.org>
@repo       https://git.ycnrg.org/projects/YRW/repos/rainwatch

"""

import os
import re
from copy import copy

from rwatch import *
from rwatch import rcfile
from rwatch.logthis import *


class RPX:
    """ruleset flags"""
    FILEONLY    = 1
    DIRONLY     = 2
    MKDIR       = 4

class RTP:
    """ruleset types"""
    RULESET     = 1
    GROUP       = 2
    DEFAULTS    = 3

# ruleset storage
rules = {}
groups = {}
rdefaults = {}

def parse(xconfig):
    """parse rules from rules file and build a working config"""
    rfile = xconfig.core['rules']
    rlist = rcfile.parseFile(rfile)

    for k, v in rlist.items():
        tset = {}
        for sk, sv in v.items():
            sk = sk.lower()
            if sk == 'match':
                # match directive
                tset['match'] = re.compile('.*'+sv+'.*', re.I)
            elif sk == 'matchs':
                # strict match directive
                tset['match'] = re.compile(sv)
            elif sk == 'exclude':
                # exclude directive
                tset['exclude'] = re.compile('.*'+sv+'.*', re.I)
            elif sk == 'excludes':
                # strict exclude directive
                tset['exclude'] = re.compile(sv)
            elif sk == 'moveto':
                # moveto directive
                tset['moveto'] = sv
                if not os.path.isdir(sv):
                    logthis("moveto path does not exist:", prefix=k, suffix=sv, loglevel=LL.WARNING)
            elif sk == 'type':
                # type attribute
                tset['type'] = sv.lower()
            elif sk == 'name':
                # name attribute
                tset['name'] = sv
            elif sk == 'fileonly' and istrue(sv):
                # fileonly flag
                tset['flags'] = tset.get('flags', 0) | RPX.FILEONLY
            elif sk == 'dironly' and istrue(sv):
                # dironly flag
                tset['flags'] = tset.get('flags', 0) | RPX.DIRONLY
            elif sk == 'mkdir' and istrue(sv):
                # mkdir flag
                tset['flags'] = tset.get('flags', 0) | RPX.MKDIR
            else:
                # unrecognized option
                logthis("Unrecognized attribute or directive:", prefix=k, suffix=sk, loglevel=LL.ERROR)

        if k[0] == '_':
            gset = k[1:]
            groups[gset] = tset
            logthis("Parsed group set:\n", prefix=gset, suffix=tset, loglevel=LL.DEBUG)
        else:
            rules[k] = tset
            logthis("Parsed ruleset:\n", prefix=k, suffix=tset, loglevel=LL.DEBUG)

def match(tordata):
    """find matching rules for a single torrent"""

    fmatch = False

    # check each ruleset for a match
    for k, v in rules.items():
        if check_ruleset(tordata, k) == True:
            fmatch = k
            break

    if fmatch:
        logthis("Found match:", suffix=fmatch, loglevel=LL.VERBOSE)
        rout = (fmatch, rresolve(fmatch))
    else:
        logthis("No match found", loglevel=LL.WARNING)
        rout = (False, {})

    return rout

def check_ruleset(tordata, rname, rtype=RTP.RULESET):
    """
    Check torrent (tordata) against specified ruleset (rname) of type (rtype)
    If all rules match, return True; else False
    """
    rset = getrule(rname, rtype)

    if not rset:
        logthis("ruleset is undefined:", suffix=rname, loglevel=LL.ERROR)
        return False

    tname = tordata.get('name', '')
    tmatch = False

    # check each rule in the ruleset
    for sk, sv in rset.items():
        sk = sk.lower()
        # get re.pattern string if this is a regex (for debugging purposes only)
        if isinstance(sv, re._pattern_type):
            svs = sv.pattern
        else:
            svs = sv
        logthis("checking rule:", prefix=rname, suffix="%s [%s]" % (sk, svs), loglevel=LL.DEBUG)
        if sk == 'match':
            if sv.match(tname): tmatch = True
            else: tmatch = False
        elif sk == 'exclude':
            if not sv.match(tname): tmatch = True
            else: tmatch = False
        elif sk == 'flags':
            if sv & RPX.FILEONLY:
                if tor_isfile(tordata): tmatch = True
                else: tmatch = False
            elif sv & RPX.DIRONLY:
                if not tor_isfile(tordata): tmatch = True
                else: tmatch = False
        elif sk == 'type':
            if sv.lower() in groups:
                logthis("checking against type/group definition:", prefix=rname, suffix=sv.lower(), loglevel=LL.DEBUG)
                tmatch = check_ruleset(tordata, sv.lower(), RTP.GROUP)
            else:
                logthis("undefined type/group specified:", prefix=rname, suffix=sv.lower(), loglevel=LL.ERROR)
                continue
        else:
            # skip over attributes and directives not relevent for matching
            logthis("directive skipped:", prefix=rname, suffix=sk, loglevel=LL.DEBUG2)
            continue
        logthis("%s [%s] =" % (sk, svs), prefix=rname, suffix=echobool(tmatch), loglevel=LL.DEBUG)
        if not tmatch: break

    return tmatch

def rresolve(rname, rtype=RTP.RULESET):
    """
    Resolves all ruleset dependencies (types and groups), and returns
    a dict of the final ruleset with all type defs applied, with proper
    ordering. Also applies var expansion in option strings.
    """
    rset = getrule(rname, rtype)

    if 'type' in rset:
        xrt = rresolve(rset['type'], RTP.GROUP)
    else:
        xrt = {}

    # merge rset into xrt
    # keys of rset will overwrite any dups in xrt
    rout = copy(xrt)
    rout.update(rset)

    # perform var expansion and change re objects into strings
    if rtype == RTP.RULESET:
        for sk, sv in rout.items():
            if sk == 'moveto':
                rout['moveto'] = vexpand(sv, rout)
            if isinstance(sv, re._pattern_type):
                rout[sk] = sv.pattern

    return rout

def getrule(rname, rtype=RTP.RULESET):
    """returns specified rule (rname) from specified type set (rtype)"""
    if rtype == RTP.RULESET:
        rset = rules.get(rname, None)
    elif rtype == RTP.GROUP:
        rset = groups.get(rname, None)
    elif rtype == RTP.DEFAULTS:
        rset = rdefaults
    return rset

def vexpand(instr, rdata):
    """perform var expansion in (instr) using data from (rdata)"""
    outstr = copy(instr)
    for tk, tv in rdata.items():
        rpterm = "{%s}" % (tk)
        if outstr.find(rpterm) >= 0:
            outstr = outstr.replace(rpterm, tv)
    return outstr

def tor_isfile(tdata):
    """check if a torrent is a single file (instead of a directory)"""
    tflist = tdata.get('files', None)
    if not tflist:
        logthis("incomplete torrent data provided", loglevel=LL.WARNING)
        return False

    if tflist[0]['path'] == tdata['name']:
        return True
    elif os.path.isfile(tdata['path']):
        return True
    else:
        return False

def list():
    """returns rule list"""
    return { 'rules': rules, 'groups': groups, 'defaults': rdefaults }

def istrue(inval):
    if inval == '1' or inval.lower() == 'yes' or inval.lower() == 'true' or inval.lower() == 'on':
        return True
    else:
        return False

def echobool(ibool):
    if ibool: return "True"
    else: return "False"
