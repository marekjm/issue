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
# set your credentials
$ issue config --global set author.email "john.doe@example.com"
$ issue config --global set author.name "John Doe"
```

And you are ready to run.

----

## It's really dead simple

Issue is written with the intent to keep the workflow optimised, and
reduce distractions to minimum.

Consider these steps:

- `issue open "Crash on big numbers"` - open an issue,
- `git checkout -b $(issue slug --git deadbeef)` - create new branch using branch name generation,
- `gdb ./a.out` - debug the program,
- `vim ...` - create a patch,
- `git commit -m 'Fix the crash on big numbers'` - commit the fix,
- `issue close -g <git-commit> deadbeef` - close the issue,

Two additional commands to open and close an issue.


### Features when needed

A comment can be put on an issue:

- `issue comment deadbeef "User input could use better validation..."`,

Issues can be listed with `ls` command:

- `issue ls` - list all issues,
- `issue ls --open` - list all open issues,
- `issue ls --closed` - list all closed issues,
- `issle ls --open -t bug` - list all open issues with tag `bug`,
- `issle ls --open -t ^bug` - list all open issues without tag `bug`,

Issue details (tags, comment thread) can be displayed with `show` command:

- `issue show <unique-id>`


### Issues distribution

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

### More

Issue overview is available with `issue help` command (use `issue help --verbose` to get full list of available features).

----

## License

Issue is published under the GNU GPL v3 license.
Mail me if you would like to use the software under a different license.

----

## Dependencies

Issue requires a recent version of Python 3, and [`CLAP`](https://github.com/marekjm/clap) library to run.
Both components should be easily installed in any Linux system.
CLAP must be installed with Git.
Issue requires CLAP at least version `0.10.1`.
