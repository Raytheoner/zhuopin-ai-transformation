# -*- coding: utf-8 -*-
"""写入时刻哨兵 · 一键安装脚本（OP-0829-A 补件）

等价于同目录《README-安装步骤.md》的三步：
  ① 项目 .claude/settings.json 注册 H3/H4 两哨兵（PostToolUse）
  ② 删除 ~/.claude.json 里正斜杠假信任记录（F1 根因）
  ③ 拷位并注册 #398 SessionStart 心跳钩子（全局 settings.json）

用法（Shao Peishen 本人 PowerShell）：python "C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\install-sentinels.py"
幂等：重复运行安全；每次运行前对三个配置文件各留一份时间戳备份（.bak-<时刻>）。
之所以由人运行：pretooluse-guard 按设计拦住 AI 写 .claude 配置件，不绕（见安装单）。
"""
import json
import pathlib
import shutil
import sys
import time

HOME = pathlib.Path.home()
TOOLS = pathlib.Path(r'C:\Dev\zhuopin-ai\0-学习与工具')
PROJ = pathlib.Path(r'C:\Dev\zhuopin-ai\.claude\settings.json')
GLOB = HOME / '.claude' / 'settings.json'
CJ = HOME / '.claude.json'


def main():
    ts = time.strftime('%Y%m%d-%H%M%S')
    for f in (PROJ, GLOB, CJ):
        shutil.copyfile(f, str(f) + '.bak-' + ts)

    # ③ 前置：心跳脚本拷位（目标不在 protected-paths 拦截面之外，但本脚本由人运行，不经 AI 工具链）
    src = TOOLS / '定时任务源码' / 'health-check-signal' / 'health-check-staleness.ps1'
    dst = HOME / '.claude' / 'hooks' / 'health-check-staleness.ps1'
    shutil.copyfile(src, dst)

    # ① 项目 settings.json：注册两哨兵（与安装单第 ① 步逐字等价）
    d = json.loads(PROJ.read_text(encoding='utf-8'))
    d.setdefault('hooks', {})['PostToolUse'] = [{
        'matcher': 'Edit|Write',
        'hooks': [
            {'type': 'command',
             'command': f'pwsh -NoProfile -File "{TOOLS}\\hooks\\sentinel-mojibake.ps1"',
             'timeout': 10},
            {'type': 'command',
             'command': f'pwsh -NoProfile -File "{TOOLS}\\hooks\\sentinel-pronoun.ps1"',
             'timeout': 10},
        ],
    }]
    PROJ.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')

    # ② 删假信任记录：只删正斜杠那条，反斜杠 True 那条保留
    d2 = json.loads(CJ.read_text(encoding='utf-8'))
    d2.get('projects', {}).pop('C:/Dev/zhuopin-ai', None)
    CJ.write_text(json.dumps(d2, ensure_ascii=False, indent=2), encoding='utf-8')

    # ③ 全局 settings.json：SessionStart 心跳（其余 hooks 键原样保留）
    d3 = json.loads(GLOB.read_text(encoding='utf-8'))
    d3.setdefault('hooks', {})['SessionStart'] = [{
        'hooks': [{'type': 'command',
                   'command': f'pwsh -NoProfile -File "{dst}"',
                   'timeout': 10}],
    }]
    GLOB.write_text(json.dumps(d3, ensure_ascii=False, indent=2), encoding='utf-8')

    # 核验（四项全 ✓ 才算装好）
    ok = True
    h = json.dumps(json.loads(PROJ.read_text(encoding='utf-8')).get('hooks', {}))
    for name, cond in (('H3 乱码哨兵已注册', 'sentinel-mojibake' in h),
                       ('H4 代词哨兵已注册', 'sentinel-pronoun' in h)):
        print(('✓' if cond else '✗'), name)
        ok = ok and cond
    zz = {k: v.get('hasTrustDialogAccepted')
          for k, v in json.loads(CJ.read_text(encoding='utf-8')).get('projects', {}).items()
          if k.rstrip('/\\').lower().endswith('zhuopin-ai')}
    cond = (zz == {r'C:\Dev\zhuopin-ai': True})
    print(('✓' if cond else '✗'), '信任记录唯一且为 True:', zz)
    ok = ok and cond
    cond = 'SessionStart' in json.loads(GLOB.read_text(encoding='utf-8')).get('hooks', {})
    print(('✓' if cond else '✗'), 'SessionStart 心跳已注册')
    ok = ok and cond
    print('—— 安装完成，四项全过；回一句「装好了」即可 ——' if ok
          else '—— 有未通过项：把上面输出原样发回，不要重试其它改法 ——')
    sys.exit(0 if ok else 1)


main()
