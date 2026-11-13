"""Generate immutable, on-demand help consumed directly by the native executable."""
import argparse
import contextlib
import io
import json
from pathlib import Path

from pixelforge.command_catalog import CATALOG
from pixelforge.command_help import root_help, print_help
from pixelforge.commands import build_commands


def entry(value):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        print_help(value, False)
    return {'json': value, 'human': output.getvalue()}


def write(path):
    application = json.loads((Path(__file__).resolve().parents[1] / 'public-api.json').read_bytes())
    commands = build_commands(None)
    groups = {}
    for group, actions in CATALOG.items():
        summary = {'usage': 'PixForgeNative.exe ' + group + ' ACTION [OPTIONS]',
                   'actions': {action: commands['describe'](name).split('\n')[0] for action, name in actions.items()}}
        groups[group] = {'help': entry(summary), 'actions': {}}
        for action, name in actions.items():
            data = {'usage': 'PixForgeNative.exe ' + group + ' ' + action + ' [OPTIONS]',
                    'description': commands['describe'](name), 'params_schema': commands['models'][name].model_json_schema()}
            groups[group]['actions'][action] = entry(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'schema': 'pixforge.command-help/v4', 'overview': entry(root_help(application)), 'groups': groups},
                              ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    write(parser.parse_args().output)
