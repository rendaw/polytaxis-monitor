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

