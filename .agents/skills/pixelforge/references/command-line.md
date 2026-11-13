# 连接常驻 PixForge

W 是正在编辑的工程工作区，R 默认位于 `W/.runtime/pixelforge-desktop`。从固定便携目录双击启动时，W 默认是 EXE 旁的 `workspace`；指定过 `--workspace` 或 `--runtime` 时沿用指定位置。已有会话直接读取 `R/commands.json`，核对其中的工作区和会话目录，再用会话地址和凭据连接。`project info` 返回当前实例的软件和公开命令版本。首次启动或进程已退出时才需要下面的启动步骤；重启后重新读取连接文件。

```powershell
# 首次启动。使用项目指定的固定 EXE；没有固定安装时使用技能随包的 EXE。
$pf = '<固定安装目录>/PixForgeNative.exe'
$W = '<消费项目绝对路径>'
$R = Join-Path $W '.runtime/pixelforge-desktop'
$p = Start-Process -FilePath $pf -WindowStyle Hidden -PassThru -ArgumentList ('serve --workspace "{0}" --runtime "{1}"' -f $W,$R)
$record = Join-Path $R 'commands.json'
$deadline = [DateTime]::UtcNow.AddSeconds(20)
do {
    if ($p.HasExited) { throw "PixForge 启动退出：$($p.ExitCode)" }
    if (Test-Path -LiteralPath $record) {
        $c = Get-Content -LiteralPath $record -Raw -Encoding utf8 | ConvertFrom-Json
        if ($c.pid -eq $p.Id) { break }
    }
    if ([DateTime]::UtcNow -ge $deadline) { throw 'PixForge 尚未就绪' }
    Start-Sleep -Milliseconds 80
} while ($true)
```

已有会话用 PowerShell 7（`pwsh`）直接请求。用 `ConvertFrom-Json -AsHashtable` 解析响应正文，调色板里的 `A` 和 `a` 是两个不同的颜色键。

```powershell
$c = Get-Content -LiteralPath (Join-Path $R 'commands.json') -Raw -Encoding utf8 | ConvertFrom-Json
$h = @{ 'X-PixForge-Session' = $c.token }
function Invoke-PixForge($Group, $Command, [hashtable]$Params = @{}) {
    $json = @{group=$Group; command=$Command; params=$Params} | ConvertTo-Json -Depth 64 -Compress
    $http = Invoke-WebRequest -Method Post -Uri $c.url -Headers $h -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($json))
    $http.Content | ConvertFrom-Json -AsHashtable
}
$state = Invoke-PixForge project state
```

`GET` 同一 URL 列出命令分组；附加 `/canvas` 列出该组动作，附加 `/canvas/draw` 取得参数类型。命令都以 `POST` 发送：`group` 是分组，`command` 是动作，`params` 是可省略的 JSON 对象。先看响应的 `ok`，失败时读取 `code/error/issues`。HTTP 200 也可能包含命令错误；鉴权、请求格式和路径错误由 HTTP 状态表示。图像返回 `preview_path`，动画播放器返回 `html_path`。

例如，把草稿的多笔绘制作为一次操作提交：

```powershell
$result = Invoke-PixForge canvas draw @{
    commands = Get-Content -LiteralPath $drawingFile -Raw -Encoding utf8
    expected_document_id = $state.document_id
    expected_revision = $state.revision
}
```

其他参考中的 `group action --request-file 文件` 表示把文件中的 JSON 对象作为 `params`；`--commands-file` 对应 `params.commands` 的文本，`--observed-file` 对应 `params.observed` 的 JSON 对象。标志中的连字符改为参数名中的下划线。HTTP 请求直接使用这些值；需要传递上一条结果时，使用内存中的响应或由调用方保存结果文件。单次 CLI 仍可供已有脚本使用。

`workbench open` 打开或复用该实例中的窗口，`workbench close` 只关闭窗口。需要结束整个会话时，通过 `project shutdown` 传入当前工程 ID 和 revision。
