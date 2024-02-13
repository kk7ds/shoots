# A simple pluggable CLI for the Bambu X1C

I wrote this for my own interfacing and automation, but it might be useful
to others. I haven't tested it with anything other than *my* X1C in LAN mode.

This tool is extensible, meaning it is easy to add new functionality in a
modular way. It is pluggable so you can add your own local commands or
hooks with python entry points.

Works on linux, macOS, and Windows without external dependencies (other than
Python).

This is not associated with Bambu Labs in any way.

## Install
```
$ pip install git+https://github.com/kk7ds/shoots
```

## Usage
```
$ shoots -h
usage: shoots [-h] [--host HOST] [--device DEVICE] [--listen LISTEN] [--reconnect] [-v] [--debug]
              key {debug,files,info,monitor,print} ...

positional arguments:
  key                   Network key
  {debug,files,info,monitor,print}
                        Command to run
    debug               Watch for every stat
    files               Manage files on printer
    info                Show info about printer
    monitor             Watch printer status
    print               Control printing

options:
  -h, --help            show this help message and exit
  --host HOST           Hostname to connect to, otherwise find first printer via discovery
  --device DEVICE       Printer Device ID (detect on connect if ommitted)
  --listen LISTEN       Listen address for discovery
  --reconnect           Attempt to (re)connect forever
  -v, --verbose         Log verbosely
  --debug               Log all messages and other debug info
```

By default, it will try to discover the printer the usual way. However, you
can just pass it the hostname/IP to connect directly (which Bambu should
support everywhere, of course.) You must pass the network key per usual.

Example:
```
$ shoots abab01cd files list
Benchy.gcode.3mf
Scraper.gcode.3mf
$ shoots abab01cd print fromsd --file Benchy.gcode.3mf
$ shoots abab01cd monitor
Printing 0% complete 1h9m remaining, ETA 14:05:57
Printing 1% complete 1h8m remaining, ETA 14:05:57
```

Run it with `--verbose` for more information about the discovery and connection
process, or with `--debug` for *all* the details.
