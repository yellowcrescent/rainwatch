#!/usr/bin/env python3.5
# coding=utf-8

from setuptools import setup, find_packages
setup(
    name = "rainwatch",
    version = "0.12.1",
    author = "Jacob Hipps",
    author_email = "jacob@ycnrg.org",
    license = "MIT",
    description = "Deluge download manager and RPC client",
    keywords = "deluge rpc client download manager torrent",
    url = "https://bitbucket.org/yellowcrescent/rainwatch/",

    packages = find_packages(),
    scripts = [],

    install_requires = ['docutils', 'setproctitle', 'pymongo', 'redis', 'pymediainfo', 'enzyme',
                        'deluge-client', 'paramiko', 'flask>=0.10.1', 'requests>=2.2.1',
                        'arrow', 'sleekxmpp>=1.4.0', 'dnspython', 'Pillow>=3.4.0'],

    package_data = {
        '': [ '*.md' ],
    },

    entry_points = {
        'console_scripts': [ 'rainwatch = rwatch.cli:_main' ]
    }

    # could also include long_description, download_url, classifiers, etc.
)
