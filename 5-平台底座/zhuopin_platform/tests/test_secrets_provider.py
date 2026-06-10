"""SecretsProvider 测试（P2 加固 · 先写测试）。"""
import os
import pytest
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider, SecretsProvider


class TestEnvSecretsProvider:

    def test_get_from_env(self, monkeypatch):
        """从环境变量正常读取。"""
        monkeypatch.setenv("TEST_KEY_P2", "secret_val")
        p = EnvSecretsProvider()
        assert p.get("TEST_KEY_P2") == "secret_val"

    def test_get_missing_key_raises_keyerror(self, monkeypatch):
        """key 不存在时抛 KeyError，不返回 None 或空字符串。"""
        monkeypatch.delenv("NONEXISTENT_KEY_P2", raising=False)
        p = EnvSecretsProvider()
        with pytest.raises(KeyError):
            p.get("NONEXISTENT_KEY_P2")

    def test_override_takes_priority_over_env(self, monkeypatch):
        """override dict 优先于 os.environ。"""
        monkeypatch.setenv("OVERRIDABLE_KEY", "env_val")
        p = EnvSecretsProvider(override={"OVERRIDABLE_KEY": "override_val"})
        assert p.get("OVERRIDABLE_KEY") == "override_val"

    def test_override_key_not_in_env(self):
        """override 中有但 os.environ 中没有的 key 可正常读。"""
        p = EnvSecretsProvider(override={"ONLY_IN_OVERRIDE": "x"})
        assert p.get("ONLY_IN_OVERRIDE") == "x"

    def test_satisfies_protocol(self):
        """EnvSecretsProvider 满足 SecretsProvider Protocol（runtime_checkable）。"""
        p = EnvSecretsProvider()
        assert isinstance(p, SecretsProvider)
