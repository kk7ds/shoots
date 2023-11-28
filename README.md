# A simple CLI for the Bambu X1C

I wrote this for my own interfacing and automation, but it might be useful
to others. I haven't tested it with anything other than *my* X1C in LAN mode.

Right now, this just implements one command called `monitor` which follows
the state of a print so I can watch it from something other than Bambu Studio.
The CLI is designed to be extensible so you can add more commands.

This is not associated with Bambu Labs in any way.

## Install
```
$ pip install https://github.com/kk7ds/shoots
```

## Usage
```
$ shoots -h
usage: shoots [-h] [--host HOST] [--device DEVICE] [--listen LISTEN] [-v] [--debug] key {monitor,other} ...

positional arguments:
  key              Network key
  {monitor}        Command to run
    monitor        Watch printer status

options:
  -h, --help       show this help message and exit
  --host HOST      Hostname to connect to, otherwise find first printer via discovery
  --device DEVICE  Printer Device ID (detect on connect if ommitted)
  --listen LISTEN  Listen address for discovery
  -v, --verbose    Log verbosely
  --debug          Log all messages and other debug info
```

By default, it will try to discover the printer the usual way. However, you
can just pass it the hostname/IP to connect directly (which Bambu should
support everywhere, of course.) You must pass the network key per usual.

Example:
```
$ shoots abab01cd monitor
Printing 51% complete 1h9m remaining, ETA 14:05:57
Printing 52% complete 1h8m remaining, ETA 14:05:57
. . .
```

Run it with `--verbose` for more information about the discovery and connection
process, or with `--debug` for *all* the details.
