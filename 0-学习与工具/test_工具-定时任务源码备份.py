"""工具-定时任务源码备份.py 单测（队列 #169）。

覆盖三条红线：① 凭据扫描 fail-closed（命中即拒绝写入，不静默入库，不影响
其余任务）；② 方向单向（只读真身、只写镜像，反向路径结构上不存在）；
③ 白名单以外的任务即便真身存在也绝不被回镜。
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-定时任务源码备份.py")

_spec = importlib.util.spec_from_file_location("scheduled_task_backup", SCRIPT)
backup = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = backup  # dataclass 在 Python 3.14 下需要能在 sys.modules 解析到所属模块
_spec.loader.exec_module(backup)


def _write_task(source_dir: Path, task_id: str, content: str) -> None:
    task_dir = source_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "SKILL.md").write_text(content, encoding="utf-8")


class CredentialScanTests(unittest.TestCase):
    """凭据扫描本身的判据——不涉及文件系统。"""

    def test_clean_content_no_hits(self):
        content = "这是一份正常的巡检 prompt，读队列文件，检查 §四 状态列。"
        self.assertEqual(backup.scan_for_credentials(content), [])

    def test_webhook_url_with_key_blocked(self):
        content = "推送地址：https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abcd1234-real-secret"
        hits = backup.scan_for_credentials(content)
        self.assertTrue(hits)

    def test_benign_github_url_not_blocked(self):
        content = "查 https://github.com/obra/superpowers/releases 最新 release。"
        self.assertEqual(backup.scan_for_credentials(content), [])

    def test_api_key_literal_value_blocked(self):
        content = 'SCRAPECREATORS_API_KEY: "sk-real-looking-1234567890abcdef"'
        self.assertTrue(backup.scan_for_credentials(content))

    def test_zp_gate_password_blocked(self):
        content = "ZP_GATE_PASSWORD=hunter2plaintext"
        self.assertTrue(backup.scan_for_credentials(content))

    def test_sa_account_password_blocked(self):
        content = "sa 账号口令: Sup3rSecret!"
        self.assertTrue(backup.scan_for_credentials(content))

    def test_word_token_in_prose_not_blocked(self):
        """README 记录的既知误报场景之一：正文提到"token"一词但无实值。"""
        content = "prompt/口令放代码块，token 在这里只是名词，不代表有实际取值。"
        self.assertEqual(backup.scan_for_credentials(content), [])

    def test_long_task_name_slug_not_blocked(self):
        """README 记录的既知误报场景之二：长任务名 slug 不应被当成随机串密钥。"""
        content = "任务 ID：openspec-config-proposal-rules-f452d3-worktree-slug-name-example"
        self.assertEqual(backup.scan_for_credentials(content), [])

    def test_git_sha_not_mistaken_for_long_secret(self):
        """40 位十六进制 git commit SHA 是本项目 prompt 里的高频合法内容，
        不应被"长随机串"模式误伤（该模式阈值定在 64，高于 SHA 的 40）。"""
        content = "commit `e912434aa1b2c3d4e5f60718293a4b5c6d7e8f90` 已归档"
        self.assertEqual(backup.scan_for_credentials(content), [])


class MirrorOneTaskTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.source_dir = base / "Scheduled"
        self.mirror_dir = base / "定时任务源码"
        self.source_dir.mkdir()
        self.mirror_dir.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_source_reported_not_crashed(self):
        result = backup.mirror_one_task(self.source_dir, self.mirror_dir, "ghost-task")
        self.assertEqual(result.status, "missing_source")
        self.assertFalse((self.mirror_dir / "ghost-task.SKILL.md").exists())

    def test_first_time_mirror_creates_file(self):
        _write_task(self.source_dir, "huijian-chaijian-patrol", "prompt 内容 v1\n")
        result = backup.mirror_one_task(self.source_dir, self.mirror_dir, "huijian-chaijian-patrol")
        self.assertEqual(result.status, "updated")
        mirrored = self.mirror_dir / "huijian-chaijian-patrol.SKILL.md"
        self.assertTrue(mirrored.exists())
        self.assertEqual(mirrored.read_text(encoding="utf-8"), "prompt 内容 v1\n")

    def test_unchanged_when_hash_matches(self):
        _write_task(self.source_dir, "weekly-status-update", "内容不变\n")
        backup.mirror_one_task(self.source_dir, self.mirror_dir, "weekly-status-update")
        result = backup.mirror_one_task(self.source_dir, self.mirror_dir, "weekly-status-update")
        self.assertEqual(result.status, "unchanged")

    def test_updated_when_real_changed(self):
        _write_task(self.source_dir, "weekly-status-update", "v1\n")
        backup.mirror_one_task(self.source_dir, self.mirror_dir, "weekly-status-update")
        _write_task(self.source_dir, "weekly-status-update", "v2 已改\n")
        result = backup.mirror_one_task(self.source_dir, self.mirror_dir, "weekly-status-update")
        self.assertEqual(result.status, "updated")
        mirrored = self.mirror_dir / "weekly-status-update.SKILL.md"
        self.assertEqual(mirrored.read_text(encoding="utf-8"), "v2 已改\n")

    def test_line_ending_only_difference_is_unchanged_not_false_positive(self):
        """队列 #188 判据：不得用裸字节哈希比对（换行符差异会造成"内容完全一致但
        字节数不同"的假阳性，2026-07-31 实测两份内容逐字一致但字节数差 1055）。
        `Path.read_text()` 走 Python 通用换行符转换，`\\r\\n`/`\\r` 均归一化为 `\\n`
        再计算哈希，本测试验证真身用 CRLF、镜像用 LF 写入同一段文字时仍判 unchanged。"""
        task_dir = self.source_dir / "weekly-status-update"
        task_dir.mkdir(parents=True, exist_ok=True)
        # 真身用 CRLF 换行（模拟 Windows 编辑器保存），原始字节含 \r\n
        (task_dir / "SKILL.md").write_bytes("第一行\r\n第二行\r\n第三行\r\n".encode("utf-8"))
        # 镜像已存在且内容逐字相同，但用 LF 换行写入（原始字节不同、规范化后文本相同）
        self.mirror_dir.mkdir(parents=True, exist_ok=True)
        (self.mirror_dir / "weekly-status-update.SKILL.md").write_bytes(
            "第一行\n第二行\n第三行\n".encode("utf-8")
        )

        result = backup.mirror_one_task(self.source_dir, self.mirror_dir, "weekly-status-update")

        self.assertEqual(result.status, "unchanged")

    def test_credential_hit_blocks_write_fail_closed(self):
        _write_task(
            self.source_dir, "check-skill-plugin-updates",
            "webhook: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=REAL-SECRET-VALUE\n",
        )
        result = backup.mirror_one_task(self.source_dir, self.mirror_dir, "check-skill-plugin-updates")
        self.assertEqual(result.status, "credential_blocked")
        mirror_path = self.mirror_dir / "check-skill-plugin-updates.SKILL.md"
        self.assertFalse(mirror_path.exists(), "凭据命中时绝不能落盘镜像文件")

    def test_credential_hit_does_not_overwrite_prior_clean_mirror(self):
        """先有一份干净镜像，真身之后被改出凭据——不得用带凭据的新内容覆盖旧镜像。"""
        _write_task(self.source_dir, "weekly-status-update", "干净版本\n")
        backup.mirror_one_task(self.source_dir, self.mirror_dir, "weekly-status-update")
        _write_task(self.source_dir, "weekly-status-update", "ZP_GATE_PASSWORD=leaked123\n")
        result = backup.mirror_one_task(self.source_dir, self.mirror_dir, "weekly-status-update")
        self.assertEqual(result.status, "credential_blocked")
        mirror_path = self.mirror_dir / "weekly-status-update.SKILL.md"
        self.assertEqual(mirror_path.read_text(encoding="utf-8"), "干净版本\n")


class RunBackupWhitelistTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.source_dir = base / "Scheduled"
        self.mirror_dir = base / "定时任务源码"
        self.source_dir.mkdir()
        self.mirror_dir.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_non_whitelisted_task_never_mirrored_even_if_present(self):
        """白名单外任务（如 Paul 个人投资类扫描）即便真身存在也绝不回镜——
        README「不镜的」清单是硬边界，不做自动发现全部任务。"""
        _write_task(self.source_dir, "sanhuan-300408-weekly-scan", "个人投资类内容\n")
        _write_task(self.source_dir, "huijian-chaijian-patrol", "项目机制内容\n")
        backup.run_backup(self.source_dir, self.mirror_dir)
        self.assertFalse((self.mirror_dir / "sanhuan-300408-weekly-scan.SKILL.md").exists())
        self.assertTrue((self.mirror_dir / "huijian-chaijian-patrol.SKILL.md").exists())

    def test_run_backup_covers_exactly_the_declared_whitelist(self):
        results = backup.run_backup(self.source_dir, self.mirror_dir)
        self.assertEqual({r.task_id for r in results}, set(backup.WHITELIST))

    def test_default_whitelist_matches_readme_declared_scope(self):
        """白名单硬编码需与 README.md「镜像范围」表保持一致——三份、且仅三份。"""
        self.assertEqual(
            set(backup.WHITELIST),
            {"huijian-chaijian-patrol", "weekly-status-update", "check-skill-plugin-updates"},
        )


class DirectionIsOneWayTests(unittest.TestCase):
    """结构性验证：脚本模块不含任何从镜像目录读取后写回真身目录的代码路径。"""

    def test_module_source_never_writes_into_source_dir_variable(self):
        source_text = SCRIPT.read_text(encoding="utf-8")
        # 唯一允许的写操作目标是 mirror_path / mirror_dir，不应出现对 source_dir 的 write_text 调用
        self.assertNotIn("source_dir", self._extract_write_text_targets(source_text))

    @staticmethod
    def _extract_write_text_targets(source_text: str) -> str:
        import re

        return "".join(re.findall(r"\n\s*([A-Za-z_][A-Za-z0-9_.]*)\.write_text\(", source_text))


if __name__ == "__main__":
    unittest.main()
