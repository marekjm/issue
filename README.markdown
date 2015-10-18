# Dead-simple, no-bullshit, command-line issue tracker

It's really dead simple.
You go *Ya got any of them unresolved issues, man?* when looking at your project.
And it says nothing.

You have to open the browser, go to the issue tracker page, filter stuff and
only after that you have some overview of what's goin' on.

Why is it so?
Because you have to *break your workflow*.

Why can't it be simple?
You know what? It *can* be.

Why don't we just cut the bullshit and instead keep working on closing them issues?!
Yeah, why don't we? Well, now we can.

----

## Big-ass, feature-overpacked tools

Oh, man, you know them.
You know how it always starts...

It promises to deliever whatever you desire.

But, there is *one, small issue* with this.
You don't need any of that.
Yeah, you really don't.

Oh, well, maybe you actually do, but not from this tool.
It is supposed to help you manage issues.
It doesn't need email client, a doctor, or a file browser.

It got **one job**.
And it should do it well.

----

## Small, focused tools

That's where the `issue` comes in.

You want to get a list of issues?
Just enter `issue ls` into you shell.

You want to open an issue?
Just enter `issue open <message>` into you shell.

You want to close an issue?
Just eneter `issue close <id>` into you shell.

Can you get smaller than that?
You probably could, but `issue`'s interface is still minimal.
However, it provides all neccessary bits to act as an issue management tool.

The workflow is non-intrusive, the commands intuitive, and - what's most important - you *don't have to leave the command line*:

```
# hack hack hack
issue open "Dang, something's broken."
<here it gives you issue-ID>

# hack hack hack
issue comment <ID> "Will fix it tomorrow, have to think about some other problems first."

# and the next day...
issue close <ID>
```

Is that enough?
For a bare-bones setup we're aiming for it definitely is.

If you want more, how about this?

```
# let's open two issues
issue open -l <label-0> -l <label-1> -l <label-2> "Foo"
deadbeef

issue open -l -l <label-1> -l <label-2> "Bar"
c00ffee

# list them
issue ls
deadbeef: Foo
c00ffee: Bar

# fileter by label
issue ls -l <label-0>
deadbeef: Foo

issue ls -l <label-1>
deadbeef: Foo
c00ffee: Bar

# close one issue
issue close deadbeef

# list them (all by default)
issue ls
deadbeef: Foo
c00ffee: Bar

# list only open ones
issue ls --open
c00ffee: Bar

# list only closed ones
issue ls --closed
deadbeef: Foo

# show details about an issue
issue show deadbeef
```

What about a team-oriented workflow?

```
# add remote issue repository
issue remote add <name> <ssh-url>

# fetch missing objects (issues, comments etc.)
issue fetch

# list all issues
issue ls
deadbeef: Foo
c00ffee: Bar
feedbeef: Baz
f00d600d: Bay

# index local objects to make fetching easier for peers
issue --pack
```

More documentation is available with `issue help` command (use `issue help --verbose` to get full list of available features).
