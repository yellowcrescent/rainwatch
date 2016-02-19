#!/usr/bin/env python
# coding=utf-8
###############################################################################
#
# jabber - rwatch/jabber.py
# Rainwatch: Jabber/XMPP functions
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
import signal
import optparse
import operator
import time
import xmpp

from rwatch.logthis import C,LL,logthis,ER,failwith,loglevel,print_r,exceptionHandler

class client:
	"""class for handling XMPP client comms"""
	clx = None
	ccon = None
	acon = None
	connected = False

	def __init__(self, juser, jpass, jres='rainwatch', jserver=None, jport=5222, abortfail=True):
		if jserver: jsx = (jserver,jport)
		else: jsx = None
		jid = xmpp.protocol.JID(juser)
		self.clx = xmpp.Client(jid.getDomain(),debug=[])

		# if server and port not specified, use the SRV records to determine server name and port
		crez = self.clx.connect(jsx)
		if not crez:
			logthis("Connection to Jabber server failed for",suffix=juser,loglevel=LL.ERROR)
			return
		else:
			self.ccon = crez
			logthis("Connected to Jabber server via",suffix=crez.upper(),ccode=C.GRN,loglevel=LL.INFO)

		# authenticate
		arez = self.clx.auth(jid.getNode(),jpass,jres)
		if not arez:
			logthis("Failed to authenticate to Jabber server for",suffix=juser,loglevel=LL.ERROR)
			return
		else:
			self.acon = arez
			logthis("Authenticated to Jabber server via",suffix=arez.upper(),ccode=C.GRN,loglevel=LL.INFO)

		# enable presence
		self.clx.sendInitPresence()
		self.connected = True

	def sendmsg(self, jid, msg):
		"""send a message (msg) to a user (jid)"""
		self.clx.send(xmpp.protocol.Message(xmpp.protocol.JID(jid),msg))

	def authorize(self, jid):
		"""authorize a JID"""
		self.clx.Roster.Authorize(xmpp.protocol.JID(jid))

	def set_status(self, status):
		"""set status message"""
		self.clx.setStatus(status)

	def __del__(self):
		self.clx.disconnect()
		self.connected = False
