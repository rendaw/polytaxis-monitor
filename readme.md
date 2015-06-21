# Installation

Requires Python 3.

Run:
```
pip install git+https://github.com/Rendaw/polytaxis-python
pip install git+https://github.com/Rendaw/polytaxis-monitor
```

# Utilities

## polytaxis-monitor

`polytaxis-monitor` monitors directories for polytaxis file additions/modifications/deletions and indexes their tags.

Files with no tags will be categorized with the tag 'untagged'.

**note** If you want to monitor a mount, make sure it's mounted before you start the monitor or nothing will be detected.

For usage, run `polytaxis-monitor -h`.

### Launching at boot

**note**: If you haven't yet indexed existing files, run `polytaxis-monitor` manually with the `-s` argument before setting up the service.

#### Linux (with systemd)

Requires a distribution that supports user systemd instances.

Create the file `~/.config/systemd/user/polytaxis-monitor.service` with the contents:
```
[Unit]
Description=polytaxis-monitor

[Service]
Type=simple
ExecStart=/usr/bin/polytaxis-monitor /home/my/files

[Install]
WantedBy=default.target
```

Configure the line `ExecStart` to contain directories you wish to monitor.

Run the following to start and run `polytaxis-monitor` at boot (with proper systemd configuration).
```
systemctl --user start polytaxis-monitor.service
systemctl --user enable polytaxis-monitor.service
```

#### Mac OSX (with launchd)

Create the file `~/Library/LaunchAgents/polytaxis-monitor.plist` with the contents:
```
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.zarbosoft.polytaxis-monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>polytaxis-monitor</string>
        <string>/Users/Me/my/files/</string>
    </array>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Run
```
launchctl load ~/Library/LaunchAgents/polytaxis-monitor.plist
launchctl start ~/Library/LaunchAgents/polytaxis-monitor.plist
```

**note**: This service doesn't run outside of your login, so if you modify/create/delete/move files as a different user (for example) the modifications won't be detected.

## ptq

`ptq` is a command line tool to query the `polytaxis-monitor` database. `ptq` can search for files by tag as well as search available tags.

For information on flags and other arguments, run `ptq -h`.

#### File Queries
File queries are written as a list of terms. A term can be an inclusion (`tag` or 
`tag=value`, matched in full), an exclusion (`^tag` or `^tag=value`), or a 
special term. Terms should be escaped if there are non-syntax special 
characters (equal signs, spaces, newlines, etc.) in the text.

Inclusions and exclusions can also incorporate `%`, which acts as a wildcard.

Special terms:
```
COLUMN>VALUE    Only output rows where the value of COLUMN > VALUE.
COLUMN>=VALUE   Only output rows where the value of COLUMN >= VALUE.
COLUMN<VALUE    Only output rows where the value of COLUMN < VALUE.
COLUMN<=VALUE   Only output rows where the value of COLUMN <= VALUE.
sort+:COLUMN    Sort output, ascending, by COLUMN.
sort-:COLUMN    Sort output, descending, by COLUMN.
sort?:COLUMN    Sort output, randomly, by COLUMN.
col:COLUMN      Include COLUMN in the output. If no columns are specified,
                show the filename.
```

Sorts are specified in higher to lower pecedence.
Currently, columns cannot be selected (only the filename is displayed).

Example:
```bash
ptq 'album=polytaxis official soundtrack' sort+:discnumber sort+:tracknumber
```

#### Tag Queries
Tag queries take a single string. The string is used as a query parameter
based on the query modifier ('prefix' or 'anywhere').

Example:
```
ptq -t prefix album=
```
The above lists all albums.

