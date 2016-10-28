
# Rainwatch
*rainwatch* is a tool for managing downloads from the Deluge or rTorrent torrent clients. It can be triggered when a torrent download has completed, and rainwatch will then connect to the torrent daemon via its RPC interface and move the file or folder to the location specified in the config file.

The config file contains a list of rules and regular expressions to match files, where to move them, and so on. Moving files and folders (and renaming them) is done via the RPC interface for Deluge, so the torrent will still be active and seeding in the client, without the need for copying or creating symlinks.

## License
```
Copyright (c) 2016 Jacob Hipps / Neo-Retro Group, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

## Installation

### Prerequisites

#### Redis

Rainwatch uses Redis for shared queue management.

In Debian-like distros:

	sudo apt-get update
	sudo apt-get install redis-server
	service redis start

In RedHat-like distros:

	sudo yum install redis
	service redis start

#### MongoDB

Mongo is used for storage of rules, logging (optionally), and certain configuration parameters.

*MongoDB 3.0 or later is required*

> https://docs.mongodb.com/v3.0/administration/install-on-linux/


#### Python 3.5

Python 3.5 is recommended, but other versions of Python 3.x may work. On Ubuntu 14.04 or Debian 8.x:

	sudo add-apt-repository ppa:fkrull/deadsnakes
	sudo apt-get update
	sudo apt-get install python3.5-complete libpython3.5-dev libpython3.5-stdlib
	wget https://bootstrap.pypa.io/get-pip.py
	sudo python3.5 get-pip.py

The pip installer will update your default pip and pip3 packages to use Python 3.5, which is probably not what you want. To revert back to the defaults:

	sudo sed -i 's/python3.5$/python/' `which pip`
	sudo sed -i 's/python3.5$/python3/' `which pip3`

### PyLint (optional)

PyLint is optional, and is used to check the source for errors and other potential issues.

If you're already using PyLint for Python 2.x, then run the following:

	export PLBASE=$(which pylint)
	sudo mv $PLBASE{,2}
	sudo pip3.5 install pylint
	sudo mv $PLBASE{,3}
	sudo ln -s $PLBASE{2,}

This will give you `pylint`, which is symlinked to `pylint2`, as well as `pylint3`.

Otherwise, if you only need PyLint for Python 3.x, run the following:

	sudo pip3.5 install pylint
	sudo ln -s `which pylint`{,3}

This will give you `pylint`, which is symlinked to `pylint3`.

Whichever method you choose, the linter task in Gulp will reference `pylint3`.

### SleekXMPP install

Rainwatch requires SleekXMPP 1.4.0 or later. As of this writing, it is not yet available from PyPI, so it must be installed from source.

	git clone https://github.com/fritzy/SleekXMPP.git
	cd SleekXMPP
	sudo python3.5 setup.py install

### Rainwatch install

	git clone https://git.ycnrg.org/scm/yrw/rainwatch.git
	cd rainwatch
	sudo python setup.py install
	npm install
	gulp

Alternatively, use `develop` (instead of `install`) to allow for easy updates or development work:

	sudo python setup.py develop

### List of Prerequisites

##### Python modules

- docutils
- setproctitle
- PyMongo
- Redis
- PyMediaInfo
- Enzyme
- deluge-client
- dnspython
- Arrow
- Paramiko
- Flask (>=0.10.1)
- Requests (>=2.2.1)
- Pillow (>=3.4.0)
- SleekXMPP (>=1.4.0)

##### External programs

- [Redis](http://redis.io/)
- [MongoDB](https://www.mongodb.com/) (>=3.0)
- [PyLint](https://pylint.org/) (optional, >=1.6.0)

## Configuration

It is recommended to create a `~/.rainwatch` directory to contain your configuration and rule files. However, configuration files can be placed in the following locations (in order of precedent): `./rainwatch.conf`, `~/.rainwatch/rainwatch.conf`, `~/.rainwatch`, or `/etc/rainwatch.conf`.

Below is an example of a minimal configuration file:
```
[core]
logfile = "~/.rainwatch/rainwatch.log"
rules = "~/.rainwatch/rules.conf"
tclient = "deluge"

[deluge]
hostname = "localhost"
user = "deluge_user"
pass = "secret"

[xfer]
hostname = "alpha.example.com"
user = "jacob"
basepath = "/destination/save/path"
keyfile = "~/.ssh/jacob-private-key"

[srv]
iface = "127.0.0.1"
url = "http://localhost:8080"
port = 8080
pidfile = "~/.rainwatch/rainwatch.pid"
shared_key = "replace.this.with.something.random"

```

The above config snippet will provide enough details to ensure that rainwatch is able to spawn a service, as well as connect to your torrent client and transfer the downloaded files to another machine. Rainwatch currently supports both Deluge and rTorrent. Check out the _Torrent Client_ below section for full details on both.

> In order for automated SFTP transfers to work properly, the provided key must **NOT** be secured with a passphrase. It is also recommended that you run rainwatch as a regular, unprivileged user, and that the xfer user is also non-root. You can test to ensure the SSH connection will work correctly via `ssh -i ~/.ssh/my-private-key user@xfer_host`

### All configuration options

Each option name is followed by the default value in italics. _(None)_ indicates the NoneType object in Python, and _()_ indicates an empty string.

#### [core] - Core configuration

- loglevel _(info)_ - Log level
- logfile _(rainwatch.log)_ - Log file output
- rules _(rainwatch.rules)_ - Rule file
- tclient _(deluge)_ - Torrent client: one of __deluge__ or __rtorrent__

#### [xfer] - SFTP transfer configuration

These settings define the server and location where completed downloads should be transferred. The transfer is done via Paramiko and does not use the actual `sftp` command.

- hostname _(None)_ - Server hostname. Either needs to be fully-qualified, or match a defined Host section in user's ssh_config
- user _(None)_ - SSH user for authentication
- port _(22)_ - SSH port number
- basepath _()_ - Remote basepath. This is where files will be copied
- keyfile _(None)_ - SSH private key (non-encrypted)

#### [notify] - DBus Desktop Notifications

Triggers a DBus notify event on the specified host when a file transfer begins. This is done by connecting via SSH, determining the user's DBus socket path, and executing the notify command. The actual `ssh` program is executed to perform this task, so the specified hostname should exist in the user's `~/.ssh/config`, and should have a corresponding private key to allow password-less login.

- hostname _(None)_ - Target hostname
- user _(None)_ - SSH username
- icon _()_ - Path to a PNG file __on the target host__ to use as an icon in the notify toast. Leave empty to send a notification without an icon. A good idea might be to use icons from `/usr/share/icons`

#### [srv] - Daemon configuration

Rainwatch runs a daemon service in the background to listen for new events, as well as manage the transfer queue. When a torrent is completed, rainwatch is called with the torrent's hash ID, and rainwatch submits the request to the running daemon via its REST interface. The URL defined below will be prefixed to these requests. This should be changed to the canonical URL when proxying requests via Nginx or another web server

- pidfile _(rainwatch.pid)_ - Path to PID file
- url _(http://localhost:4464)_ - URL used to access REST API from the client
- iface _(0.0.0.0)_ - IP to bind
- port _(4464)_ - Port to bind
- nofork _(False)_ - When `True`, prevents rainwatch from detaching itself from the user's tty and forking into the background. Useful mainly for debugging server crashes
- debug _(False)_ - When `True`, enables Flask's debug mode
- shared_key _()_ - A randomized shared key, used for simple authentication for inbound requests

#### [redis] - Redis configuration

- host _(localhost)_ - Redis server hostname
- port _(6379)_ - Redis server port
- db _(11)_ - DB number
- prefix _(rainwatch)_ - Keyspace prefix. All keys in Redis are prefixed with this string

#### [xmpp] - XMPP/Jabber configuration

Rainwatch can send completion notifications after a succesesful transfer, as well as indicate progress of a download via XMPP announce/presence. The user and password defined here will be used by rainwatch, and will show a status of 'Ready' when it's up and running.

- user _(None)_ - Jabber ID, user@domain.tld
- pass _(None)_ - Password
- server _(None)_ - Explicitly connect to this hostname, rather than relying on SRV records
- sendto _(None)_ - JID to send notifications. This can be a different domain (eg. sent to a user on a different Jabber server), as long as the host server is federated.
- avatar\_img _(None)_ - Path to an image to use for the Jabber bot's profile icon (optional). Should be of sensible dimensions. PNG or GIF types are recommended. Theoretically, any image type is possible, but clients must have the necessary support to display the supplied type.
- nick _(None)_ - Nickname for the bot to use (optional)

#### [deluge] - Deluge JSON-RPC configuration

Deluge RPC client configuration. Rainwatch connects via the JSON-RPC interface, so the credentials used here will be the same as those used when connecting with the deluge-gtk client. If the hostname is not localhost, Deluge will need to be configured to listen on a public interface, and 'Allow remote connections' should enabled

- user _()_ - Deluge RPC username
- pass _()_ - Deluge RPC password
- hostname _(localhost)_ - Hostname of server running deluged
- port _(58846)_ - deluged RPC port

#### [rtorrent] - rTorrent XMLRPC configuration

rTorrent RPC client configuration. Rainwatch connects via the XMLRPC interface. The rTorrent RPC interface does not use any authentication, so many people run rTorrent behind Nginx or another web server, and either enforce an ACL, or use Basic Auth. When using Basic Auth, modify the URI to include the authentication information. The URI should _not_ contain the `/RPC2` portion.

- uri _(http://localhost:5000)_ - rTorrent RPC base URI. Basic authentication can be encoded in the URL

#### [web] - Web interface configuration

- bw\_graph _(None)_ - URL to a graph generated by Graphite, Grafana, Cacti, Munin, etc. showing recent bandwidth usage. The URL should be accessible by users visiting the rainwatch web interface (eg. does not require proxying)
