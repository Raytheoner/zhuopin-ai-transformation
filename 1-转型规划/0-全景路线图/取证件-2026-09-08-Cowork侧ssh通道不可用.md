---
title: "取证件 · Cowork 侧 PowerShell 通道跑不了 ssh（2026-09-08）"
created: 2026-09-08
status: 已执行
会话: Cowork 业务总线 OP-0908-A（批 B-0908_B，泳道 358-audit-retention-p1p2）
结论: 通道不可用，非网络/密钥/目标机问题；该项按 lan-closeout 四步「冒烟不过即停项」降回留步态
---

# 取证件 · Cowork 侧 PowerShell 通道跑不了 ssh

## 一、背景

`#358`（平台 audit 留存与归档策略）的 design 审有两条**审前置**，`design.md` 自己写死：

- **P1**：`.51` 上审计类 `*.jsonl` 的真实大小与行数（`Get-ChildItem`）——决定 309 MB 落在 `TRACE` 类还是 `COMPLIANCE` 类，进而决定 D5 阈值默认值与 D7 迁移优先级；
- **P2**：该盘剩余磁盘空间（`Get-PSDrive`）——决定 D6 是「先封存后压缩」还是「封存即压缩」。

原文：**「在 P1/P2 有真实输出之前，D5／D6 的数值一律视为占位，审时不得当已定值照准。」**

两项均为 `.51` **纯只读**取证 ⇒ D1 ⏭️ 档。Shao Peishen 2026-09-08 在本会话答定夺 2 = (a)，已按 `#478` 条件放行路径走完 `transfer-out` → `deploy-authorize`（授权记录 #0，绑定转出记录 #0，LAN 探针 status=on），随后按 `zhuopin-lan-closeout` SKILL.md「执行步骤」第 4 项的固定四步执行。

## 二、实测（本机 PowerShell 通道，2026-09-08 09:30–09:3x +08:00）

| # | 命令 | 退出码 | stdout | stderr |
|---|---|---|---|---|
| 1 | `ssh -o BatchMode=yes -o ConnectTimeout=15 supplychain-server "hostname"` | **255** | 空 | 空 |
| 2 | 同上，stdout/stderr 各重定向到独立文件 | **255** | 空文件 | **空文件** |
| 3 | `ssh -vv …`（verbose 全量落文件） | **255** | 空文件 | — |
| 4 | `cmd /c "ssh … > %TEMP%\out.txt 2>&1"`（换 cmd 宿主） | **255** | 空文件 | — |
| 5 | 🔑 **`ssh -V`**（纯本地、不连网、只打印版本号） | **255** | 空 | 空 |

**对照组（同一通道、同一次调用批）**：

| 命令 | 退出码 | 输出 |
|---|---|---|
| `git --version` | 0 | `git version 2.53.0.windows.2` |
| `ping -n 1 192.168.100.51` | 0 | `Reply from 192.168.100.51: bytes=32 time=7ms TTL=127` |
| `Test-NetConnection 192.168.100.51 -Port 22` | — | `TcpTestSucceeded = True` |
| `Test-Path ~/.ssh/supplychain_server`（私钥） | — | `True` |
| `~/.ssh/config` 别名 | — | `Host supplychain-server → 192.168.100.51 / User Administrator / IdentityFile ~/.ssh/supplychain_server / StrictHostKeyChecking no` |
| `(Get-Command ssh).Source` | — | `C:\WINDOWS\System32\OpenSSH\ssh.exe` |

## 三、定性

🔑 **判定的支点是第 5 行**：`ssh -V` 不建立任何连接、不读密钥、不碰目标机，只打印版本号——**它也是 exit 255、零输出**。

⇒ 排除：网络不通（ping/TCP 22 均通）、密钥缺失（私钥在）、别名配置错（config 正确）、目标机故障（22 端口应答）、宿主壳差异（PowerShell 与 cmd 同结果）。

⇒ **结论：`ssh.exe` 在 Cowork 这条 PowerShell 执行通道里根本起不来**，与参数、目标、网络全部无关。三处旁证与之一致：⑴ 任何 ssh 调用退出码恒为 255；⑵ **连 `-vv` 都产不出一个字节**——正常的 ssh 失败一定会打印诊断，「一个字节都没有」说明进程在产出任何输出之前就被终止；⑶ 同批次其它外部 exe 全部正常。

🔴 **这正是「只读命令结果『太干净』先怀疑没读到对象」那条判据的又一实例**（`取证方法知识库.md`）：若不做第 5 行那个不连网的对照，最容易的误判是「`.51` 上没有 `.jsonl` 文件」或「LAN 断了」——两个结论都是错的，且都不会当场报错。

## 四、按纪律的处置

`zhuopin-lan-closeout` SKILL.md「执行步骤」第 4 项：**每项固定四步＝快照→执行→冒烟→回写证据；冒烟不过即回滚停项，失败项降回留步态并注明原因。**

- **步 1 快照/定位** 即失败（上表第 1 行），后续三步未进行。
- **无需回滚**：本项为纯只读，`.51` 上**没有发生任何写入**——快照那一步本身就没跑成，不存在需要撤销的状态改变。
- **降回留步态**：已跑 `deploy-record --outcome stopped --evidence-ref 1-转型规划/0-全景路线图/取证件-2026-09-08-Cowork侧ssh通道不可用.md`。
- 🔴 **授权未被消耗掉，也未被扩大**：Shao Peishen 的 2a 授权仍然只覆盖「P1/P2 两条只读取证」这一项；换执行体重跑时**须重新走一次 `transfer-out` → `deploy-authorize`**（逐项粒度，无批次级授权、无时间窗）。

## 五、承接（J1）

- **`#358` 的 design 审仍被 P1/P2 挡着**，本次未推进一步；队列 `#358` 行内的「▶ 下一棒 ＝ design 审」那句其真实前置是这两条取证。
- **可行的执行体**：CC 侧。依据＝`本周计划-2026-09-07.md` B-5，Shao Peishen 已加 `/permissions` 允许 `ssh supplychain-server`（当时为 `#424` 的 `ingest_tax_export.py` 放行）。⚠️ **该依据是他人转述的配置状态，本件未独立复核**——CC 侧首次跑之前应先 `ssh -V` 自测一次，**用同一个不连网的对照命令**，再决定要不要往下走。
- **不在本会话修**（`zhuopin-lane-watch` §「看护会话不修工具」）：本件只取证＋登记，通道本身怎么修、是否需要修，归后续派单。
