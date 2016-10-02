#!/usr/bin/env python
# coding=utf-8

from setuptools import setup, find_packages
setup(
    name = "rainwatch",
    version = "0.11.17",
    author = "Jacob Hipps",
    author_email = "jacob@ycnrg.org",
    license = "MIT",
    description = "Deluge download manager and RPC client",
    keywords = "deluge rpc client download manager torrent",
    url = "https://bitbucket.org/yellowcrescent/rainwatch/",

    packages = find_packages(),
    scripts = ['rainwatch'],

    install_requires = ['docutils>=0.3','setproctitle','pymongo>=3.0','redis>=2.10','pymediainfo>=1.4.0','enzyme>=0.4.1','deluge-client>=1.0.3','xmpppy','paramiko>=1.16.0','flask>=0.10.1','requests>=2.2.1'],

    package_data = {
        '': [ '*.md' ],
    }

    # could also include long_description, download_url, classifiers, etc.
)
