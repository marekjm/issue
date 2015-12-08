# Issue user manual: Opening issues

New issues are opened with `issue open` command.
In its most simple form it does not take any commandline options.

If issue message is not given on the command line (as the only optional operand of
the `open` command) then `$EDITOR` (which defaults to `vi`) is opened and
user is prompted for a message for the issue being opened.
If the issue message is an empty string, opening is aborted.


----


## Tagging

Issues can be tagged at the same time they are being opened.
Tags are assigned using `-t/--tag <tag>` option (it may appear multiple times).


----


## Parameters

Parameters can be set at open-time using `-p/--param` option.
