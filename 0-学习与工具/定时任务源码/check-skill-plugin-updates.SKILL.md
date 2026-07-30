---
name: check-skill-plugin-updates
description: 每月检查企业AI转型项目环境依赖清单里登记的工具/插件/Skill(SuperPowers/OpenSpec等)是否有新版本，有则简报影响，不建议盲目升级
---

这是"卓品智能AI转型"项目（企业AI转型仓库）的定期环境依赖巡检任务，Paul（分管供应链的VP）要求对项目里用到的所有 skill/plugin 建立"有更新就提醒"的习惯，这是那个习惯的自动化实现。

背景：这个项目用 OpenSpec + SuperPowers 做 SDD（Spec-Driven Development）协同开发。SuperPowers（github.com/obra/superpowers）是全局插件，项目文档里记录的版本容易过时（之前发现文档写的是 v5.1.0，实际最新已经到 v6.1.1）。项目根目录 `0-学习与工具/环境依赖清单.md` 是登记当前工具版本和用途的地方，`.claude/settings.json`（如果能访问到）里有项目域插件声明。

请执行：
1. 如果连接了「企业AI转型」项目文件夹，读一遍 `0-学习与工具/环境依赖清单.md`，拿到当前登记的工具清单和版本（目前至少有：Claude Code、OpenSpec、SuperPowers）。如果没连接到文件夹，就只检查下面第2步里明确列出的几个工具，不用为了读文件去申请文件夹权限。
2. 对清单里的每个工具，用 WebSearch 或 web_fetch 查它的最新版本/发布日期：
   - SuperPowers：直接查 https://github.com/obra/superpowers/releases 最新 release，**优先直接抓 release 具体标签页的内容核实，不要只信搜索引擎摘要**——之前发现过搜索摘要和实际release notes对不上的情况，一定要交叉验证。
   - OpenSpec：查 npm 上 openspec 包的最新版本。
   - 如果环境依赖清单里后续又登记了别的工具（比如 Comet 或其他编排层，如果 Paul 之后采纳了），一并检查。
3. 对比清单里记录的版本和查到的最新版本，判断是否有新版本发布。
4. 如果有新版本：简述这次更新具体改了什么（重点关注：是否涉及审查/验证机制变化、有没有 breaking change、是否新增了跟这个项目实际使用场景相关的功能）。**不要主动建议"应该升级"**——只客观汇报事实和你对影响的判断，升级与否是 Paul 的决定，不是你的。如果你查到的信息来源不可靠/无法交叉验证，如实说明"没能验证清楚"，不要编造细节。
5. 如果没有新版本，只需要简短确认"本月无更新"，不用写长报告。
6. 回复格式：简洁的中文小结，每个工具一两句话即可，不需要复杂排版。这是纯只读检查，不要修改仓库里的任何文件。
