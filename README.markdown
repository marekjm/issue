# Dead-simple, no-bullshit, command line issue tracker

Issue is a command line issue tracker with dead-simple interface, and *no-bullshit* philosophy.

### Command-line issue tracker?

Issue has only one interface - the cli `issue` tool written in Python 3.

### Dead-simple interface?

The command line tool is built around simple actions, e.g. opening, closing or commenting issues.
All of basic concepts map to a command:

- `issue open "<message>"` to open an issue,
- `issue close <unique-id>` to close an issue,
- `issue comment <unique-id> "<comment>"` to comment on an issue,

### No-bullshit philosophy?

Issue provides machinery for those few things that are really neccessary:

- opening issues,
- listing issues,
- closing issues,
- commenting on issues,
- sharing issues with other programmers,

Notice the word *programmers*.
It is not a tool intended to be used by general audience.

It is created for those people who spend numerous hours a day
in front of a black screen filled with code, shell commands and debugger output.
They don't need the distraction of switching to a web-based issue tracker
but still may need to note problems with the code.
This program is created for them - to not break their workflow,
but to be easily intergrated into it.
Written with the UNIX spirit in mind, it does one thing and (hopefully) does it well.

All the extra features are written while keeping in mind that the target group are programmers.
For example, there is a `issue slug` command that generates branch names based on issue messages.

### Quick to start and almost configuration-free

These are the only commands you have to run before you can initialise a repository and
start creating issues:

```
# set your credentials...
$ issue config --global set author.email "john.doe@example.com"
$ issue config --global set author.name "John Doe"
# initialise the repository
$ issue init
```

And you are ready to run.
For more help, you can use:

```
$ issue help -vc | less -R
```

This command will give you an exhaustive overview of the commands and
options.

--------------------------------------------------------------------------------

## It's really dead simple

Issue is written with the intent to keep the workflow optimised, and
reduce distractions to minimum.

Consider these steps:

- `issue open "Crash on big numbers"` - open an issue
- `git checkout -b $(issue slug --git deadbeef)` - create new branch using
  branch name generation
- `gdb ./a.out` - debug the program
- `vim ...` - create a patch
- `git commit -m 'Fix the crash on big numbers'` - commit the fix
- `issue close -g HEAD deadbeef` - close the issue

Two additional commands to open and close an issue.

--------------------------------------------------------------------------------

## Features when needed

Issue provides you with more than just `open` and `close` commands. This FAQ
will provide examples of common tasks that you can perform using the tool.

The `deadbeef` string will be used to provide a placeholder for an issue ID.

#### How do I put a comment on an issue?

```
$ issue comment deadbeef 'A comment'
```

If you do not supply the comment text directly on the command line, an `$EDITOR`
will be open for you, with a message reminding you what you wanted to do:

```
$ issue comment deadbeef
A comment
# Type a comment.
# Lines beginning with '#' will be ignored.
#
# Issue deadbeefd2eece78dbf8f98e357ba0af65f7e180:
#
#  > Dummy issue
#  >
#  > A dummy issue's description.
#
# vim:ft=gitcommit:
#
```

#### How can I get a list of stored issues?

```
$ issue ls              # all issues
$ issue ls --open       # only open issues
$ issue ls --closed     # only closed issues
```

Issue also provides you with more sphisticated methods of listing issues.

#### How do I filter the list of stored issues?

```
$ issue ls "your" "filter" "terms"
```

The `--open` and `--closed` options also work:

```
$ issue ls -o "memory"  # List all open issues related to "memory".
$ issue ls -c "test"    # List all closed issues related to testing.
```

You can also filter by time.

*List all open issues created during last two weeks, that contain the keyword
"deadlock"*:

```
$ issue ls -o --since 2weeks "deadlock"
```

*List all issues closed today*:

```
$ issue ls -c --since 8hours
```

*List all open issues created in the previous week*:

```
$ issue ls -o --since 2weeks --until 1week
```

*List all issues with tag "bug" created more than 3 days ago*

```
$ issue ls --until 3days --tag bug
```

#### How do I put a tag on an issue?

```
$ issue tag 'bug' deadbeef
```

This will put a tag `bug` on the issue `deadbeef`. The full example would be
like this:

```
$ issue show deadbeefd2eece78dbf8f98e357ba0af65f7e180
issue deadbeefd2eece78dbf8f98e357ba0af65f7e180
opened by:    John Doe (john.doe@example.com), on 1970-01-01 23:59:59.000000

    Dummy issue
$ issue tag bug deadbeef
issue deadbeefd2eece78dbf8f98e357ba0af65f7e180
opened by:    John Doe (john.doe@example.com), on 1970-01-01 23:59:59.000000
tags:         bug

    Dummy issue
```

A tag must be created before it can be assigned to issues. This prevents typos
and frustration when looking for issues tagged with `docs` and not finding the
one accidentally tagged `doca`.

#### How do I create a new tag?

```
$ issue tag new 'tagname'
```

#### How do I list all available tags?

```
$ issue tag ls
```

#### How do I display issue details?

```
$ issue show deadbeef
```

#### How do I link two issues together?

```
$ issue chain link deadbeef f1eece
```

This command will "chain" the issue `f1eece` to `deadbeef`. This will be visible
in the output of `issue show deadbeef`.

An issue cannot be closed until all issues that are chained to it are closed. In
the example above Issue will not allow closing `deadbeef` before `f1eece` is
closed.

#### How do I get some statistics?

```
$ issue statistics
```

This will give you an overview of the repository:

- how many open and closed issues it has
- the total, average, and median lifetime of open and closed issues
- the total, average, and median lifetime of all issues without the division
  into open and closed

#### How do I track issue repository within a Git repository?

Issue creates its repository inside a `.issue` directory. Since it is a hidden
file any reasonable `.gitignore` will opt out of tracking it. Here are the rules
you need to put inside your `.gitignore` file to enable tracking of the relevant
bits of the issue repository:

```
!.issue
.issue/*
!.issue/objects
.issue/objects/issues/*/*.json
```

Paste this rules after the `.*` rule and Git will track issue diffs and comments
without tracking all the other files that can be crated locally (using less data
when either cloning or pushing - "yay!" for efficiency).

After that, you can just periodically use `git add .issue` and commit changed
issues like any other file.

#### How do I avoid typing all this?

Yeah, typing `issue statistics` can get old really quick. Lucky you, Issue
commands may be abbreviated (funny that the word meaning "shortened" is a long
one). So instead of typing `issue statistics` you can just type `issue st`. The
shortest string that uniquely identifies a command will work.

As another example, instead of using `issue tag new foo` you can use
`issue t n foo`.

#### How do I create a branch name based on an issue?

```
$ issue slug deadbeef
issue-deadbeef-dummy-issue
```

Then you can either create a command like this one:

```
$ git checkout -b $(issue sl deadbeef)
```

...or use the shortcuts built into Issue itself:

```
$ issue sl -BC deadbeef
```

#### How do I reming myself what I was doing?

```
$ issue log
```

The log contains a list of events that happened inside you local repository.
This log is *not* exchanged between repositories as every developer has their
own log (the fact that Alice checked the `deadbeef` issue does not mean that
Bob also did and would pollute his log).

#### How do I get help?

```
$ issue help -vc | less -R
```

This will give you a long, long wall of text that lists every option and command
that Issue provides. The `-v` (or `--verbose`) is there to enable recursive help
screen display, and `-c` enabled colours.

Alternatively, you can get a help screen about just a single command:

```
$ issue help -c ls
```

or a even a single option:

```
$ issue help -c ls --open
```

--------------------------------------------------------------------------------

### Arcane features: Issues distribution (HERE BE DRAGONS!)

> Note that using the built-in features for issue distribution is discouraged.
> They are slow, inefficient, and not really tested. It is much better to just
> track issue repository as a normal directory in your Git repository.

Issue is designed as a distributed system, with a *pull* method for data distribution.
A peer must explicitly pull the data and cannot push it.
Currently, Issue can use only SSH for issue distribution.

Remote nodes are managed with `remote` command:

- `issue remote set --url <username>@<hostname>:<path> <remote-name>` - to set a remote,
- `issue remote set --key <key-name> --value <data> <remote-name>` - to set additional info for a remote,
- `issue remote ls [--verbose]` - to list available remote names (include `--verbose` to display SSH URLs in the report),
- `issue remote rm <remote-name>` - to remove a remote,

Before peers can fetch data from a node, it must *pack* its repository to announce what is available from it.
Each node should maintain an up-to-date pack of itself.
Pack is updated with `issue --pack` command.

Obtaining data from a node is simple:

- `issue fetch --probe <remote-name>` - to probe a remote and display how much data it holds that is locally unavailable,
- `issue fetch <remote-name>` - to fetch locally unavailable data,

Every node in the network operates as a peer to others, and there is no central one.

--------------------------------------------------------------------------------

## License

Issue is published under the GNU GPL v3 license.
Mail me if you would like to use the software under a different license.

--------------------------------------------------------------------------------

## Dependencies

Issue requires a recent version of Python 3 (any above 3.6 should be good).

Libraries:

- [`CLAP`](https://github.com/marekjm/clap): at least `0.10.1` (must be installed from Git)
- `unidecode`: at least `1.0.23`
- `colored`: at least `1.3.93` (optional; provides colorisation)
