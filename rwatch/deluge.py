#!/usr/bin/env python
# coding=utf-8
###############################################################################
#
# deluge - rwatch/deluge.py
# Rainwatch: Deluge RPC interface functions
#
# @author   J. Hipps <jacob@ycnrg.org>
# @repo     https://bitbucket.org/yellowcrescent/yc_xbake
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
import signal
import optparse
import operator
import time
from deluge_client import DelugeRPCClient

from rwatch.logthis import C,LL,logthis,ER,failwith,loglevel,print_r,exceptionHandler

class delcon:
	"""class for handling Deluge RPC comms"""
	xcon = None
	connected = False

	def __init__(self, duser, dpass, dhost='localhost', dport=58846, abortfail=True):
		"""connect to deluged and authenticate"""
		logthis("Connecting to deluged on",suffix="%s:%d" % (dhost,dport),loglevel=LL.INFO)
		self.xcon = DelugeRPCClient(dhost, dport, duser, dpass)
		try:
			self.xcon.connect()
		except Exception as e:
			logthis("Failed to connect to Deluge:",suffix=e,loglevel=LL.ERROR)
			if abortfail: failwith(ER.CONF_BAD, "Connection to Deluge failed. Aborting.")
		logthis("Connected to Deluge OK",ccode=C.GRN,loglevel=LL.INFO)
		self.connected = True

	def getTorrent(self, torid):
		"""get info on a particular torrent"""
		try:
			return self.xcon.call('core.get_torrent_status',torid,[])
		except Exception as e:
			logthis("Error calling core.get_torrent_status:",suffix=e,loglevel=LL.ERROR)
			return False

	def getTorrentList(self, filter={}, fields=['name','progress','tracker_host','eta','paused']):
		"""get list of torrents"""
		try:
			return self.xcon.call('core.get_torrents_status',filter,fields)
		except Exception as e:
			logthis("Error calling core.get_torrents_status:",suffix=e,loglevel=LL.ERROR)
			return False

	def renameFolder(self, torid, newname):
		"""rename torrent directory name"""
		# first, get info on this torrent
		torinfo = self.xcon.call('core.get_torrent_status',torid,[])

		# Check if the dir is the same as torrent name
		if os.path.isdir(torinfo['save_path'] + '/' + torinfo['name']):
			fdir = torinfo['save_path'] + '/' + torinfo['name']
		elif os.path.isdir(os.path.dirname(torinfo['save_path'] + '/' + torinfo['files'][0]['path'])):
			fdir = os.path.dirname(torinfo['save_path'] + '/' + torinfo['files'][0]['path'])
		else:
			logthis("Unable to determine existing directory name for",suffix=torid,loglevel=LL.ERROR)
			return False

		# get base dir from full path
		sdir = os.path.basename(fdir)

		try:
			self.xcon.call('core.rename_folder',torid,sdir,newname)
			return True
		except Exception as e:
			logthis("Failed to rename torrent dir:",prefix=torid,suffix=e,loglevel=LL.ERROR)
			return False

	def moveTorrent(self, torids, destdir):
		"""move torrent data (directory or file) to new location"""
		if not torids is list: torids = [ torids ]

		rpdir = os.path.realpath(destdir)
		if not os.path.isdir(rpdir):
			logthis("Failed to move torrent storage. Directory does not exist:",suffix=rpdir,loglevel=LL.ERROR)
			return False

		try:
			self.xcon.call('core.move_storage',torids,rpdir)
			return True
		except Exception as e:
			logthis("Failed to move torrent storage:",suffix=e,loglevel=LL.ERROR)
			return False


	def __del__(self):
		"""disconnect from deluged"""
		# nothing special required for disconnection, socket/connection
		# will be cleaned up on shutdown
		pass
