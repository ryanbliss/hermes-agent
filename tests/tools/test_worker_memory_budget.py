"""Heavy cron builds can raise their memory budget without losing host bounds."""
from pathlib import Path

import pytest

from hermes_cli.config import atomic_config_write
from hermes_constants import set_hermes_home_override, reset_hermes_home_override
from tools import process_registry as pr


@pytest.fixture
def host_memory(monkeypatch):
    original = Path.read_text
    def read(path, *args, **kwargs):
        if str(path) == '/proc/self/cgroup':
            return '0::/test-worker'
        if str(path) == '/sys/fs/cgroup/test-worker/memory.max':
            return str(6 * 1024**3)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr(pr.os, 'sysconf', lambda key: 4096 if key == 'SC_PAGE_SIZE' else 32 * 1024**3 // 4096)
    monkeypatch.delenv('TERMINAL_LOCAL_MEMORY_MAX_MB', raising=False)


@pytest.mark.parametrize('configured,expected_mb', [(8192, 6144), (2048, 2048), ('bad', 4096), (0, 4096)])
def test_real_config_sets_scope_budget_with_host_bounds(tmp_path, monkeypatch, host_memory, configured, expected_mb):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    atomic_config_write(tmp_path / 'config.yaml', {'terminal': {'worker_memory_max_mb': configured}})
    argv = pr._systemd_scope_argv('systemd-run', 'budget-test', 'true')
    assert f'MemoryMax={expected_mb * 1024**2}' in argv


def test_memory_budget_follows_profile_scope_not_launch_home(tmp_path, monkeypatch, host_memory):
    homes = [tmp_path / 'a', tmp_path / 'b']
    for home, budget in zip(homes, [2048, 8192]):
        home.mkdir()
        atomic_config_write(home / 'config.yaml', {'terminal': {'worker_memory_max_mb': budget}})
    monkeypatch.setenv('HERMES_HOME', str(homes[0]))
    for home, expected in [(homes[0], 2048), (homes[1], 6144), (homes[0], 2048)]:
        token = set_hermes_home_override(home)
        try:
            assert pr._worker_memory_max_bytes() == expected * 1024**2
        finally:
            reset_hermes_home_override(token)
