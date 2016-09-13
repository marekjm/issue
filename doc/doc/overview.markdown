# Issue

> A distributed issue tracking system.


## TL;DR

Issue is a distributed issue tracking system.
It is designed for programmers working Linux/\*NIX environments and
is highly optimised for fast, commandline interaction and
smooth integration into existing workflow and toolchain.


#### Features

Main features of Issue are:

- distributed model of work
- independence from constant network access
- using only minial amount of data during each synchronisation run
- independence from a database engine (Issue provides its own distributed database-like model)
- dumb remote server (a shared remote repository is just a directory somewhere in the filesystem),

> **Note about using Git with issue**
>
> Certain aspects of the software are adjusted for Git-based workflow, but Issue is
> independent from Git and may be effectively used without it.


#### Limitations

Current version of the system has some limitations:

- only SSH supported for transfer
- suboptimal algorithm for transferring data (requires multiple SSH connections)
- young protocol prone to changes (structure of a repository is mostly stable but may change in the future),


## Workflow

The commands provided should be intuitive for target audience:

```
$ vi src/main.cpp
$ make
$ make test
.......
Segmentation fault, core dumped
$
$ issue open -t bug -t urgent  # opens $EDITOR to enter issue message
Short description of a bug

With optional longer description following the subject line.
$
$ issue slug -gBC --last  # create a Git-friendly slug, use it to create new branch and "git checkout" to it
*hack hack hack*
$ make
$ make test
...........
OK
$
$ git checkout -
$ git merge -
$ issue close --git HEAD --last
$
$ git push
```

As can be seen in the example, three commands provided by Issue are used in the basic process of tracking an issue.
First is `open` - which opens an issue (with optional tags set with `-t/--tag` switches); it opens up `$EDITOR` to prompt
use for issue message.
Second is slug (term *slug* comes from the world of newspaper editing, and is a short name assigned for a story or article).
This command is used to generate branch names for source-code-tracking software and is integrated with Git;
short switches used above expand to `issue slug --git --git-branch --git-checkout --last`.
Third command is `close` - and it closes the issue (setting optional Git commit SHA1 as *closing commit*, SHA1 hashes are
always stored in full length).

One option appears twice - the `--last` one in `close` and `slug` commands.
Usually, almost every Issue command requires issue SHA1 as an operand.
However, when `--last` switch is given on the command line Issue will automatically find *last active* issue and
supply it as an operand.

Additional frequently used commands are `publish`, `fetch` and `show`.


## The model

On the lowest level Issue is a distributed, domain-specific data exchange system with fat, feature-packed client that
requires either very dumb or no exchange servers.

> **Distribution method advice**: While issue is *fast* when run locally, synchronisation over the network is
> painfully slow (only dumb SSH copying is implemented).
> It is advised to track Issue repository changes with a VCS used in the project, and
> to piggyback on its transport method to distribute the diffs.
> Issue diffs are JSON-encoded text files so no binary blobs will appear in the VCS repository.
>
> This may, however, alter the distributed nature of Issue if your VCS of choice is not distributed.

Every issue is represented as an *object* under a *class namespace* within the network.
A class namespace is a separator between different object classes, e.g. issues, milestones, tags and
can be thought of as a *type* (i.e. a class) of an object.
Objects with the same SHA1 identifiers *can* appear under different class namespaces but there are no clashes as
every object is referred to with its full path - `<class>.<shortest class-unique sha1>`, e.g. `issue.4a69`.
Each change to an issue (a *diff* is saved as a separate object in the *object namespace*).
An object namespace is similar to class namespace, only limited to a single object within a class (an example
would be `issue.4a69.diff.c0ff`).

The hierarchy representing class and object namespaces resides in each Issue repository in `objects/` directory.
Example:

```
.issue/
       objects/
               issue/ # opens a class namespace
                     4a/
                        4a6920dfb...7f8/ # opens an object namespace
                                        diff/
                                             f00deadbeef...05
```

Objects are encoded using JSON.
Diffs (recorded changesets) are encoded using JSON.

Objects represent static data *indexed from available set* of diffs.
As such, objects themselves do not exist and
are only a result of processing an ordered sequence of diffs.
This means that on a two fully synchronised repositories every object has exactly the same state, but
on two only partially synchronised repositories the same object may contain different data.

This model provides transfer efficiency (only diffs are exchanged and not full, indexed objects),
write efficiency (only creates new, small files) and
network independence (no need to have a constant connection).
The tradeoff is reduced read efficiency (objects must be indexed before they can be fully displayed;
viewing changelogs does not require indexing though).
Indexing can be made faster by only applying *new diffs*, i.e. those that were not so far included in
the full representation of an object.


Network is formed by *nodes*.
Each node can be either an *endpoint* or an *exchange*.
Endpoint nodes are client repositories and can only be fetched from (current limitation, may be removed later).
Exchange nodes act as shared repositories and issues can be fetch from, or published to them.
Using single exchange node for multiple projects is not recommended; however, it is not enforced and is only a suggestion.

Every issue can be tagged but *tag objects* are not shared between repositories (they can be easily recreated locally and
Issue makes it easy to do so).
