#!/usr/bin/env python
# coding=utf-8
###############################################################################
#
# ssh2 - rwatch/ssh2.py
# Rainwatch: SSH2 Functions
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
import paramiko

from rwatch.logthis import C,LL,logthis,ER,failwith,loglevel,print_r,exceptionHandler
from rwatch.util import *
from rwatch import jabber

class rainshell(paramiko.client.SSHClient):
    """
    rainwatch ssh2 wrapper class around paramiko's SSHClient
    """
    rsc = None
    connected = False
    jbx = None

    xfer_stats = { 'xname': None, 'files_tot': 0, 'files_done': 0, 'cur_file': None, 'gtotal': 0, 'gxfer': 0, 'ttotal': 0, 'txfer': 0, 'last_update': 0 }

    statusUpdateFreq = 1.0

    def __init__(self,hostname,username=None,keyfile=None,password=None,port=22,timeout=None,autoconnect=True):
        """
        initialize, connect, and establish sftp channel
        """
        # initialize our big daddy, SSHClient
        super(self.__class__, self).__init__()

        # set hostkey policy
        self.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())

        if not username: username = os.getlogin()

        # connect
        if autoconnect:
            try:
                self.connect(hostname,port,username,password,key_filename=keyfile,timeout=timeout,compress=True)
            except Exception as e:
                logthis("!! Failed to connect via SSH to remote host (%s@%s:%d):" % (username,hostname,port),suffix=e,loglevel=LL.ERROR)
                return

            self.connected = True
            logthis("** Connected to remote host via SSH:",suffix="%s@%s:%d" % (username,hostname,port),loglevel=LL.INFO)

            # initialize sftp channel
            self.rsc = self.open_sftp()

    def jabber(self,jabobj):
        """
        set jabber ref
        """
        self.jbx = jabobj

    def xfer(self,src,dest):
        """
        perform recursive 'put' operation via sftp
        """
        rps = os.path.realpath(os.path.expanduser(src))
        localbase = os.path.dirname(rps)
        dlist = []
        flist = []
        totsize = 0

        # if directory, then get listing
        if os.path.isdir(rps):
            rootdir = os.path.basename(rps)
            xname = rootdir
            for dpath,dirs,files in os.walk(rps):
                # get path relative to our src dir
                drel = dpath.replace(localbase,'')
                dlist += [ drel ]
                # enumerate files
                for tf in files:
                    flist += [ drel+'/'+tf ]
                    totsize += os.lstat(dpath+'/'+tf).st_size
        else:
            rootdir = None
            xname = os.path.basename(rps)
            flist = [ '/'+xname ]
            totsize = os.lstat(rps).st_size

        logthis(">> Xfer [%s] -> [%s]" % (src,dest),loglevel=LL.INFO)
        logthis(">> Files: %d / Dirs: %d / Size: %s" % (len(flist),len(dlist),fmtsize(totsize)),loglevel=LL.INFO)
        logthis("dlist:\n",suffix=print_r(dlist),loglevel=LL.DEBUG)
        logthis("flist:\n",suffix=print_r(flist),loglevel=LL.DEBUG)

        # check that we have enough free space on target device
        dfree = self.df(dest)
        logthis("-- Free space on %s (%s):" % (dfree['dev'],dfree['mount']),suffix=fmtsize(dfree['free']),loglevel=LL.VERBOSE)
        if dfree['free'] < totsize:
            logthis("!! Not enough free space on target device",suffix="%s (%s)" % (dfree['dev'],dfree['mount']),loglevel=LL.ERROR)
            return False

        # create rootdir
        if rootdir and not self.ifexist(dest+'/'+rootdir):
            try:
                self.rsc.mkdir(dest+'/'+rootdir,mode=os.lstat(localbase+'/'+rootdir).st_mode)
            except Exception as e:
                logthis("!! Failed to create rootdir (%s). Error:" % (localbase+'/'+rootdir),suffix=e,loglevel=LL.ERROR)
                return False

        # create directories
        for xtd in dlist:
            if not self.ifexist(dest+xtd):
                try:
                    self.rsc.mkdir(dest+xtd,mode=os.lstat(localbase+xtd).st_mode)
                except Exception as e:
                    logthis("!! Failed to create directory (%s). Error:" % (dest+rootdir),suffix=e,loglevel=LL.ERROR)
                    return False

        # set up xfer_stats
        self.xfer_stats = { 'xname': xname, 'files_tot': len(flist), 'files_done': 0, 'cur_file': None, 'gtotal': totsize, 'gxfer': 0, 'ttotal': 0, 'txfer': 0, 'last_update': 0 }

        # copy files
        for xtf in flist:
            logthis(">> [put] %s -> %s" % (localbase+xtf,dest+xtf),loglevel=LL.VERBOSE)
            self.xfer_stats['cur_file'] = xtf
            self.rsc.put(localbase+xtf,dest+xtf,callback=self._progress)
            self.xfer_stats['files_done'] += 1
            self.xfer_stats['gxfer'] += os.lstat(localbase+xtf).st_size

        logthis("** Xfer complete:",suffix=xname,loglevel=LL.INFO)
        return self.xfer_stats['gxfer']

    def df(self,path):
        """
        get free diskspace for a given input path
        """
        dfo = self.rexec('df -P "%s"' % (path)).splitlines()[1].split()
        dfx = { 'dev': dfo[0], 'total': int(dfo[1]) * 1024, 'used': int(dfo[2]) * 1024, 'free': int(dfo[3]) * 1024, 'usage': (float(dfo[2]) / float(dfo[1]) * 100.0), 'mount': dfo[5] }
        return dfx

    def rexec(self,cmd):
        """
        simple wrapper around exec_command that returns stdout as a string
        """
        si,so,se = self.exec_command(cmd)
        sout = so.read()
        return sout

    def _progress(self,txb,totb):
        """
        file xfer progress callback
        """
        nowtime = time.time()
        self.xfer_stats['txfer'] = txb
        self.xfer_stats['ttotal'] = totb
        # if statusUpdateFreq has elapsed, then update jabber status
        if (nowtime - self.xfer_stats['last_update']) > self.statusUpdateFreq:
            # update jabber status
            dltot = self.xfer_stats['gxfer'] + self.xfer_stats['txfer']
            percento = float(dltot) / float(self.xfer_stats['gtotal']) * 100.0
            jabber.send('set_status', { 'show': "xa", 'status': "Downloading [%0.01f%% -- %s of %s]: %s" % (percento,fmtsize(dltot),fmtsize(self.xfer_stats['gtotal']),self.xfer_stats['xname']) })
            self.xfer_stats['last_update'] = nowtime

    def ifexist(self,rpath):
        """
        check if remote file/dir exists
        """
        try:
            self.rsc.stat(rpath)
            return True
        except:
            return False
