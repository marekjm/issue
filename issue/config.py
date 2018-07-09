import json
import os


def getConfig():
    config_data = {}
    config_path_global = os.path.expanduser('~/.issueconfig.json')
    config_path_local = './.issue/config.json'
    if os.path.isfile(config_path_global):
        with open(config_path_global, 'r') as ifstream:
            config_data = json.loads(ifstream.read())
    if os.path.isfile(config_path_local):
        with open(config_path_local, 'r') as ifstream:
            for k, v in json.loads(ifstream.read()).items():
                config_data[k] = v
    return config_data
