
# Rainwatch
*rainwatch* is a tool for managing downloads from the Deluge torrent client. It can be called via the Execute plugin when a torrent download has completed, and rainwatch will then connect to deluged via its RPC interface and move the file or folder to the location specified in the config file.

The config file contains a list of rules and regular expressions to match files, where to move them, and so on. Moving files and folders (and renaming them) is done via the Deluge RPC interface, so the torrent will still be active and seeding in the client, without the need for copying or creating symlinks.

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