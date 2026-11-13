"""Build-time command help; the executable reads the generated catalog directly."""
import json
from .command_catalog import PURPOSES


def types(schema):
    found = {schema['type']} if 'type' in schema else set()
    for branch in schema.get('anyOf', []):
        found.update(types(branch))
    return found


def root_help(application):
    return {
        **{key: application[key] for key in ('application', 'version', 'public_api_version')},
        'usage': 'PixForgeNative.exe serve [--workspace DIR --runtime DIR] | GROUP ACTION [OPTIONS]', 'groups': PURPOSES,
        'options': {
            '--workspace DIR': 'Project workspace; defaults to the current directory.',
            '--runtime DIR': 'Reuse this workspace session; defaults to WORKSPACE/.runtime/pixelforge-desktop.',
            '--request-file FILE': 'UTF-8 JSON parameter object; use - for standard input.',
            '--request-json JSON': 'Inline JSON parameter object.',
            '--result-file FILE': 'Also save the JSON response to a new file.',
            '--json': 'Machine-readable help/version. Execution always returns JSON.',
            '--help': 'Show only this level of help; does not start a session.',
            '--version': 'Show software/command contract version; does not start a session.',
        },
        'discovery': 'Start serve once; read RUNTIME/commands.json. GET /v1/commands[/GROUP[/ACTION]] for help; POST {group,command,params} to /v1/commands. CLI help: GROUP [ACTION] --help.',
        'input': 'Flags use kebab-case. Every parameter has --NAME-file; strings read UTF-8 text, other values read JSON.',
        'desktop': 'Run without a command to open the workbench. Commands reuse its project and history.',
        'exit_codes': {'0': 'success', '1': 'operation or constraint failure', '2': 'invalid command/input',
                       '3': 'document/revision conflict', '4': 'output already exists', '5': 'busy/timeout',
                       '6': 'approval or stale export evidence', '7': 'session/window unavailable'},
    }


def print_help(data, machine):
    if machine:
        print(json.dumps(data, ensure_ascii=False))
        return
    if 'params_schema' in data:
        print(data['usage'] + '\n\n' + data['description'] + '\n')
        schema = data['params_schema']
        for key, spec in schema['properties'].items():
            flag = '--' + key.replace('_', '-')
            kind = '/'.join(sorted(types(spec))) or 'JSON'
            status = 'required' if key in schema.get('required', []) else 'default=' + json.dumps(spec.get('default'), ensure_ascii=False)
            print('  ' + flag.ljust(26) + kind + '; ' + status)
        print('\n--NAME-file reads UTF-8 text for string parameters, JSON for other types.')
        print('--request-file FILE (or - for stdin) reads a parameter object; keys use snake_case.')
        print('--workspace DIR / --runtime DIR select the shared session; --json shows the exact parameter schema.')
    elif 'actions' in data:
        print(data['usage'] + '\n')
        for action, description in data['actions'].items():
            print('  ' + action.ljust(24) + description)
    else:
        print('PixForge ' + data['version'] + ' — desktop and commands in one executable\n\n' + data['usage'] + '\n')
        for group, description in data['groups'].items():
            print('  ' + group.ljust(16) + description)
        print('\n' + data['discovery'] + '\n')
        for flag, description in data['options'].items():
            print('  ' + flag + '\n      ' + description)
        print('\n' + data['input'] + '\n' + data['desktop'])


