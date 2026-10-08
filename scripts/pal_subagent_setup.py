#!/usr/bin/env python3
"""Install discoverable skills for both clients and a single shared PAL checkout."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

REPO_URL = 'https://github.com/BeehiveInnovations/pal-mcp-server.git'
SKILL_NAME = 'pal-subagent'


class Paths:
    def __init__(self, home=None, codex_skills_dir=None):
        self.home = Path(home or Path.home()).resolve()
        self.codex_home = Path(os.environ.get('CODEX_HOME', self.home / '.codex')).expanduser().resolve()
        self.claude_skill = self.home / '.claude/skills' / SKILL_NAME
        # Honor this desktop's established layout; use the current portable layout for fresh installs.
        saved_skills = read_json(self.home / '.config/pal-subagent/install.json').get('skills', {})
        if codex_skills_dir:
            root = Path(codex_skills_dir).expanduser()
        elif saved_skills.get('codex'):
            root = Path(saved_skills['codex']).parent
        elif (self.codex_home / 'skills').is_dir():
            root = self.codex_home / 'skills'
        else:
            root = self.home / '.agents/skills'
        self.codex_skill = root.resolve() / SKILL_NAME
        self.codex_config = self.codex_home / 'config.toml'
        self.claude_config = self.home / '.claude.json'
        self.state = self.home / '.config/pal-subagent/install.json'


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else {}


def registrations(paths):
    codex = tomllib.loads(paths.codex_config.read_text()) if paths.codex_config.exists() else {}
    return {
        'codex': codex.get('mcp_servers', {}).get('pal'),
        'claude': read_json(paths.claude_config).get('mcpServers', {}).get('pal'),
    }


def registered_server(config):
    if not config:
        return None
    for arg in config.get('args', []):
        path = Path(arg).expanduser()
        if path.name == 'server.py' and path.is_absolute():
            return path.parent.resolve()
    raise ValueError('Existing PAL registration has no absolute server.py path; resolve it before installation.')


def make_plan(paths, source, client=None, env_name=None, server_dir=None, codex_skills_dir=None):
    state = read_json(paths.state)
    if not client:
        client = state.get('owner_client')
    if client not in ('claude', 'codex'):
        raise ValueError('Specify the initiating client with --client claude or --client codex.')
    source = Path(source).resolve()
    candidates = set()
    if state.get('server_dir'):
        candidates.add(Path(state['server_dir']).expanduser().resolve())
    for config in registrations(paths).values():
        candidate = registered_server(config)
        if candidate:
            candidates.add(candidate)
    for skill in (source, paths.claude_skill, paths.codex_skill):
        if (skill / 'pal-mcp-server/server.py').is_file():
            candidates.add((skill / 'pal-mcp-server').resolve())
    if server_dir:
        server = Path(server_dir).expanduser().resolve()
    elif len(candidates) > 1:
        raise ValueError('Conflicting PAL paths: ' + ', '.join(map(str, sorted(candidates))) +
                         '. Select the shared checkout explicitly with --server-dir.')
    elif candidates:
        server = candidates.pop()
        if not (server / 'server.py').is_file():
            raise ValueError(f'Existing PAL path is missing: {server}. Select --server-dir explicitly to repair.')
    else:
        owner = paths.claude_skill if client == 'claude' else paths.codex_skill
        server = owner / 'pal-mcp-server'
    if server.exists() and not all((server / name).is_file() for name in ('server.py', 'requirements.txt')):
        raise ValueError(f'Not a valid PAL checkout: {server}')
    for skill in (paths.claude_skill, paths.codex_skill):
        # A service can be inside a skill, but must not replace the skill root or its parent.
        if skill == server or server in skill.parents:
            raise ValueError('PAL server directory must not contain a skill root.')
    return {
        'version': 1, 'owner_client': state.get('owner_client', client),
        'server_dir': str(server), 'env_name': env_name or state.get('env_name', 'pal-mcp-server'),
        'skills': {'claude': str(paths.claude_skill), 'codex': str(paths.codex_skill)},
    }


def remove_pal_sections(text):
    """Remove PAL tables and subtables wherever they occur, preserving other tables verbatim."""
    keep = True
    result = []
    for line in text.splitlines(keepends=True):
        if re.match(r'^\s*\[', line):
            # Parse the actual TOML header, including quoted table components.
            try:
                header = tomllib.loads(line)
            except tomllib.TOMLDecodeError:
                raise ValueError('Cannot safely edit multiline/invalid TOML table header.')
            keep = not ('pal' in header.get('mcp_servers', {}))
        if keep:
            result.append(line)
    return ''.join(result).rstrip() + '\n'


def update_codex_config(text, python, server_dir, pal_path):
    server = Path(server_dir)
    section = '\n[mcp_servers.pal]\n' + '\n'.join([
        'command = ' + json.dumps(str(python)),
        'args = [' + json.dumps(str(server / 'server.py')) + ']',
        'cwd = ' + json.dumps(str(server)),
        'tool_timeout_sec = 1200',
        '\n[mcp_servers.pal.env]',
        'PATH = ' + json.dumps(pal_path),
    ]) + '\n'
    updated = remove_pal_sections(text).rstrip() + '\n' + section
    tomllib.loads(updated)
    return updated


def backup(path):
    if path.exists():
        target = path.with_name(path.name + '.backup.' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        shutil.copy2(path, target)
        print(f'Backup: {target}', flush=True)


def write_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == data:
        return
    backup(path)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name + '.')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(data)
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def packaged_files(source):
    files = [source / name for name in ('SKILL.md', 'README.md', 'README_zh.md') if (source / name).is_file()]
    if not (source / 'SKILL.md').is_file():
        raise ValueError(f'SKILL.md missing: {source}')
    for folder in ('scripts', 'references', 'agents', 'assets'):
        files.extend(path for path in (source / folder).rglob('*')
                     if path.is_file() and '__pycache__' not in path.parts
                     and '.backup.' not in path.name and path.name != '.DS_Store')
    return files


def install_skills(source, targets):
    files = packaged_files(source)
    for target in targets:
        if target.is_symlink():
            raise ValueError(f'Skill target is a symlink; choose a real directory: {target}')
        for file in files:
            destination = target / file.relative_to(source)
            if not destination.resolve().is_relative_to(target.resolve()):
                raise ValueError(f'Skill file escapes target through a symlink: {destination}')
    for target in targets:
        for file in files:
            destination = target / file.relative_to(source)
            if file.resolve() == destination.resolve():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and destination.read_bytes() == file.read_bytes():
                continue
            backup(destination)
            shutil.copy2(file, destination)
        print(f'Skill installed: {target}', flush=True)


SOURCE = Path(__file__).resolve().parents[1]


def run(args, capture=False, **kwargs):
    result = subprocess.run([str(arg) for arg in args], check=True, text=True,
                            capture_output=capture, **kwargs)
    return result.stdout.strip() if capture else None


def dependencies_ready(python, requirements):
    code = '''
import importlib.metadata as metadata
from pathlib import Path
from pip._vendor.packaging.requirements import Requirement
requirements = ['mcp>=1.28,<2'] + Path(__import__('sys').argv[1]).read_text().splitlines()
for line in requirements:
    line = line.split('#', 1)[0].strip()
    if not line:
        continue
    requirement = Requirement(line)
    if requirement.marker and not requirement.marker.evaluate():
        continue
    if metadata.version(requirement.name) not in requirement.specifier:
        raise SystemExit(1)
'''
    return subprocess.run([str(python), '-c', code, str(requirements)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def pal_path():
    extra = ['/usr/local/bin', '/usr/bin', '/bin', '/opt/homebrew/bin',
             str(Path.home() / '.local/bin'), str(Path.home() / '.cargo/bin'), str(Path.home() / 'bin')]
    for name in ('codex', 'claude'):
        binary = shutil.which(name)
        if binary:
            extra.insert(0, str(Path(binary).parent))
    return os.pathsep.join(dict.fromkeys(part for part in extra + os.environ.get('PATH', '').split(os.pathsep) if part))


def perform_install(paths, source, plan, update=False):
    clients = [name for name in ('claude', 'codex') if shutil.which(name)]
    if not clients:
        raise ValueError('Install Codex CLI or Claude Code before registering PAL.')
    if not shutil.which('conda'):
        raise ValueError('conda not found.')
    server = Path(plan['server_dir'])
    install_skills(source, [Path(path) for path in plan['skills'].values()])
    plan['skill_files'] = [str(path.relative_to(source)) for path in packaged_files(source)]
    if not server.exists():
        server.parent.mkdir(parents=True, exist_ok=True)
        run(['git', 'clone', '--depth', '1', REPO_URL, server])
    elif update:
        if not (server / '.git').exists():
            raise ValueError('--update requires a Git checkout.')
        run(['git', '-C', server, 'diff', '--exit-code'], capture=True)
        run(['git', '-C', server, 'diff', '--cached', '--exit-code'], capture=True)
        run(['git', '-C', server, 'pull', '--ff-only'])
    for name in ('server.py', 'requirements.txt'):
        if not (server / name).is_file():
            raise ValueError(f'Missing {server / name}')
    if not (server / '.env').exists():
        write_file(server / '.env', '# Placeholder local endpoint; clink uses CLI authentication.\n'
                   'CUSTOM_API_URL=http://localhost:11434/v1\nCUSTOM_API_KEY=safe-code\nCUSTOM_MODEL_NAME=llama3.2\n')
    envs = json.loads(run(['conda', 'env', 'list', '--json'], capture=True))['envs']
    if not any(Path(path).name == plan['env_name'] for path in envs):
        run(['conda', 'create', '-n', plan['env_name'], 'python=3.12', '-y'])
    python = run(['conda', 'run', '--no-capture-output', '-n', plan['env_name'],
                  'python', '-c', 'import sys; print(sys.executable)'], capture=True)
    if not Path(python).is_file():
        raise ValueError('Conda did not return a valid Python executable.')
    if update or not dependencies_ready(python, server / 'requirements.txt'):
        pip_args = [python, '-m', 'pip', 'install'] + (['--upgrade'] if update else [])
        run(pip_args + ['mcp>=1.28,<2', '-r', server / 'requirements.txt'])
    else:
        print('Existing environment already satisfies PAL dependencies; reusing it.', flush=True)
    run([python, '-m', 'pip', 'check'])
    plan['python'] = python
    plan['registered_clients'] = []
    plan['verified'] = False
    # Persist the resolved service before registration so a partial installation can be retried.
    write_file(paths.state, json.dumps(plan, indent=2) + '\n')
    path = pal_path()
    if 'claude' in clients:
        previous = read_json(paths.claude_config).get('mcpServers', {}).get('pal')
        backup(paths.claude_config)
        if previous:
            run(['claude', 'mcp', 'remove', 'pal', '-s', 'user'])
        try:
            run(['claude', 'mcp', 'add', 'pal', '-s', 'user', '-e', 'PATH=' + path,
                 '--', python, server / 'server.py'])
        except subprocess.CalledProcessError:
            current = read_json(paths.claude_config)
            if previous:
                current.setdefault('mcpServers', {})['pal'] = previous
                write_file(paths.claude_config, json.dumps(current, indent=2) + '\n')
            raise
        plan['registered_clients'].append('claude')
    if 'codex' in clients:
        old = paths.codex_config.read_text() if paths.codex_config.exists() else ''
        write_file(paths.codex_config, update_codex_config(old, python, server, path))
        plan['registered_clients'].append('codex')
    write_file(paths.state, json.dumps(plan, indent=2) + '\n')
    run([python, source / 'scripts/pal_subagent_setup.py', 'probe', '--server-dir', server],
        env={**os.environ, 'PATH': path, 'LOG_LEVEL': 'WARNING'})
    plan['verified'] = True
    write_file(paths.state, json.dumps(plan, indent=2) + '\n')
    for client in set(('claude', 'codex')) - set(clients):
        print(f'{client}: skill installed; MCP registration skipped (CLI not found).')
    print('Installation verified. Claude: /pal-subagent; Codex: $pal-subagent. Restart sessions to load MCP.', flush=True)


def validated_skill_files(plan, clients):
    files = plan.get('skill_files')
    if not files:
        raise ValueError('No managed skill file list found; reinstall before uninstalling.')
    targets = []
    for client in clients:
        if client not in plan.get('skills', {}):
            continue
        root = Path(plan['skills'][client]).resolve()
        for name in files:
            relative = Path(name)
            target = root / relative
            managed = relative.parts and (relative.parts[0] in ('scripts', 'references', 'agents', 'assets')
                       or str(relative) in ('SKILL.md', 'README.md', 'README_zh.md'))
            if not managed or relative.is_absolute() or '..' in relative.parts or not target.resolve().is_relative_to(root):
                raise ValueError('Invalid managed skill path; refusing to remove files.')
            targets.append((client, root, target))
    return targets


def check_server_removal(paths, plan, clients):
    server = Path(plan['server_dir']).resolve()
    if server.name != 'pal-mcp-server' or not all((server / f).is_file() for f in ('server.py', 'requirements.txt')):
        raise ValueError('Refusing automatic removal: expected a valid directory named pal-mcp-server.')
    for client, config in registrations(paths).items():
        if config and client not in clients:
            raise ValueError(f'{client} still has a PAL registration; remove both clients before deleting the service.')
    for client, directory in plan.get('skills', {}).items():
        if client not in clients and (Path(directory) / 'SKILL.md').is_file():
            raise ValueError(f'{client} skill still uses the shared PAL service.')


def uninstall_clients(paths, plan, clients):
    targets = validated_skill_files(plan, clients)
    configs = registrations(paths)
    for client in clients:
        config = configs[client]
        if config and registered_server(config) != Path(plan['server_dir']).resolve():
            raise ValueError(f'{client} PAL configuration changed; refusing to remove another service.')
    if 'claude' in clients and configs['claude']:
        data = read_json(paths.claude_config)
        del data['mcpServers']['pal']
        write_file(paths.claude_config, json.dumps(data, indent=2) + '\n')
    if 'codex' in clients and configs['codex']:
        write_file(paths.codex_config, remove_pal_sections(paths.codex_config.read_text()))
    saved = paths.state.parent / 'backups' / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    for client, root, target in targets:
        if target.is_file():
            destination = saved / client / target.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)
            target.unlink()
    # Keep runtime, user-created files and file backups even when the service lives under this skill.
    for client in clients:
        plan.get('skills', {}).pop(client, None)
    plan['registered_clients'] = [name for name in plan.get('registered_clients', []) if name not in clients]
    write_file(paths.state, json.dumps(plan, indent=2) + '\n')
    print(f'Removed selected skills/MCP registrations. Skill file backup: {saved}. Conda environment retained.')


def probe(server):
    import asyncio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def check():
        params = StdioServerParameters(command=sys.executable, args=[str(server / 'server.py')],
                                       cwd=str(server), env=dict(os.environ))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                if 'clink' not in {tool.name for tool in tools.tools}:
                    raise ValueError('MCP connected but clink is missing.')
                print('PASS: MCP handshake and clink discovery.', flush=True)
    asyncio.run(asyncio.wait_for(check(), timeout=45))


def confirm(yes):
    if yes:
        return
    if not sys.stdin.isatty():
        raise ValueError('Review --dry-run and obtain user authorization, then pass --yes for noninteractive execution.')
    if input('Apply this plan? [y/N]: ').strip().lower() not in ('y', 'yes'):
        raise ValueError('Cancelled; no changes made.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'uninstall', 'probe'])
    parser.add_argument('--client', choices=['claude', 'codex', 'both'], help='Initiating client, or uninstall target')
    parser.add_argument('--env-name', help='Conda environment to reuse/create (default: saved environment or pal-mcp-server)')
    parser.add_argument('--server-dir', help='Single shared PAL checkout; defaults to existing checkout or initiating skill directory')
    parser.add_argument('--codex-skills-dir', help='Override Codex skills directory')
    parser.add_argument('--yes', action='store_true', help='Apply the plan after prior user authorization')
    parser.add_argument('--dry-run', action='store_true', help='Print plan without changing files')
    parser.add_argument('--update', action='store_true', help='Explicitly update PAL source and dependencies')
    parser.add_argument('--remove-server', action='store_true', help='Uninstall: explicitly remove unreferenced shared checkout')
    args = parser.parse_args(argv)
    if args.action == 'probe':
        if not args.server_dir:
            raise ValueError('probe requires --server-dir')
        probe(Path(args.server_dir).resolve())
        return
    if args.action == 'install' and args.remove_server:
        raise ValueError('--remove-server is only for uninstall.')
    paths = Paths(codex_skills_dir=args.codex_skills_dir)
    if args.action == 'install':
        client = args.client
        if not client and not read_json(paths.state).get('owner_client') and sys.stdin.isatty():
            client = input('Initiating client [claude/codex]: ').strip().lower()
        plan = make_plan(paths, SOURCE, client, args.env_name, args.server_dir, args.codex_skills_dir)
        print(json.dumps(plan, indent=2), flush=True)
        print('Both skills will be installed. Existing conda environment will be reused; otherwise Python 3.12 will be created.\n'
              'PAL source updates: ' + ('enabled' if args.update else 'disabled; reuse existing checkout'), flush=True)
        if args.dry_run:
            return
        confirm(args.yes)
        perform_install(paths, SOURCE, plan, args.update)
    else:
        if args.env_name or args.server_dir or args.update or args.codex_skills_dir:
            raise ValueError('Uninstall uses saved installation paths; install/update options are not accepted.')
        plan = read_json(paths.state)
        if not plan:
            raise ValueError('No installation record; run install first to adopt the existing setup.')
        client = args.client
        if not client and sys.stdin.isatty():
            client = input('Uninstall client [claude/codex/both]: ').strip().lower()
        if client not in ('claude', 'codex', 'both'):
            raise ValueError('Select --client claude, codex or both for uninstall.')
        clients = ['claude', 'codex'] if client == 'both' else [client]
        validated_skill_files(plan, clients)
        if args.remove_server:
            check_server_removal(paths, plan, clients)
        print(json.dumps({'remove_clients': clients, 'remove_server': args.remove_server,
                          'server_dir': plan['server_dir'], 'retain_conda': plan['env_name']}, indent=2), flush=True)
        if args.dry_run:
            return
        confirm(args.yes)
        uninstall_clients(paths, plan, clients)
        if args.remove_server:
            server = Path(plan['server_dir'])
            shutil.rmtree(server)
            paths.state.unlink()
            print(f'Removed shared PAL checkout: {server}. Conda environment retained.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, TimeoutError) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
