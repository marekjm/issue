# Filtering issues

When you're looking for a specific issue, you usually apply filters to the list of issues
stored in the repository.
You may want to see only issues with tag `bug` whose description contains keyword
`interface` but does not contain keyword `user`, for example to see issues opened for your
programming interfaces.

Issue provides `ls` command for browsing through, searching, and listing issues.
The `ls` command has several options that alter its behaviour; also, its operands can also
have varying semantics.
This article exlains the `ls` command in greater detail.


----


## Status

All issues have a status, which is either `open` or `closed`.
This basic filter can be applied using `--open` (short `-o`) or
`--closed` (short `-c`) options.

By default, issues with both statuses are listed.

**Example:**

```
# list all open issues
issue ls --open

# list all closed issues
issue ls --closed
```


----

## Tag

An issue can have zero or more tags assigned.
It is possible to list issues containing specific tag
using `--label` (short `-l`) option.
Several tags may be listed.

```
# list all open urgent bugs
issue ls -o -l urgent -l bug

# list all closed "feature" issues
issue ls -c -l feature
```


----

## Time and date

Issues can be filtered using time periods.

For example, you may want to list all issues closed since last two weeks or
you may want to list all issues older than one month that are still open.
First command would be `issue ls --closed --since 2weeks` and
the second one would be `issue ls --open --until 1month`.

There are two options used to filter issues by time:

- `--since` (short `-S`) lists issues *newer* than specified time,
- `--until` (short `-u`) lists issues *older* than specified time,

These two options may both appear several times on the command line to give a
more accurate description of a point in time, and it is posible to combine them (i.e. use both `--since` and
`--until` in a single command).
For example, to list issues newer than one week but older that one-and-a-half days use this command:
`issue ls --since 1week --until 1day --until 12hours`.
Or, to list issues closed since last hour: `issue ls -c -S 1hour`.

Both `--since` and `--until` take one parameter, with following format:

- `Nmonths?`,
- `Nweeks?`,
- `Ndays?`,
- `Nhours?`,
- `Nminutes?`,
- `Nseconds?`,

Consider following example:

```
issue ls --open -S 4months -S 2weeks -S 5days -S 1hout -S 46minutes -S 1second`
```

While not very common, it shows nicely how a precise point in time may be given for Issue.

> Note: as of version 0.1.4, points in time are always relative to *current time*.
> That is, there is no way to specify e.g. 13. December - if it's 17. you must say `--since 4days`.

There is another time-related option: `--recent` which shows recently modified issues.
The value used by recent is configurable with `default.time.recent` key and
must conform to the format of `--since` and `--until` options parameters.


----

## Keywords

An issue is listed only if it reaches at least a set threshold of *good enough* match.
This threshold is influenced by the number of operands given to the `ls` command, the
basic rule being: *the more opreands, the higher the threshold*.

Keywords can be bare words, like `foo` and `bar`, but can also be prefixed with modifiers.
Currently (as of version 0.1.4) following modifiers are available:

- `-` keyword should not appear in the description,
- `+` keyword should appear in the description,
- `^` keyword must not appear in the descritpion,
- `=` keyword must appear in the description,

To reuse the early example:

```
# list all open "bug" issues containing "interface" and not containing "user"
issue ls -o -l bug interface ^user
```
