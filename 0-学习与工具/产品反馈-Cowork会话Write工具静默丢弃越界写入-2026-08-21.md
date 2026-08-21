---
status: 待发
title: "产品反馈 · Cowork 本地会话 Write 工具对越界路径静默丢弃（2026-08-21）"
created: 2026-08-21
执行方: Cowork 环境总线（OP-0821-B，执行队列 §四 #78）
用途: 供 Shao Peishen 直接提交给 Anthropic（Claude 桌面版 Cowork 反馈入口／thumbs-down）
---

# 产品反馈 · Cowork 本地会话的 `Write` 工具会静默丢弃越界写入

> **给 Shao Peishen 的说明**：本件已按「可直接提交」写好，下面 **§ 提交正文** 整块复制即可。§ 附录是留在本仓库的取证细节，不必一并提交。

---

## 提交正文（复制这一段）

**产品**：Claude 桌面版 / Cowork 模式
**日期**：2026-08-21
**严重度建议**：High —— 数据静默丢失，且系统提示本身在引导用户踩进去

### 问题一句话

在 Cowork 本地会话中，`Write` 工具对**超出 connected folders 边界**的路径**返回成功、实际不写入任何文件**，且不产生任何错误或警告。同一路径的 `Read` 工具则会**正确拒绝**并给出清晰的边界提示。

**⇒ 缺陷是 `Write` 没有执行 `Read` 已经在执行的那道边界检查，而它选择的失败模式是 fail-silent 而不是 fail-loud。**

### 为什么这条比一般的边界问题严重

**读类工具静默回退，最坏结果是拿到一个错误答案；写类工具静默回退，结果是「以为存下来了，其实什么都没有」。** 后者不会在当次暴露，只会在很久以后、当有人去取那份数据时才发现——而那时已经无从追溯写了什么、写了几次。

### 让它更严重的第二层：系统提示自己就在引导用户踩进去

Cowork 会话的系统提示中有一段 **Memory** 说明，明确给出一个本机路径并写道：

> "You have a persistent file-based memory at `…\local-agent-mode-sessions\<…>\spaces\<…>\memory\`. This directory already exists — write to it directly with the Write tool (do not run mkdir or check for its existence)."

实测：

1. **该目录确实存在**，但里面只有两个 2026-06／2026-07 的陈旧文件；
2. **按该指引用 `Write` 往其中写文件 → 返回 `File created successfully at: …`；本机 PowerShell `Test-Path` → `False`**；
3. **同一会话的系统提示还注入了一份 `MEMORY.md` 索引，并声明它位于同一目录**——而该目录下没有 `MEMORY.md`，在 `AppData\Roaming\Claude` 全树递归搜索 `MEMORY.md` 也是 **0 命中**（索引显然来自服务端）。

**⇒ 一个严格照系统提示行事的会话，会把记忆写进一个没人读、且不会报错的地方。** 我们这边已经真实发生了两次（第一次丢的是一份人员信息记录，直到隔天做审计才发现）。

### 复现步骤（约 2 分钟）

1. 在 Claude 桌面版 Cowork 模式开一个会话，连接任意一个工作文件夹；
2. 用 `Write` 工具往系统提示 Memory 段给出的 `…\spaces\<…>\memory\` 路径写一个新 `.md` 文件；
3. 观察工具返回：`File created successfully at: <路径>`；
4. 在 Windows PowerShell 中执行 `Test-Path '<同一路径>'` → 返回 **`False`**；
5. 递归搜索该文件名（`AppData\Roaming\Claude`、`AppData\Local\Claude`、`~\.claude` 三处）→ **全部 0 命中**（说明不是被重定向，是真的丢弃）；
6. 对照组：用 `Read` 工具读同一目录下一个**确实存在**的文件 → 返回 `… is outside this session's connected folders, so Read can't reach it.`（边界检查在 `Read` 侧是生效的）。

**同一缺陷的第二个受害者**：往会话的 `outputs` 暂存目录写文件同样「报成功、目录根本不存在」。**在该会话类型下，`Write` 真正能落盘的只有 connected folder，其余路径一律静默丢弃。**

### 期望行为（按优先级）

1. **`Write` 对越界路径应 fail-loud**，返回与 `Read` 同样清晰的边界错误，而不是 `File created successfully`。这是最小修复，且与现有 `Read` 行为一致。
2. **修正系统提示**：Cowork 本地会话的 Memory 段不应指向一个 `Write` 无法写入的本机路径。要么提供真正可写的 memory 工具，要么把该段改为明确说明「本会话对 memory 只读」。
3. **补充说明会话类型差异**（可选但很有帮助）：实测三种会话类型的 memory 能力完全不同——桌面版 Cowork 无任何 memory 工具；claude.ai 网页版 chat 有 `memory_read/write/append/str_replace/delete/list`；claude.ai 网页版 Cowork 两套都没有。用户无从得知自己所处会话属于哪一种，也就无从判断「我刚才存的东西到底有没有存下来」。

### 环境

Windows 11 / Claude 桌面版 Cowork 模式 / 工作文件夹位于 OneDrive 同步目录下（该路径的 `Read`／`Write` 均正常，问题只出现在 connected folder 之外的路径）。

---

## 附录（留档，不必提交）

- 完整取证与三种会话类型对照见 `1-转型规划/0-全景路线图/memory与上下文预算治理-审核与方案-2026-08-21.md` §一.0 与 §一.1。
- 本项目对此缺陷的处置：memory 层已整体判为**只读历史资产**（队列 `#254` 于 2026-08-21 整行销号），跨会话纪律的权威载体只有根 `CLAUDE.md` 与队列。
- 本项目已把该形态归入既有的「**工具静默回退**」家族——随身判据是：**当一个只读命令返回了「太干净」或「太正常」的结果，先问它是不是根本没读到我以为的那个对象**；本次把这条判据从读侧扩展到了写侧：**写类工具报成功，不等于真的写了；须用工具链之外的手段（本机 `Test-Path`／哈希）复核。**
