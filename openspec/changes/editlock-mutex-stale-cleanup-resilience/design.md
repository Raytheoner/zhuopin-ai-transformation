# Design: editlock-mutex-stale-cleanup-resilience

> 本设计**未经拍板，待 Shao Peishen 审**——与多数机制类变更包（三选一已由队列历史讨论定案、design 只做落地记录）不同，本变更的核心取舍（决策点 1）此前从未被讨论过，需要真实审议，不是补记录。

## 背景：为什么现有代码会死循环（先讲清楚 bug 本身，再讲怎么修）

`_acquire_mutex`（`工具-共享文档编辑锁.py` L479-517）用 `os.open(path, O_CREAT|O_EXCL)` 做原子测试并置位——这是保证互斥的唯一原语，本设计**不改动这一部分**。真正出问题的是"发现一枚陈旧 mutex 后如何清理"这一分支：

```python
except FileExistsError:
    age = ...
    if age is not None and age > MUTEX_STALE_SECONDS:
        try:
            mutex_path.unlink()
        except OSError:
            pass
        continue          # ← bug：无论 unlink 成功与否都执行，跳过了下面的 deadline 判断
    if time.monotonic() >= deadline:
        raise TimeoutError(...)
    time.sleep(MUTEX_POLL_SECONDS)
```

Cowork 沙箱对挂载目录没有删除权限，`unlink()` 恒抛 `PermissionError`；`continue` 让循环回到 `while True` 顶部再次尝试 `O_CREAT|O_EXCL`——但 mutex 文件其实还在原地（unlink 没成功），于是又是 `FileExistsError`，年龄仍然 > 10s，又 unlink 失败，又 `continue`……**死循环，且从不触达 `deadline` 判断**，`MUTEX_WAIT_TIMEOUT_SECONDS` 完全不起作用。`release` 的 `finally` 块是同一模式（`except OSError: pass`，只是没有循环，所以后果是"遗留"而非"死循环"，但成因相同）。

## 决策点 1：清理失败时的退路机制（核心决策，待拍板）

三个候选，**推荐候选 A**：

### 候选 A（推荐）：rename-away 到固定伴生路径

`unlink()` 失败时，改用 `os.replace(mutex_path, mutex_path.with_suffix(mutex_path.suffix + ".stale"))`——`os.replace` 是覆盖式原子改名，POSIX/Windows 均支持，且**本次巡逻已实测 Cowork 沙箱对 rename 有权限**（unlink 无权限但 rename 可用，这是队列 #322 行原文给出的环境事实）。canonical 路径 `xxx.mutex` 因改名而清空，下一次 `O_CREAT|O_EXCL` 能立即成功；`.stale` 目标路径固定（不随每次清理事件生成新文件名），后续清理复用同一目标名覆盖，junk 文件数量有界（每个锁目标至多 1 个 `.stale` 伴生文件，不会像巡逻手工处置那样无限堆积）。

**正确性论证（为什么改名不会破坏互斥语义）**：真正的互斥保证来自 `O_CREAT|O_EXCL` 在 canonical 路径上的原子创建，改名只是"清空路径"这一个动作，不改变谁能在 canonical 路径成功创建的判定规则。并发场景推演：若两个等待者 B、C 同时判定 mutex 陈旧并都尝试清理——不论谁的 `unlink`/`os.replace` 先成功，一旦 canonical 路径被清空，第二个清理调用会因为源文件已不存在而收到 `FileNotFoundError`（是 `OSError` 子类，被同一 `except OSError` 捕获，视为清理失败，不 `continue`，落到 deadline/sleep，下一轮循环再战）；两者中只有先清空路径的那个会立即在下一轮 `O_CREAT|O_EXCL` 上争到真正的持有权，另一个即便清理"失败"也不影响正确性——它会在下一轮看到一个**新鲜**的 mutex（刚被赢家创建，年龄很小），乖乖排队等待，不会误判为可再次强制接管。故 A 不引入双持有风险。

### 候选 B（不推荐）：内容标记代替存在性标记（对齐 `.editlock` 自身的 released 标记写法）

`.editlock` 本身的 release 是"改写为 released 标记而非删除"（#121(a)），队列 #322 行原文把这个选项并列写出。但 `.editlock` 的场景和 mutex 的场景**互斥要求不同**：`.editlock` 判定"是否有锁"是靠**读取并解析 JSON 内容**（`released: true` 即视为无锁），本来就不依赖文件存在性；而 `_acquire_mutex` 的互斥保证**恰恰来自** `O_CREAT|O_EXCL` 这一"存在性即所有权"的原子操作——若改成"读内容判断是否可声明所有权，再写内容声明"，则"读判定→写"退化回 #197 修复之前的 check-then-act 两步式，两个并发进程可能都读到"可声明"、都写入声明成功、都相信自己持有互斥——这正是 `_acquire_mutex` 当初被引入就是为了消灭的那类 bug（见模块 L478-484 docstring）。**除非引入额外的原子 CAS 原语（本项目现有工具箱内没有，跨平台文件锁 `fcntl`/`msvcrt` 会显著加重本次改动），候选 B 在正确性上不如候选 A，故不推荐。**

### 候选 C：unlink 失败即直接 fail-loud，不设退路

最简单，但会让 Cowork 沙箱下**每一次**遭遇陈旧 mutex 都必须等满 `MUTEX_WAIT_TIMEOUT_SECONDS` 才报错退出，且**从不会自动恢复**——因为 Cowork 环境下 unlink 恒失败，候选 C 下陈旧 mutex 会永久卡在原地，所有后续 acquire 都会在超时后失败，等于把"死循环"换成了"每次都失败"，没有解决"下一个 Cowork session 用不了"这个核心诉求。不推荐，仅作为 A/B 都不可行时的最后防线保留在代码里（deadline 判断本身就是这条防线，A 失败时自然会走到这里）。

**推荐**：候选 A。若 Shao Peishen 认为需要与 `.editlock` 自身写法保持形式一致（哪怕牺牲部分正确性边界），可选候选 B，但需接受"极窄并发窗口下理论上可能双持有"这一新增风险（发生概率：陈旧 mutex 存在 **且** 两个等待者的清理调用落在同一 `MUTEX_POLL_SECONDS`=0.02s 轮询窗口内，历史上从未观测到，但候选 A 完全不引入这个风险，做等价的事不需要多付出正确性代价）。

## 决策点 2：release 路径是否同步加固，还是只修 acquire 侧

**推荐：同步加固**（已写入 proposal 的 What Changes 第二条）。理由：不修 release 侧，Cowork 沙箱下每次正常 release 后 mutex 仍会遗留在原地，下一次 acquire 仍要先撞见 `FileExistsError`、算年龄、等到 >10s 才能进入（已修复的）stale 清理分支——多付出最多 10 秒的无谓等待。同步加固后，release 时立即改名清空，下一次 acquire 大概率直接命中 `O_CREAT|O_EXCL` 快路径，零等待。两处复用同一清理助手函数，不重复实现。

## 决策点 3：清理彻底失败（A 的 unlink 与 rename 都失败）时的行为

**推荐：不特殊处理，直接沿用既有的 deadline/sleep 逻辑**（即"落到下面的 deadline 判断"，不是清理失败就立刻抛错）。理由：若两条路都失败，可能是更严重的环境问题（如整个目录不可写），但也可能只是瞬时竞态（对方正在改名，稍等即可）；沿用既有轮询节奏给它 `MUTEX_WAIT_TIMEOUT_SECONDS` 内的重试机会，超时后自然 fail-loud，这正是修复前代码"本该有但被 `continue` 跳过"的行为，不新增额外分支、不扩大改动面。

## Non-Goals

- 不改动 `O_CREAT|O_EXCL` 这一核心互斥原语本身（#197 已验证正确，不重新设计）。
- 不引入跨平台文件锁（`fcntl`/`msvcrt`）等更重的同步机制——候选 A 已经在不引入新依赖的前提下解决问题。
- 不处理"`.stale` 伴生文件本身长期占用磁盘空间"这一更次要的问题——每锁目标至多 1 个，且是 0 字节文本文件，成本可忽略；若未来需要彻底清零，属于独立的运维脚本范畴，不在本变更内。
