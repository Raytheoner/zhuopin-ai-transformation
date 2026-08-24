# ================================================================
#  assert-no-orphan-cr.ps1  —— 孤立 CR 断言器（队列 #355，2026-08-24）
#
#  用途：给两份计划任务注册脚本（register-decision-reminder-task.ps1 /
#  register-followup-dispatch-task.ps1）在**生成 wrapper 的那一刻**做写盘前
#  与写盘后自检——正文里不得出现「孤立 CR」（0x0D 未跟 0x0A）。
#
#  为什么要有这个东西（#355 事故原文）：
#    生成器的 wrapper 模板原先是**双引号 here-string**（@" … "@），PowerShell
#    会对其内容做转义与插值。模板注释里写了反引号包裹的标识符
#    `resolve_repo_root`，其中「反引号 + r」被当成 CR 转义符 ⇒ 生成物第 933
#    字节处出现一个孤立 CR，`resolve_repo_root` 变成 `<CR>esolve_repo_root`。
#    PowerShell 把孤立 CR 当断行 ⇒ 注释被就地截断，后半截
#    「esolve_repo_root 会以这个路径为」被当命令执行，每日 08:30 必报
#    CommandNotFoundException。
#
#  🔑 这个缺陷之所以能藏住，是因为它**不产生任何失败信号**：stdout 正常、
#    exit 0、状态文件正确，只有 stderr 多一条没人看的异常。所以防线必须挂在
#    「生成侧」这个唯一咽喉上、且必须 fail-loud——事后在生成物上查等于没查
#    （生成物是 gitignore 件，没人会去读它）。
#
#  同族：根 CLAUDE.md「工具静默回退」一节；memory
#  feedback_bash_heredoc_backslash_mangling（反斜杠 f 被当换页符吃掉路径）。
#  共同点都是**不报错，只是悄悄换掉了一个字节**。
#
#  用法（在同目录脚本内 dot-source）：
#    . (Join-Path $PSScriptRoot "assert-no-orphan-cr.ps1")
#    Assert-NoOrphanCR -Text $wrapperContent -Label "xxx 模板"     # 写盘前
#    Assert-NoOrphanCR -Path $WRAPPER        -Label "已写盘的 xxx" # 写盘后反查
# ================================================================

function Assert-NoOrphanCR {
    [CmdletBinding()]
    param(
        # 出错信息里用来指认「是谁不合格」，必填——省了它，报错文本会退化成
        # 一句放之四海皆准的废话，跟没报一样。
        [Parameter(Mandatory = $true)][string] $Label,

        # 二选一：-Text 查内存里的字符串（写盘前）；-Path 查落盘文件（写盘后反查）。
        [string] $Text,
        [string] $Path
    )

    if ($PSBoundParameters.ContainsKey('Path') -and $PSBoundParameters.ContainsKey('Text')) {
        throw "Assert-NoOrphanCR：-Text 与 -Path 只能给一个（$Label）。"
    }

    if ($PSBoundParameters.ContainsKey('Path')) {
        # 🔴 [System.IO.File]::* 的相对路径按**宿主进程 CWD**解析，不是按
        # PowerShell 的当前位置——传相对路径会静默读到别的文件（根 CLAUDE.md
        # 「工具静默回退」已知实例之一）。故此处强制转绝对路径再读。
        $absolute = (Resolve-Path -LiteralPath $Path).ProviderPath
        $bytes = [System.IO.File]::ReadAllBytes($absolute)
        $source = $absolute
    }
    else {
        # 写盘用的是 -Encoding UTF8，故按 UTF8 取字节，与落盘形态同口径。
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
        $source = "(内存字符串)"
    }

    for ($i = 0; $i -lt $bytes.Length; $i++) {
        if ($bytes[$i] -ne 0x0D) { continue }
        if (($i -lt $bytes.Length - 1) -and ($bytes[$i + 1] -eq 0x0A)) { continue }  # 正常 CRLF

        # 截一小段上下文，让报错能直接指到人眼可读的位置。
        $from = [Math]::Max(0, $i - 40)
        $len  = [Math]::Min(80, $bytes.Length - $from)
        $near = [System.Text.Encoding]::UTF8.GetString($bytes, $from, $len)
        throw ("孤立 CR 检查未通过（队列 #355）：$Label 在第 $i 字节处出现 0x0D 未跟 0x0A。" +
               "来源：$source；附近内容：<<$near>>。" +
               "最常见成因＝双引号 here-string 里写了反引号 + r（PowerShell 会把它当 CR 转义符），" +
               "改用单引号 here-string ＋ 占位符 .Replace() 即可。已中止，未继续。")
    }
}
