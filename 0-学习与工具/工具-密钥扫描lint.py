"""仓库凭据扫描（队列 #309 步骤 2④，CI 基线）。

只做两件事，均只读、零外部依赖（不装 gitleaks/trufflehog 等第三方工具——
本次改动无法在真实 GitHub Actions 上试跑一遍再上线，引入一个无法预先
验证行为的外部 Action 风险高于自写一个可本地验证过的小脚本）：

① `.env` 类文件不得被 git 跟踪——`.gitignore` 已声明 `.env`/`.env.*.local`/
  `.env.*`（仅 `.env.example` 白名单放行，见根 `.gitignore` 注释），本项跑
  `git ls-files` 复核这条约定在当前 checkout 里确实成立，防止某次
  `git add -f` 之类的操作意外把真实凭据文件带进历史。
② 已跟踪文本文件内容按几类已知凭据形状扫描（AWS key／私钥头／
  Anthropic·OpenAI 风格 API key／企微 webhook 真实 key 参数／通用
  `*_SECRET`/`*_KEY`/`*_TOKEN`/`*_PASSWORD` 赋值且右值不是占位符）。

范围与已知边界（如实登记，本地对存量仓库跑过一次并逐项核对零假阳性
才定稿，见下方三条设计取舍）：
- 只扫**已跟踪**文件（`git ls-files`），不扫工作区未跟踪/被忽略的内容——
  被 `.gitignore` 挡住的 `.env` 本身已经不会进 CI checkout，不需要再扫。
- 通用 `*_SECRET=`/`*_KEY=` 类启发式判据**只扫代码/配置类文件**
  （`.py`/`.ps1`/`.psm1`/`.sh`/`.js`/`.ts`/`.json`/`.yml`/`.yaml`/`.toml`/
  `.cfg`/`.ini`），不扫 `.md`/`.txt` 等叙述性文档——本仓库文档大量以
  "环境变量 `XKY_APP_KEY=<value>`"这类叙述句提及变量名，与真实赋值在
  文本形状上无法用正则可靠区分，真正危险的"硬编码真实凭据"几乎只会
  出现在代码/配置文件里的赋值语句，不会出现在说明性 prose 里。
- 通用启发式**跳过测试文件**（`test_*.py`／`*_test.py`／路径含 `/tests/`）
  ——本仓库测试用例里存在大量刻意构造的"看起来像泄漏"的假凭据字符串
  （用于测试凭据扫描类工具自身的检测逻辑，如
  `test_工具-定时任务源码备份.py`），是有意为之的测试夹具，不是真实
  泄漏；跳过的只是"启发式判据"这一层，四个结构化 `CREDENTIAL_PATTERNS`
  （AWS key／私钥头／Anthropic key／企微 webhook 真实 key）仍对测试文件
  生效，真发生泄漏（哪怕在测试文件里）依然会被抓。
- 通用启发式**要求右值是带匹配引号的字符串字面量**（而非任意非空白
  字符游程）——排除 `GATE_PASSWORD = (os.environ.get(_GATE_ENV_VAR) or
  "").strip()` 这类"右值其实是代码表达式、不是字面量"的情形；同时**排除
  右值本身形如另一个大写常量/环境变量名**（`^[A-Z][A-Z0-9_]*$`，如
  `_GATE_ENV_VAR = "ZP_GATE_PASSWORD"`／`SECRET_KEY = "WECOM_AIBOT_SECRET"`
  这类"变量存的是密钥的名字，不是密钥本身"的模式）——真实密钥值几乎
  不会恰好是一个纯大写下划线组成的合法标识符形状。
- 不做历史 commit 扫描（只查当前 checkout 那一刻的文件内容），已提交后
  又删除的历史凭据需要另外的工具（如需要，交给未来的 gitleaks 等专用
  工具补齐，不在本次范围内重新发明）。

用法：
  python 0-学习与工具/工具-密钥扫描lint.py
  # 退出码 0=通过；1=发现问题（详情打印到 stdout）
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 与根 .gitignore 的 .env 规则同口径：任何名为 .env 或 .env.* 的文件都不该
# 被跟踪，唯一豁免是 .env.example（样例文件，只列变量名不含真实值）。
ENV_FILE_RE = re.compile(r"(^|/)\.env(\.|$)")
ENV_EXAMPLE_RE = re.compile(r"(^|/)\.env\.example$")

# 占位符右值——命中即不算真实凭据，避免样例/文档误报。
PLACEHOLDER_VALUE_RE = re.compile(
    r"""^\s*(|["']?\s*["']?|xxx+|XXX+|todo|TODO|<.*>|your[-_].*|
        \.\.\.|None|null|NULL|example|EXAMPLE|CHANGE_ME|changeme|
        \$\{.*\}|%[A-Za-z_]+%)\s*$""",
    re.VERBOSE,
)

CREDENTIAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "私钥文件头",
        re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----"),
    ),
    ("Anthropic API Key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("企微 webhook 真实 key 参数", re.compile(
        r"qyapi\.weixin\.qq\.com/cgi-bin/webhook/send\?key=[0-9a-fA-F-]{20,}"
    )),
]

# 通用 "VAR_NAME = "value"" 形态——变量名含 SECRET/KEY/TOKEN/PASSWORD，右值
# 须是带匹配引号的字符串字面量（(?P=q) 反向引用保证开闭引号一致，排除
# `= os.environ.get(...)` 这类右值其实是代码表达式的情形）。刻意不含
# API_BASE/API 等宽泛后缀，避免把"变量名本身"误判为凭据（如 U9C_API_BASE
# 是主机地址，不是凭据）。
GENERIC_ASSIGNMENT_RE = re.compile(
    r"""(?P<name>[A-Z][A-Z0-9_]*(?:SECRET|_KEY|TOKEN|PASSWORD))[ \t]*[:=][ \t]*
        (?P<q>["'])(?P<value>[^"'\n]{4,})(?P=q)""",
    re.VERBOSE,
)

# 右值本身形如"另一个大写常量/环境变量名"——变量存的是密钥的名字，不是
# 密钥本身（如 SECRET_KEY = "WECOM_AIBOT_SECRET"），真实密钥值几乎不会
# 恰好是这个形状。
IDENTIFIER_LIKE_VALUE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# 通用启发式判据只对代码/配置类文件生效（见文件头部说明）；结构化
# CREDENTIAL_PATTERNS 对全部 TEXT_EXTENSIONS 生效，不受此限制。
CODE_CONFIG_EXTENSIONS = {
    ".py", ".ps1", ".psm1", ".sh", ".js", ".ts",
    ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini",
}
TEST_FILE_RE = re.compile(r"(^|/)(test_[^/]+\.py|[^/]+_test\.py)$|(^|/)tests/")


def _tracked_files(repo_root: Path) -> list[str]:
    # -c core.quotepath=false：git 默认（true）会把路径里的非 ASCII 字节
    # 八进制转义（如中文目录名），本项目路径几乎全是中文，不关掉这个开关
    # 会让 ENV_EXAMPLE_RE 等按字面 UTF-8 文本匹配的正则全部落空——本机
    # 全局 git 配置恰好已把 core.quotepath 设为 false，本地测试因此从未
    # 暴露这个问题；GitHub Actions runner 是全新 checkout、用 git 默认值，
    # 首次真实 CI 运行（gh run 31249058308）才把它暴露出来（`.env.example`
    # 被误判为需要跟踪限制之外的 .env 类文件）。理由与 `工具-落库sweep.py`
    # `_run_git`/测试文件 `_git` helper 里同款设置完全一致，不是本文件
    # 独有的新踩坑。
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files"], cwd=repo_root,
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _check_env_files_not_tracked(tracked: list[str]) -> list[str]:
    violations = []
    for path in tracked:
        if ENV_EXAMPLE_RE.search(path):
            continue
        if ENV_FILE_RE.search(path):
            violations.append(f".env 类文件被 git 跟踪（应仅 .env.example 例外）：{path}")
    return violations


def _looks_like_real_secret(name: str, value: str) -> bool:
    if PLACEHOLDER_VALUE_RE.match(value):
        return False
    if IDENTIFIER_LIKE_VALUE_RE.match(value):
        return False
    if len(value) < 8:
        return False
    return True


def _scan_file_content(repo_root: Path, rel_path: str) -> list[str]:
    full = repo_root / rel_path
    try:
        text = full.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    violations = []
    for label, pattern in CREDENTIAL_PATTERNS:
        m = pattern.search(text)
        if m:
            violations.append(f"疑似{label}：{rel_path}（命中 {m.group(0)[:24]}…）")

    is_generic_scan_target = (
        Path(rel_path).suffix.lower() in CODE_CONFIG_EXTENSIONS
        and not TEST_FILE_RE.search(rel_path)
    )
    if is_generic_scan_target:
        for m in GENERIC_ASSIGNMENT_RE.finditer(text):
            name, value = m.group("name"), m.group("value")
            if _looks_like_real_secret(name, value):
                violations.append(
                    f"疑似凭据赋值 {name}=...：{rel_path}（右值非占位符，长度 {len(value)}）"
                )
    return violations


# 扩展名白名单——只扫文本类文件，避免对二进制（docx/xlsx/pptx/图片等）
# 做无意义的 errors='ignore' 解码噪音扫描。
TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".json", ".yml", ".yaml", ".ps1", ".psm1",
    ".cfg", ".ini", ".toml", ".sh", ".js", ".ts", ".html", ".css",
}


def main() -> int:
    tracked = _tracked_files(REPO_ROOT)
    violations = _check_env_files_not_tracked(tracked)

    for rel_path in tracked:
        if Path(rel_path).suffix.lower() not in TEXT_EXTENSIONS:
            continue
        violations.extend(_scan_file_content(REPO_ROOT, rel_path))

    if not violations:
        print(f"✓ 凭据扫描通过（{len(tracked)} 个已跟踪文件，无 .env 类文件被跟踪，无疑似凭据字符串）。")
        return 0

    print(f"✗ 凭据扫描发现 {len(violations)} 处疑似问题：")
    for v in violations:
        print(f"  - {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
