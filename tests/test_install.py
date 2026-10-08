import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import tomllib
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'pal_subagent_setup.py'


class InstallationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('setup', SCRIPT)
        cls.setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.setup)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.source = self.home / 'source'
        (self.source / 'scripts').mkdir(parents=True)
        (self.source / 'SKILL.md').write_text('---\nname: pal-subagent\ndescription: test\n---\n')
        (self.source / 'scripts' / 'test.sh').write_text('test')
        self.paths = self.setup.Paths(self.home)

    def server(self, path):
        path.mkdir(parents=True, exist_ok=True)
        (path / 'server.py').write_text('')
        (path / 'requirements.txt').write_text('')
        return path

    def plan(self, **kwargs):
        options = dict(client='claude', env_name=None, server_dir=None,
                       codex_skills_dir=None)
        options.update(kwargs)
        return self.setup.make_plan(self.paths, self.source, **options)

    def test_fresh_install_defaults_to_initiating_skill_directory(self):
        plan = self.plan()
        self.assertEqual(plan['server_dir'], str(self.paths.claude_skill / 'pal-mcp-server'))
        self.assertEqual(self.plan(client='codex')['server_dir'], str(self.paths.codex_skill / 'pal-mcp-server'))

    def test_existing_source_server_is_reused(self):
        server = self.server(self.source / 'pal-mcp-server')
        self.assertEqual(self.plan()['server_dir'], str(server))

    def test_both_clients_reuse_registered_server(self):
        server = self.server(self.home / 'existing server')
        self.paths.codex_config.parent.mkdir()
        self.paths.codex_config.write_text('[mcp_servers.pal]\ncommand="python"\nargs=[' + json.dumps(str(server / 'server.py')) + ']\n')
        self.assertEqual(self.plan()['server_dir'], str(server))
        self.assertEqual(self.plan(client='codex')['server_dir'], str(server))

    def test_conflicting_registrations_require_explicit_selection(self):
        first = self.server(self.home / 'one')
        second = self.server(self.home / 'two')
        self.paths.codex_config.parent.mkdir()
        self.paths.codex_config.write_text('[mcp_servers.pal]\ncommand="python"\nargs=[' + json.dumps(str(first / 'server.py')) + ']\n')
        self.paths.claude_config.write_text(json.dumps({'mcpServers': {'pal': {'args': [str(second / 'server.py')]}}}))
        with self.assertRaisesRegex(ValueError, 'server-dir'):
            self.plan()
        self.assertEqual(self.plan(server_dir=str(first))['server_dir'], str(first))

    def test_manifest_reuses_environment_and_service(self):
        server = self.server(self.home / 'shared')
        self.paths.state.parent.mkdir(parents=True)
        self.paths.state.write_text(json.dumps({'server_dir': str(server), 'env_name': 'existing-pal'}))
        self.assertEqual(self.plan()['env_name'], 'existing-pal')
        self.assertEqual(self.plan()['server_dir'], str(server))

    def test_skill_copy_excludes_runtime_and_preserves_existing_runtime(self):
        self.server(self.source / 'pal-mcp-server')
        (self.source / '.env').write_text('secret')
        self.setup.install_skills(self.source, [self.paths.claude_skill, self.paths.codex_skill])
        for target in [self.paths.claude_skill, self.paths.codex_skill]:
            self.assertTrue((target / 'SKILL.md').is_file())
            self.assertFalse((target / 'pal-mcp-server').exists())
            self.assertFalse((target / '.env').exists())
        self.server(self.paths.claude_skill / 'pal-mcp-server')
        self.setup.install_skills(self.source, [self.paths.claude_skill, self.paths.codex_skill])
        self.assertTrue((self.paths.claude_skill / 'pal-mcp-server/server.py').is_file())

    def test_config_update_is_idempotent_and_preserves_unrelated_sections(self):
        original = '[mcp_servers.pal]\ncommand="old"\n[mcp_servers.pal.env]\nPATH="old"\n[mcp_servers.other]\ncommand="keep"\n[model_providers.custom]\nname="Keep"\n'
        updated = self.setup.update_codex_config(original, '/some "quoted"/python', '/server folder', '/bin')
        parsed = tomllib.loads(updated)
        self.assertEqual(parsed['mcp_servers']['other']['command'], 'keep')
        self.assertEqual(parsed['model_providers']['custom']['name'], 'Keep')
        self.assertEqual(parsed['mcp_servers']['pal']['command'], '/some "quoted"/python')
        self.assertEqual(updated, self.setup.update_codex_config(updated, '/some "quoted"/python', '/server folder', '/bin'))
        removed = tomllib.loads(self.setup.remove_pal_sections(updated))
        self.assertNotIn('pal', removed['mcp_servers'])
        self.assertIn('other', removed['mcp_servers'])


    def install_record(self):
        server = self.server(self.home / 'pal-mcp-server')
        plan = self.plan(server_dir=str(server))
        plan['python'] = '/existing/python'
        plan['skill_files'] = ['SKILL.md', 'scripts/test.sh']
        self.setup.install_skills(self.source, [self.paths.claude_skill, self.paths.codex_skill])
        self.paths.state.parent.mkdir(parents=True)
        self.paths.state.write_text(json.dumps(plan))
        self.paths.codex_config.parent.mkdir(exist_ok=True)
        self.paths.codex_config.write_text(self.setup.update_codex_config('', plan['python'], server, '/bin'))
        self.paths.claude_config.write_text(json.dumps({'mcpServers': {'pal': {'command': plan['python'], 'args': [str(server / 'server.py')]}}}))
        return plan, server

    def test_single_client_uninstall_keeps_shared_service_and_other_client(self):
        plan, server = self.install_record()
        self.setup.uninstall_clients(self.paths, plan, ['claude'])
        self.assertFalse((self.paths.claude_skill / 'SKILL.md').exists())
        self.assertTrue((self.paths.codex_skill / 'SKILL.md').is_file())
        self.assertTrue((server / 'server.py').is_file())
        self.assertNotIn('pal', json.loads(self.paths.claude_config.read_text())['mcpServers'])
        self.assertIn('pal', tomllib.loads(self.paths.codex_config.read_text())['mcp_servers'])

    def test_shared_server_deletion_is_blocked_while_any_client_uses_it(self):
        plan, server = self.install_record()
        with self.assertRaisesRegex(ValueError, 'still'):
            self.setup.check_server_removal(self.paths, plan, ['claude'])
        self.assertTrue((server / 'server.py').is_file())
        self.setup.check_server_removal(self.paths, plan, ['claude', 'codex'])

    def test_uninstall_cannot_remove_paths_outside_skill_from_manifest(self):
        plan, server = self.install_record()
        plan['skill_files'].append('../outside.txt')
        outside = self.paths.claude_skill.parent / 'outside.txt'
        outside.write_text('keep')
        with self.assertRaises(ValueError):
            self.setup.uninstall_clients(self.paths, plan, ['claude'])
        self.assertEqual(outside.read_text(), 'keep')
        self.assertIn('pal', json.loads(self.paths.claude_config.read_text())['mcpServers'])

    def test_install_dry_run_does_not_mutate(self):
        with patch.object(self.setup, 'Paths', return_value=self.paths), patch.object(self.setup, 'SOURCE', self.source):
            self.setup.main(['install', '--client', 'claude', '--dry-run'])
        self.assertFalse(self.paths.state.exists())
        self.assertFalse(self.paths.claude_skill.exists())

    def test_noninteractive_install_needs_explicit_approval(self):
        with patch.object(self.setup, 'Paths', return_value=self.paths), patch.object(self.setup, 'SOURCE', self.source), patch('sys.stdin.isatty', return_value=False):
            with self.assertRaisesRegex(ValueError, '--yes'):
                self.setup.main(['install', '--client', 'claude'])
        self.assertFalse(self.paths.claude_skill.exists())

    def test_uninstall_keeps_runtime_inside_removed_skill(self):
        plan, old = self.install_record()
        server = self.server(self.paths.claude_skill / 'pal-mcp-server')
        plan['server_dir'] = str(server)
        self.paths.claude_config.write_text(json.dumps({'mcpServers': {'pal': {'args': [str(server / 'server.py')]}}}))
        self.setup.uninstall_clients(self.paths, plan, ['claude'])
        self.assertTrue((server / 'server.py').is_file())
        self.assertFalse((self.paths.claude_skill / 'SKILL.md').exists())


    def test_full_install_then_other_client_reinstall_shares_one_service(self):
        def external(args, capture=False, **kwargs):
            args = list(map(str, args))
            if args[:3] == ['conda', 'env', 'list']:
                return json.dumps({'envs': [str(self.home / 'envs/pal-mcp-server')]})
            if args[:2] == ['conda', 'run']:
                return sys.executable
            if args[:2] == ['git', 'clone']:
                self.server(Path(args[-1]))
            if args[:3] == ['claude', 'mcp', 'add']:
                data = json.loads(self.paths.claude_config.read_text()) if self.paths.claude_config.exists() else {'other': 'keep'}
                separator = args.index('--')
                data.setdefault('mcpServers', {})['pal'] = {'command': args[separator + 1], 'args': [args[separator + 2]], 'env': {'PATH': args[args.index('-e') + 1].split('=', 1)[1]}}
                self.paths.claude_config.write_text(json.dumps(data))
            if args[:3] == ['claude', 'mcp', 'remove']:
                data = json.loads(self.paths.claude_config.read_text())
                data['mcpServers'].pop('pal', None)
                self.paths.claude_config.write_text(json.dumps(data))
        with patch.object(self.setup, 'run', side_effect=external), patch.object(self.setup, 'dependencies_ready', return_value=True), patch.object(self.setup.shutil, 'which', side_effect=lambda name: '/bin/' + name):
            first = self.plan()
            self.setup.perform_install(self.paths, self.source, first)
            second = self.plan(client='codex')
            self.setup.perform_install(self.paths, self.source, second)
        state = json.loads(self.paths.state.read_text())
        self.assertTrue(state['verified'])
        self.assertEqual(state['server_dir'], first['server_dir'])
        self.assertEqual(list(self.home.rglob('server.py')), [Path(first['server_dir']) / 'server.py'])
        for target in state['skills'].values():
            self.assertTrue((Path(target) / 'SKILL.md').is_file())
        claude = json.loads(self.paths.claude_config.read_text())
        codex = tomllib.loads(self.paths.codex_config.read_text())
        self.assertEqual(claude['other'], 'keep')
        self.assertEqual(claude['mcpServers']['pal']['args'], codex['mcp_servers']['pal']['args'])
        self.assertEqual(claude['mcpServers']['pal']['command'], codex['mcp_servers']['pal']['command'])

    def test_copy_preflights_both_targets_before_writing(self):
        outside = self.home / 'outside'
        outside.mkdir()
        self.paths.codex_skill.mkdir(parents=True)
        (self.paths.codex_skill / 'scripts').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.setup.install_skills(self.source, [self.paths.claude_skill, self.paths.codex_skill])
        self.assertFalse(self.paths.claude_skill.exists())
        self.assertFalse((outside / 'test.sh').exists())

    def test_custom_codex_skill_path_is_preserved_on_reinstall(self):
        custom = self.home / 'custom-skills/pal-subagent'
        self.paths.state.parent.mkdir(parents=True)
        self.paths.state.write_text(json.dumps({'skills': {'codex': str(custom)}}))
        self.assertEqual(self.setup.Paths(self.home).codex_skill, custom)


if __name__ == '__main__':
    unittest.main()
