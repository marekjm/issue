import json
import os
import tomllib

#
# Path "constants" for use with other code.
#


def global_path():
    return os.path.expanduser("~/.config/issue/config.toml")


def local_path():
    return ".issue/config.toml"


def system_path():
    return "/etc/issue/config.toml"


#
# By default load the full configuration ie, as it normally needs to be used by
# the program.
#
# If an explicit path is given only load that file.
# This is useful mostly when editing configuration.
#
_loaded = None


def load(path: str = None, cache: bool = True) -> dict:
    paths_to_consider = (
        system_path(),
        global_path(),
        local_path(),
    )
    if path is not None:
        paths_to_consider = (path,)

    partial_configs = []
    for p in paths_to_consider:
        if os.path.isfile(p):
            with open(p, "rb") as fd:
                partial_configs.append(tomllib.load(fd))

    config = {}
    for p in partial_configs:
        config.update(p)

    # Cache loaded config.
    global _loaded
    _loaded = config

    return config


#
# Extract values from the configuration.
# Since the configuration is sectioned eg, author data is stored in the "author"
# section:
#
#   [author]
#       name = "John Doe"
#       email = "john.doe@example.com"
#
# the access to an author's email would be specified like this:
#
#   get(key="email", section=("author",))
#
# By default the complete configuration is searched; use the `path' parameter to
# set the file to be searched.
#
def get_from(*, key: str, section: tuple[str], config: dict):
    tmp = config
    for s in section:
        tmp = tmp.get(s)
        if tmp is None:
            return None
    return tmp.get(key)


def get(key: str, section: tuple[str], *, path: str = None):
    global _loaded
    if _loaded is None:
        load()
    return get_from(key=key, section=section, config=_loaded)


def get_non_cached(key: str, section: tuple[str], *, path: str = None):
    return get_from(key=key, section=section, config=load(path=path, cache=False))


# Special-cased getters for the crucial values used by the program.
def get_editor():
    global _loaded
    if _loaded is None:
        load()
    return get(key="editor", section=("core",)) or os.environ.get("EDITOR", "vi")


def get_author_email():
    global _loaded
    if _loaded is None:
        load()
    return get(key="email", section=("author",))


def get_author_name():
    global _loaded
    if _loaded is None:
        load()
    return get(key="name", section=("author",))
