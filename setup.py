#!/usr/bin/env python
# coding=utf-8

from setuptools import setup, find_packages
setup(
    name = "rainwatch",
    version = "0.11.18",
    author = "Jacob Hipps",
    author_email = "jacob@ycnrg.org",
    license = "MIT",
    description = "Deluge download manager and RPC client",
    keywords = "deluge rpc client download manager torrent",
    url = "https://bitbucket.org/yellowcrescent/rainwatch/",

    packages = find_packages(),
    scripts = [],

    install_requires = ['docutils','setproctitle','pymongo','redis','pymediainfo','enzyme','deluge-client','xmpppy','paramiko','flask>=0.10.1','requests>=2.2.1','arrow'],

    package_data = {
        '': [ '*.md' ],
    },


    entry_points = {
        'console_scripts': [ 'rainwatch = rwatch.cli:_main' ]
    }

    # could also include long_description, download_url, classifiers, etc.
)
