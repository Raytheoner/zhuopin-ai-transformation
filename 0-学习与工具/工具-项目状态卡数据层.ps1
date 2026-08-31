# ============================================================================
# 工具-项目状态卡数据层.ps1
# 卓品智能 AI 转型 · Cowork artifact「Zhuopin Project Status」的只读数据层。
#
# 🔴 为什么脚本在这里、而不是内联在 artifact 里（2026-08-31）：
#    Windows-MCP 的 PowerShell 通道对单条 command 有长度上限。实测判据（取自本卡
#    debug.jsonl，非推断）：11,780 / 11,826 字符历次 OK；15,099 字符连续 8 次全部
#    FileNotFoundError [WinError 206] 文件名或扩展名太长 ⇒ 墙在 11,826 与 15,099 之间，
#    约 12,000。cmd.exe 的 8,191 已被 11,826 的成功排除；最合理解释是走 -EncodedCommand，
#    UTF-16LE→base64 膨胀约 2.67 倍，32,767 / 2.67 ≈ 12,270，正落在这两个数之间。
#    2026-08-31 的 fail-loud 改造把脚本从 11,826 推到 15,099，当场越线、整卡打不开。
#    ⇒ 外置到本文件后，artifact 只发一条约 80 字符的调用命令，余量从 ~0 变为 ~99%，
#      且脚本进版本控制、可 grep、可脱离 artifact 单跑。
#
# 契约：stdout 必须输出且仅输出一行 "@@JSON@@" + 压缩 JSON。调用方按该前缀切片。
# 纪律：纯只读——不改文件、不触发动作、不发通知。
# 编码：UTF-8 with BOM（含中文字面量与正则；无 BOM 时 PS 5.1 会按 ANSI 解致乱码）。
# ============================================================================

# 🔴 2026-08-31：仓库 2026-08-26 迁至 C:\Dev\zhuopin-ai，原 OneDrive\Projects\企业AI转型 已零残留。
#    本机实测：旧根 Test-Path=False；12 条读取路径在旧根**全 False**、在新根**全 True**。
#    ⇒ 迁移当日起本页每一张卡都在读不存在的路径，而 inbox／pool／wk／disp 四张把「读不到」
#    渲染成 0 且挂绿色 .zero ⇒ **全盘失效的那一刻，页面显示的是最健康的状态**。
#    这与 #312 记的静默回退同形态：返回值正常、结论是空的，且只核源码文本看不出来。
# 🔑 刻意**硬编码单一字面量，不做候选列表回退**：回退会在旧副本某天重新出现时静默读到陈旧数据，
#    正是本项目反复付学费的形态。再搬一次家，就让所有卡显式喊「无法核验：仓库根不存在」。
$root='C:\Dev\zhuopin-ai'
$rootOk=[bool](Test-Path -LiteralPath $root)
# ===== 数据源可核验性登记（2026-08-31）=====
# 每个逻辑数据源登记 ok/why，JS 渲染前必查。ok=false ⇒ 渲染「本类无法核验：<原因>」，
# **绝不落到 0／绿色「无事项」**。why 必须指名道姓（哪个文件、哪一节），否则等于没说。
$src=[ordered]@{}
# ok=false 却给不出 why，本身就是缺陷：那会在页面上渲染成一个没有理由的「无法核验」，
# 与「静默变 0」只差一步。故在此兜住，让缺陷自曝而不是让它安静。
function Set-Src($k,$ok,$why){ if((-not $ok) -and ($null -eq $why -or $why -eq '')){ $why='判定为不可核验但未给出原因——这是本状态页脚本自身的缺陷，请报修' }; $src[$k]=[ordered]@{ok=[bool]$ok;why=$why} }
# 函数名不得用 RD/rd 等（rd 是 Remove-Item 的内置别名，别名优先级高于函数）
function Read-Src($k,$rel){
  if(-not $rootOk){ Set-Src $k $false ('仓库根不存在：'+$root); return '' }
  $p=Join-Path $root $rel
  if(-not (Test-Path -LiteralPath $p)){ Set-Src $k $false ('文件不存在：'+$rel); return '' }
  try{ $t=Get-Content -LiteralPath $p -Raw -Encoding UTF8 }catch{ Set-Src $k $false ('读取异常：'+$rel+' — '+$_.Exception.Message); return '' }
  if($null -eq $t -or $t.Trim().Length -eq 0){ Set-Src $k $false ('文件为空：'+$rel); return '' }
  Set-Src $k $true ''; return $t }
function Read-Doc($rel){ $p=Join-Path $root $rel; if($rootOk -and (Test-Path -LiteralPath $p)){ Get-Content -LiteralPath $p -Raw -Encoding UTF8 } else { '' } }
# 队列 #22 v1 ①：状态列「开头片段」判据——**直接复用 0-学习与工具/工具-落库sweep.py 的口径，不另写一套**。
# 对应 sweep 的 _leading_status_segment()：先去除前导 `*`/空格/Tab/全角空格(U+3000)，
# 再截到第一个句级分隔符（。/——/━━━，即 sweep 的 LEADING_SEGMENT_SEPARATORS）之前。
# 为何必须锚定开头而非全列扫描：#248 实证全列扫描会命中说明文字里被引用的判据原文（同族第三次才达阈值机制化）。
function Get-LeadSeg($s){ $t=$s.TrimStart([char[]]@([char]42,[char]32,[char]9,[char]0x3000)); $cut=$t.Length; foreach($sp in @([char]0x3002,'——','━━━')){ $i=$t.IndexOf($sp); if($i -ge 0 -and $i -lt $cut){ $cut=$i } }; return $t.Substring(0,$cut) }
# 🔴 2026-08-10 队列 #312 主体：反引号感知切列（PS 侧），口径逐字复刻权威实现
#    zhuopin_platform/shared_tools/queue_table.py::split_row_cells（队列 #314，CommonMark 反引号
#    **游程**配对，不是单反引号正则——后者已在真实数据上被证伪，见该模块 _mask_backtick_spans 注释）。
# 🔑 为何必须与本卡同批改（非顺手扩范围）：原朴素 `-split '|'` 在**当前生产队列文件上正在失效**——
#    #313 一行的状态列含 `git grep` 正则交替符（反引号包裹的合法内容），朴素切列取到的"状态列"
#    实为任务列碎片、不含 [S:] 字段 → 该行被静默漏计 WIP 且落入「其他」桶。这是 #314① 已在
#    Python 侧修好、而 JS/PS 第二实现仍存活的同一缺陷；不修则新卡要么复用坏解析、要么另造一份
#    第二解析器，两条都是本项目反复付学费的形态。
function Split-Row($line){ $s=$line.Trim(); if(-not $s.StartsWith('|')){ return $null }; $sb=New-Object System.Text.StringBuilder; $i=0; $n=$s.Length
  while($i -lt $n){ if($s[$i] -ne [char]96){ [void]$sb.Append($s[$i]); $i++; continue }
    $j=$i; while($j -lt $n -and $s[$j] -eq [char]96){ $j++ }; $rl=$j-$i; $k=$j; $cs=-1; $ce=-1
    while($k -lt $n){ if($s[$k] -ne [char]96){ $k++; continue }; $k2=$k; while($k2 -lt $n -and $s[$k2] -eq [char]96){ $k2++ }; if(($k2-$k) -eq $rl){ $cs=$k; $ce=$k2; break }; $k=$k2 }
    if($cs -lt 0){ [void]$sb.Append($s.Substring($i,$j-$i)); $i=$j } else { [void]$sb.Append($s.Substring($i,$ce-$i).Replace('|',[char]1)); $i=$ce } }
  return @($sb.ToString().Trim('|') -split '\|' | ForEach-Object { $_.Replace([char]1,'|').Trim() }) }
$relay = Read-Src 'relay' '1-转型规划\0-全景路线图\session接力-Phase1收口.md'
# 🔴 2026-08-31：原锚点 `^> 更新：` 已随 2026-08-22 OP0822A「定长交接卡」改版**整行消失**
#    （本机实测：全文 -match '更新' 亦为 False）⇒ 快照卡自那日起长期空白。
#    **这是与本次搬家无关的第二处独立失效**——搬家只是让它从"空白"变成"空白且无人察觉"。
#    改锚 `## 二、当前状态快照（YYYY-MM-DD）` 一节正文：改版后状态文字即落在该节。
#    §三「下一会话主攻」正则实测仍命中，不动。
$snap=''
$m=[regex]::Match($relay,'(?s)##+[^\r\n]*当前状态快照[^\r\n]*\r?\n(.*?)(?=\r?\n## |\z)')
if($m.Success){ $s=(($m.Groups[1].Value -split "`r?`n" | Where-Object { $_.Trim() -ne '' }) -join "`n").Trim(); if($s.Length -gt 900){$s=$s.Substring(0,900)+[char]0x2026}; $snap=$s }
if(-not $src['relay'].ok){ Set-Src 'snap' $false $src['relay'].why } elseif(-not $m.Success){ Set-Src 'snap' $false '节未匹配：session接力-Phase1收口.md 内找不到「## 二、当前状态快照」' } else { Set-Src 'snap' $true '' }
$next=@()
$mm=[regex]::Match($relay,'(?s)##+[^\r\n]*下一会话主攻[^\r\n]*\r?\n(.*?)(?=\r?\n## |\z)')
if($mm.Success){ $next=@($mm.Groups[1].Value -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '^\d' } | Select-Object -First 6) }
if(-not $src['relay'].ok){ Set-Src 'next' $false $src['relay'].why } elseif(-not $mm.Success){ Set-Src 'next' $false '节未匹配：session接力-Phase1收口.md 内找不到「下一会话主攻」' } else { Set-Src 'next' $true '' }
$impl = Read-Src 'impl' '1-转型规划\0-全景路线图\卓品智能AI转型实施计划（最新版）.md'
$dls=New-Object System.Collections.Generic.List[string]
$on=$false
foreach($l in ($impl -split "`r?`n")){
  if($l.StartsWith('|') -and ($l -match '红线日')){ $on=$true; continue }
  if($on){
    if($l.StartsWith('|--') -or $l.StartsWith('| --') -or $l.StartsWith('|:')){ continue }
    if(-not $l.StartsWith('|')){ break }
    if($dls.Count -lt 18){ $dls.Add($l) }
  }
}
$deadlines=@($dls)
if(-not $src['impl'].ok){ Set-Src 'deadlines' $false $src['impl'].why } elseif($deadlines.Count -eq 0){ Set-Src 'deadlines' $false '节未匹配：实施计划内未找到含「红线日」的表头行' } else { Set-Src 'deadlines' $true '' }
$readme = Read-Src 'letters' '6-人才与组织\部门AI专员跟进\README-跟进机制与命名约定.md'
$letters=@(($readme -split "`r?`n") | Where-Object { $_.StartsWith('| 20') } | Select-Object -Last 12)
if($src['letters'].ok -and $letters.Count -eq 0){ Set-Src 'letters' $false '节未匹配：跟进 README 内无以 | 20 起头的清单行' }
$one = Read-Src 'domains' '6-人才与组织\部门AI专员协同一页纸.md'
$domains=@(($one -split "`r?`n") | Where-Object { $_.StartsWith('## ') -and $_.Contains(' · ') } | ForEach-Object { $_.Substring(3) })
if($src['domains'].ok -and $domains.Count -eq 0){ Set-Src 'domains' $false '节未匹配：协同一页纸内无「## X · Y」形态的域标题' }
# 🔴 2026-08-11 队列 #315 / 变更包 queue-dual-file-split 任务 3.8：队列已拆为**两份物理文件**。
#    原实现读的 `跨桌任务队列.md` 自 2026-08-11 11:37 起只剩 1237 字节的**指针文件**（正文只有两行去向
#    指引，无 `## 一、` 标题、无任何表格）⇒ §一/§二/§四 三处正则全部失配 ⇒ 任务看板、可 Open 池、
#    全局收工态三张卡同时空白。**这不是待办，是拆分当天即已发生的现网故障**（实测旧逻辑取到 §一 = 0 行）。
#    改法取最小改动：**只换取数源、不动解析口径**——两份文件各跑一遍同一套正则、行数组按序拼接；
#    §一 的 `[S:…][D:…]` 机器字段在两份文件里都已保留，故下游桶归属／WIP／可 Open 池判据一字未改。
# 🔑 两处与合并前的真实差异，均已在本机实测坐实（不是照搬旧正则想当然）：
#    ⑴ §二 的 lookahead **必须加 `|\z`**——业务场景那份的 §二 是**末节**、其后没有下一个 `## `，
#       沿用原 `(?=\r?\n## )` 会整节失配，实测该文件 6 行批次一行都读不到**且不报错**——
#       正是本项目记的「工具静默回退」：返回值正常、结论是空的。§一 一并加上，防其日后也变成末节。
#    ⑵ **§三 口径冻结标、§四 需 Shao Peishen 的动作、编号高水位线声明只在机制环境那份**——
#       对业务场景那份不去找它们：`Match` 自然失配即跳过；HWM 另用 `if($hwm -eq '')` 守住，
#       不让后一份的空结果覆盖前一份已取到的值。
$QF=@('1-转型规划\0-全景路线图\跨桌任务队列-机制环境.md','1-转型规划\0-全景路线图\跨桌任务队列-业务场景.md')
# 🔴 2026-08-31 实测踩中：**PowerShell 变量名大小写不敏感**，下面 `foreach($qf in $QF)` 的
#    循环变量 $qf 与数组 $QF 是**同一个变量** ⇒ 循环结束后 $QF 已被覆写成最后一个文件路径（字符串），
#    `$QF.Count` 返回 1 而非 2 ⇒ `$q1f -eq $QF.Count` 恒为 false ⇒ q1/q2 被判「无法核验」。
#    方向上是安全的（宁可多报无法核验），但理由为空、且会天天误报。故先把长度存下来再进循环。
$QFn=$QF.Count
$qk=@(); $qp=@(); $qb=@(); $qbAll=@(); $hwm=''; $qBad=@(); $q1f=0; $q2f=0; $q4f=0
# 🔴 2026-08-31：两份队列文件**各自登记成败**。只要有一份读不到，§一/§二 的行数就是偏低的，
#    而偏低的计数长得跟「今天很清闲」一模一样 ⇒ 任一份失败即把相关卡整体判为无法核验，
#    **不显示一个看起来正常的残缺数字**。这是 #315 拆两份之后新增的失败面。
foreach($qf in $QF){
  $lf=Split-Path $qf -Leaf
  if(-not $rootOk){ $qBad+=('仓库根不存在：'+$root); break }
  $pq=Join-Path $root $qf
  if(-not (Test-Path -LiteralPath $pq)){ $qBad+=('文件不存在：'+$lf); continue }
  $queue=Get-Content -LiteralPath $pq -Raw -Encoding UTF8
  if($null -eq $queue -or $queue.Trim().Length -eq 0){ $qBad+=('文件为空：'+$lf); continue }
  $mq=[regex]::Match($queue,'(?s)## 一、任务看板(.*?)(?=\r?\n## |\z)')
  if($mq.Success){ $q1f++; $qk+=@($mq.Groups[1].Value -split "`r?`n" | Where-Object { $_ -match '^\| \d+ \|' }) } else { $qBad+=($lf+' 缺「## 一、任务看板」节') }
  $mb=[regex]::Match($queue,'(?s)## 二、待 commit 批次(.*?)(?=\r?\n## |\z)')
  if($mb.Success){ $q2f++; $qbAll+=@($mb.Groups[1].Value -split "`r?`n" | Where-Object { $_ -match '^\| B-' }) } else { $qBad+=($lf+' 缺「## 二、待 commit 批次」节') }
# §四 按设计只在机制环境那份（业务场景那份没有属正常，不计失败）；仅当两份都没有才算失败。
  $mp=[regex]::Match($queue,'(?s)## 四、[^\r\n]*(.*?)(?=\r?\n---|\z)')
  if($mp.Success){ $q4f++; $qp+=@($mp.Groups[1].Value -split "`r?`n" | Where-Object { $_ -match '^\| \d+ \|' }) }
  if($hwm -eq ''){ $mh=[regex]::Match($queue,'编号高水位线：§一 #(\d+)[^#]*#(\d+)'); if($mh.Success){ $hwm='§一 #'+$mh.Groups[1].Value+' ｜ §四 #'+$mh.Groups[2].Value } }
}
$qWhy=($qBad -join '；')
Set-Src 'q1' ($qBad.Count -eq 0 -and $q1f -eq $QFn) $qWhy
Set-Src 'q2' ($qBad.Count -eq 0 -and $q2f -eq $QFn) $qWhy
$q4why=$qWhy; if($q4f -lt 1 -and $q4why -eq ''){ $q4why='节未匹配：两份队列文件均无「## 四、」节' }
Set-Src 'q4' ($qBad.Count -eq 0 -and $q4f -ge 1) $q4why
# 队列 #22 v1 ②：原实现是「整行 -notmatch ✅」——比 #248 那次还宽（连状态列都不切就全行扫），
# 说明文字里出现 ✅ 即会把待处理批次误判为已完成。改为 sweep 同款：只看状态列(cells[3])的开头片段。
$qb=@(); $qbFuzzy=@(); $qbSkip=@()
# 🔴 2026-08-31：原为**裸 continue**——列数不足的批次行被静默丢弃，§二 计数偏低，
#    而页面照样显示绿色「0 批，已全部落库」。这正是「把源异常当正常分支跳过」的形态：
#    payload 合法、结论是空的。改为记入 $qbSkip 并在看板上列出，失败显式传到渲染层。
foreach($rb in $qbAll){ $cb2=($rb -split '\|'); if($cb2.Count -lt 6){ $qbSkip+=,($rb.Trim()); continue }; $cb2=$cb2[1..($cb2.Count-2)]; $LB=Get-LeadSeg ($cb2[3].Trim()); if($LB -match '待'){ $qb+=$rb } elseif($LB -notmatch '✅'){ $qbFuzzy+=$rb } }
# 队列 #22 v1 ①：§一 分组。桶归属只看开头片段的**首个状态标记**（本项目约定状态列以标记起头）。
# 为何不是「含某关键词」：实测 #172 的开头片段里有「待领行」三字（在描述代码解析对象），
# #153 的开头片段中段有个 ✅——两者用「含」判据都会归错桶。首标记锚定对 102 行实测无误。
$qg=[ordered]@{}; foreach($kk in @('已完成','在办','待领','定时触发型','挂起','搁置','其他')){ $qg[$kk]=New-Object System.Collections.Generic.List[string] }
$qconf=New-Object System.Collections.Generic.List[string]
# 协议〇.9 措施 C：机制类可动 WIP 计数。上限 16（2026-08-09 由 8 上调，口径冻结观察至 2026-08-16）。
# 🔴 2026-08-10 队列 #312⑹：判据由「关键词正则猜中文」改为直接读 #308 机器字段，口径严格对齐
#    工具-共享文档编辑锁.py::_count_mechanism_wip——域为机/业 且 状态属 open/partial/hold，
#    字段后正文剥前导星号空白后不以停止符号起首；done/blocked/timed= 结构性排除。原 metaRe/bizRe 双侧比大小已随此退休。
# ===== 队列 #312 主体：opener 出处扫描（先扫，供下方 §一 行循环引用）=====
# 判据（本卡登记，可机械化）：只认**标题行**里写明「队列 #NNN」或「#NNN」的段落——
#   ⑴ `派单件-*.md`：整份文件即派单件，任何层级标题里的 #NNN 都算；
#   ⑵ `本周计划-*.md`：**只认 A 节**（`A1`/`A7a`/`A8`…）——B 节是决策项、C 红线日、D 自检，
#      它们同样大量引用 #NNN，全扫会把「等你拍板」误报成「已出 opener」（实测 B-2 引用 §一 #122）。
#   ⑶ `§四 #NN` 先剥掉再取号——§四 与 §一 编号独立，不剥会把 §四 #52 认成 §一 #52（A5 标题实例）。
# 新鲜度：按**文件名里的日期**降序取第一份命中的文件（同一文件内多个 A 节标签一并列出）；
#   比最新一份《本周计划》更旧的出处标 ⏳旧 —— 不谎称"在用"，只说"最近一次出处"。
$op=@{}; $opNewest=''
$odir=Join-Path $root '1-转型规划\0-全景路线图'
if(Test-Path -LiteralPath $odir){
  $ofs=@(Get-ChildItem -LiteralPath $odir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '派单件-*.md' -or $_.Name -like '本周计划-*.md' })
  foreach($of in $ofs){ $md0=[regex]::Match($of.Name,'\d{4}-\d{2}-\d{2}'); if($md0.Success -and $md0.Value -gt $opNewest){ $opNewest=$md0.Value } }
  $ofs=@($ofs | Sort-Object @{Expression={ $m0=[regex]::Match($_.Name,'\d{4}-\d{2}-\d{2}'); if($m0.Success){$m0.Value}else{'0000-00-00'} }} -Descending)
  foreach($of in $ofs){
    $isw=$of.Name.StartsWith('本周计划'); $mdt=[regex]::Match($of.Name,'\d{4}-\d{2}-\d{2}'); $ofd=$(if($mdt.Success){$mdt.Value}else{''})
    foreach($hl in @(Get-Content -LiteralPath $of.FullName -Encoding UTF8 | Where-Object { $_ -match '^#{1,4} ' -and $_ -match '#\d+' })){
      $h2=($hl -replace '§四\s*#\d+',''); if($h2 -notmatch '#\d+'){ continue }
      $mlb=[regex]::Match($h2,'^#+\s+([A-Za-z]+\d*[a-z]?)'); $lab=$(if($mlb.Success){$mlb.Groups[1].Value}else{''})
      if($isw -and $lab -notmatch '^A\d'){ continue }
      foreach($mn in @([regex]::Matches($h2,'#(\d+)'))){ $kk2=$mn.Groups[1].Value
        if(-not $op.ContainsKey($kk2)){ $op[$kk2]=[ordered]@{file=$of.BaseName;date=$ofd;labs=@()} }
        if($op[$kk2].file -eq $of.BaseName -and $lab -ne '' -and ($op[$kk2].labs -notcontains $lab)){ $op[$kk2].labs+=$lab } } } } }
# ===== 队列 #312 主体：可 Open 池 =====
# 入池判据**全部读 #308 机器字段**，不用关键词猜中文：
#   · [S:open]          → 结构性入池
#   · [S:partial]       → **默认入池**（partial 语义即"部分完成 ⇒ 必有剩余"），
#                         仅当状态列开头片段自陈「在办/在建/进行中/建造中」时排除，且**单列出来不静默丢弃**
#   · done/blocked/hold/timed= / 正文以 🛑 起首 → 结构性排除（同 _count_mechanism_wip 口径）
# 🔑 为何 partial 用"默认入池 + 例外排除"，而不是反过来"找待领证据才入池"：
#   本轮实测——用 #304 那张待领词表（待领|仍待|待补|…）反向找证据，13 条 partial 只命中 4 条，
#   会漏掉 #22／#68／#234／#254 这类**把待领子项写在句号之后**的行（开头片段截到句号即止）。
#   **漏报正是 #312 立行时点名要避免的失败形态**（原文：只取 open 会漏掉 13 条中的绝大多数可做项），
#   而多报一条的代价只是他多看一眼。故选偏多报、并把被排除的行也列出来供反查。
# 🔴 2026-08-31：$qkSkip 记录**切列失败被跳过的 §一 行**。原为裸 continue：这类行不进任何桶、
#    不进可 Open 池、也不进 poolDeg，等于从全页彻底消失 —— 行还在文件里，页面上却当它不存在。
$pool=@(); $poolEx=@(); $poolDeg=@(); $qkSkip=@()
$wipMeta=0; $wipBiz=0
# 🔴 2026-08-10 队列 #312 实测发现（第三处静默失效，非本次引入）：#308 机器字段 2026-08-09 回填后，
#    状态列开头已变成 `[S:done][D:机] ✅…`，而本桶判据锚定「开头片段的首个状态标记」——
#    于是 `^✅`/`^🟡`/`^待领` 全部失配，**122 行全部落入「其他」桶，待领/在办/已完成 均显示 0**
#    （对上线版实跑复现：其他=122、待领=0）。`wkN` 徽标随之显示 0 并挂上绿色 zero 类 ⇒ **看起来最健康的时候恰是坏掉的时候**。
#    修法取最小改动：切列后**先剥掉机器字段前缀**再交给原判据，语义与 #308 之前逐字相同，不动桶定义。
foreach($rq in $qk){ $cq=Split-Row $rq; if($null -eq $cq -or $cq.Count -lt 8){ $qkSkip+=,(($rq.Trim('|') -split '\|')[0].Trim()); continue }; $nq=$cq.Count; $LQ=Get-LeadSeg ($cq[$nq-3] -replace '^[\s\*]*\[S:[^\]]*\](\[D:.\])?(\[A:[^\]]*\])?\s*',''); $kk='其他'
  if($LQ -match '^✅'){ $kk='已完成' }
  elseif($LQ -match '^(🟡|🔄|📤|✉️|📌|🔽|⚠️|🟢)' -or $LQ -match '^部分完成'){ $kk='在办' }
  elseif($LQ -match '^待领'){ if($LQ -match '定时触发型'){ $kk='定时触发型' } else { $kk='待领' } }
  elseif($LQ -match '^(⏸|🔒)'){ $kk='挂起' }
  elseif($LQ -match '^🛑'){ $kk='搁置' }
  $qg[$kk].Add($cq[0])
# 词表＝队列 #304 的权威定义，**改词表须同步改 #304 行并回写另一处实现**（已登记的重复，非静默重复）。
# 🔴 刻意不含「缺口」——它在本项目是业务名词（材料缺口/缺口清单），与任务状态词撞义
# （同 §〇.2「已有专属含义的词不得表达第二种含义」）；实测含它会把 #203/#297 误报，去掉后当前文件精确率 100%。
  if($kk -eq '已完成' -and $LQ -match '待领|仍待|待补|待实现|待审|待你|未做|未实现|另一半|半边'){ $qconf.Add($cq[0]) }
# 字段匹配改为**行首锚定**（原为不锚定的 Match，会命中正文里被引用的字段样例）——
# 与权威实现 工具-共享文档编辑锁.py::_parse_status_domain_fields 一致：先剥前导 `*`/空白，再从头匹配。
  $scq=$cq[$nq-3]; $mfq=[regex]::Match($scq,'^[\s\*]*\[S:(\w+)(?:=[\d-]+)?\]\[D:(.)\]')
  if($mfq.Success){ $svq=$mfq.Groups[1].Value; $dvq=$mfq.Groups[2].Value; $rq2=($scq.Substring($mfq.Index+$mfq.Length) -replace '^[\s\*]+','')
    if(@('open','partial','hold') -contains $svq -and -not $rq2.StartsWith('🛑')){ if($dvq -eq '机'){ $wipMeta++ } elseif($dvq -eq '业'){ $wipBiz++ } }
    $LR=Get-LeadSeg $rq2; $tk=Get-LeadSeg $cq[1]; if($tk.Length -gt 78){ $tk=$tk.Substring(0,78)+[char]0x2026 }
    if(@('open','partial') -contains $svq -and -not $rq2.StartsWith('🛑') -and $scq -notmatch '\[A:'){
      if($svq -eq 'partial' -and $LR -match '在办|在建|进行中|建造中'){ $poolEx+=,([ordered]@{no=$cq[0];dom=$dvq;why='partial 但开头片段自陈在办';lead=(Get-LeadSeg $rq2)}) }
      else { $fl=''; if($svq -eq 'partial' -and $LR -match '^\s*✅'){ $fl='字段=partial 但首标记写 ✅（以字段为准，#308 决策点 1）' }
        $oo=$null; if($op.ContainsKey($cq[0])){ $oo=$op[$cq[0]] }
        $pool+=,([ordered]@{no=$cq[0];dom=$dvq;st=$svq;task=$tk;flag=$fl;op=$oo}) } } }
  else { $poolDeg+=,$cq[0] }
}
$rep=@(); $rd=Join-Path $root '1-转型规划\0-全景路线图'
if(Test-Path -LiteralPath $rd){ $rep=@(Get-ChildItem -LiteralPath $rd -Filter '拆件巡逻报告-*.md' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 4 | ForEach-Object { $_.BaseName + ' ｜ ' + $_.LastWriteTime.ToString('MM-dd HH:mm') }); Set-Src 'rep' $true '' } else { Set-Src 'rep' $false '目录不存在：1-转型规划\0-全景路线图' }
# ===== sweep 执行结果统计（队列 #232，2026-08-04 环境保障线）=====
# 判据必须【行首锚定】：日志正文的批次说明文字里含「非 clean」「schannel」字样，
# 用整块 -match 会把它们误判成本轮态（2026-08-04 实测：近 24h 52 轮全被误报为让路）。
# 另：$cb 是 List[string]，`$cb -ne $null` 在集合上被重载为「元素级过滤」，空表即 false
# → 所有行都收不进去、四态全归「其他」。故一律写 `$null -ne $cb`（标量在左）。
$sweep=''; $sstat=$null; $sp=Join-Path $root 'reports\sweep-commit.log'
if(-not $rootOk){ Set-Src 'sweep' $false ('仓库根不存在：'+$root) } elseif(Test-Path -LiteralPath $sp){ Set-Src 'sweep' $true '' } else { Set-Src 'sweep' $false '文件不存在：reports\sweep-commit.log' }
if(Test-Path -LiteralPath $sp){
  $sl=Get-Content -LiteralPath $sp -Encoding UTF8
  $sweep=(($sl|Select-Object -Last 6) -join "`n")
  $rr=New-Object System.Collections.Generic.List[object]; $ct=$null; $cb=$null
  foreach($ln in $sl){
    if($ln -match '^=== sweep 运行 (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC ==='){
      if($null -ne $ct){ $rr.Add([pscustomobject]@{ts=$ct;body=$cb}) }
      $ct=[datetime]::ParseExact($matches[1],'yyyy-MM-dd HH:mm',$null); $cb=New-Object System.Collections.Generic.List[string]
    } elseif($null -ne $cb){ $cb.Add($ln) }
  }
  if($null -ne $ct){ $rr.Add([pscustomobject]@{ts=$ct;body=$cb}) }
  $ks=New-Object System.Collections.Generic.List[object]
  foreach($r in $rr){
    $bd=@($r.body); $k='其他'
    if($bd -match '^§二无待处理批次'){$k='空转'}
    if($bd -match '^✓ 批次 .*已落库并推送'){$k='落库'}
    if($bd -match '^⚠ (起跑探测到共享编辑锁|编辑锁占用中)'){$k='锁忙'}
    if($bd -match '^⚠ 非 clean：'){$k='让路'}
    if(($bd -match '^✗ ') -or ($bd -match '^⚠ git fetch origin master 失败')){$k='推送失败'}
    $ks.Add([pscustomobject]@{ts=$r.ts;kind=$k;fz=@($bd|Where-Object{$_ -match '^⚠ 状态列模糊'}).Count;body=$bd})
  }
  $mk={ param($s) $o=[ordered]@{}; foreach($k in @('落库','空转','让路','锁忙','推送失败','其他')){ $c=@($s|Where-Object{$_.kind -eq $k}).Count; if($c -gt 0){$o[$k]=$c} }; $o }
  $nu=(Get-Date).ToUniversalTime()
  $L=$ks[$ks.Count-1]
  $cy=0; for($i=$ks.Count-1;$i -ge 0;$i--){ if($ks[$i].kind -eq '让路'){$cy++} else {break} }
  $bk=@(); if($L.kind -eq '让路'){ $bk=@($L.body|Where-Object{$_ -match '^\s+- '}|ForEach-Object{$_.Trim().Substring(2)}) }
  $sstat=[ordered]@{ total=$ks.Count; last=$L.kind; lastUtc=$L.ts.ToString('yyyy-MM-dd HH:mm'); lastLoc=$L.ts.AddHours(8).ToString('MM-dd HH:mm'); ageMin=[int]($nu-$L.ts).TotalMinutes; fuzzy=$L.fz; consecYield=$cy; blocked=$bk; all=(& $mk $ks); d1=(& $mk @($ks|Where-Object{$_.ts -gt $nu.AddDays(-1)})); d7=(& $mk @($ks|Where-Object{$_.ts -gt $nu.AddDays(-7)})) }
}
# 队列 #22 v1 ③：最近 N 个 commit 的首行 —— 与 #302 主判据同源（只认首行 type(scope)，不认 body）。
$gl=@(); $gitWhy=''
if(-not $rootOk){ $gitWhy='仓库根不存在：'+$root } else { try{ $gl=@(git -C $root log -10 --format='%h|%ad|%s' --date=format:'%m-%d %H:%M' 2>$null) }catch{ $gl=@(); $gitWhy='git 调用异常：'+$_.Exception.Message } }
if($gitWhy -eq '' -and $gl.Count -eq 0){ $gitWhy='git log 无输出（非 git 仓库，或 git 不在 PATH）' }
Set-Src 'git' ($gitWhy -eq '') $gitWhy
# 队列 #22 v1 ④：四服务存活。🔴 必须区分「服务挂了」与「本机不在网段」——
# 2026-08-07 实测：本机 IPv4=192.168.3.35（不在 192.168.100.x），四端口全超时；
# 若直接显示为「服务异常」，会误判成保供看板挂了，而姚祖怡当时刚收到复核信。
# 故：不在 192.168.100.x 网段时**根本不发起探测**，直接标注「无法判定」（顺带省掉 4 次超时等待）。
# 🔴 2026-08-31：原 catch 直接吞成空数组 ⇒ $lan=false ⇒ 页面说「本机不在 LAN」。
#    但「枚举网卡失败」与「确实不在该网段」是两件事，前者说成后者就是编了个理由。记录真因。
$ips=@(); $ipsWhy=''; try{ $ips=@(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '127.*' } | ForEach-Object { $_.IPAddress }) }catch{ $ips=@(); $ipsWhy='Get-NetIPAddress 异常：'+$_.Exception.Message }
$lan=(@($ips | Where-Object { $_ -like '192.168.100.*' }).Count -gt 0)
$svc=[ordered]@{}
if($lan){ foreach($pp in 8091,8092,8093,8094){ try{ $rr2=Invoke-WebRequest -Uri ('http://192.168.100.51:' + $pp + '/api/ping') -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop; $svc["$pp"]=$(if($rr2.StatusCode -eq 200){'up'}else{'http' + $rr2.StatusCode}) }catch{ $svc["$pp"]='down' } } }
$net=[ordered]@{ lan=$lan; ips=($ips -join ', '); svc=$svc; ipsWhy=$ipsWhy }
$mt=[ordered]@{}
foreach($rel in @('1-转型规划\0-全景路线图\session接力-Phase1收口.md','CLAUDE.md','1-转型规划\0-全景路线图\跨桌任务队列-机制环境.md','1-转型规划\0-全景路线图\跨桌任务队列-业务场景.md','1-转型规划\0-全景路线图\文档台账-自动生成.md')){
  $p=Join-Path $root $rel
  if(Test-Path -LiteralPath $p){ $mt[(Split-Path $rel -Leaf)] = (Get-Item -LiteralPath $p).LastWriteTime.ToString('MM-dd HH:mm') }
}
$ledger = Read-Src 'ledger' '1-转型规划\0-全景路线图\文档台账-自动生成.md'
$lgen=''; $ltot=''; $lpend=''
$ml=[regex]::Match($ledger,'> 生成于 ([^｜\r\n]+)')
if($ml.Success){ $lgen=$ml.Groups[1].Value.Trim() }
$mc=[regex]::Match($ledger,'共 (\d+) 份 md，(\d+) 份待补状态头')
if($mc.Success){ $ltot=$mc.Groups[1].Value; $lpend=$mc.Groups[2].Value }
$lcats=@([regex]::Matches($ledger,'(?m)^## (.+?)（(\d+)）') | ForEach-Object { $_.Groups[1].Value + '（' + $_.Groups[2].Value + '）' })
# 🔴 2026-08-10 队列 #312：WIP 上限**改为直读权威源**，不再在本文件写死数字。
# 原为 `wipCap=8`——2026-08-09 协议〇.9 上调到 16 后本处未同步；同日 A4 只改了下方 JS 的
# `st.wipCap==null?16` 兜底，而 PS 始终**给得出**值（8），兜底永不生效 ⇒ 页面上分母仍是 8。
# 这正是本项目记的「工具静默回退」：源码看着改了、渲染值没变，且只核源码文本看不出来。
# ⇒ 直接从 工具-共享文档编辑锁.py::MECHANISM_WIP_CAP_DEFAULT 取值，消灭第三份副本，此后不会再过时。
# 🔴 2026-08-31：上限**只认权威源，读不到就留 $null**，由 JS 显式说「上限无法核验」。
#    原写死 `$wcap=16` 的兜底正是 #312 记的过时副本形态（本机实测权威值现为 22）——
#    宁可不显示分母，也不拿一个可能过时的数字去判「超限/未超」。
$wcap=$null; $lockPy = Read-Src 'lock' '0-学习与工具\工具-共享文档编辑锁.py'
$mwc=[regex]::Match($lockPy,'(?m)^MECHANISM_WIP_CAP_DEFAULT\s*=\s*(\d+)'); if($mwc.Success){ $wcap=[int]$mwc.Groups[1].Value } elseif($src['lock'].ok){ Set-Src 'lock' $false '字段未匹配：工具-共享文档编辑锁.py 内无 MECHANISM_WIP_CAP_DEFAULT' }
$out=[ordered]@{ root=$root; rootOk=$rootOk; src=$src; now=(Get-Date -Format 'yyyy-MM-dd HH:mm'); snapshot=$snap; next=$next; letters=$letters; deadlines=$deadlines; domains=$domains; qk=$qk; qp=$qp; qb=$qb; qbFuzzy=$qbFuzzy; qkSkip=@($qkSkip); qbSkip=@($qbSkip); qstat=[ordered]@{groups=$qg;conflict=@($qconf);wipMeta=$wipMeta;wipBiz=$wipBiz;wipCap=$wcap}; pool=@($pool); poolEx=@($poolEx); poolDeg=@($poolDeg); opNewest=$opNewest; net=$net; gl=$gl; hwm=$hwm; rep=$rep; sweep=$sweep; sweepStat=$sstat; ledger=[ordered]@{gen=$lgen;total=$ltot;pending=$lpend;cats=$lcats}; mtime=$mt }
Write-Output ('@@JSON@@' + (ConvertTo-Json $out -Compress -Depth 8))