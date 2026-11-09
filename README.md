# 饮水小憩

Windows 桌面喝水提醒工具。启动后每 30 分钟弹出主屏全屏提醒，支持暂停、稍后提醒和喝水次数记录。使用 Python 标准库，无需安装第三方依赖。

## 下载与运行

1. 安装适用于 Windows 的 Python 3.10 或更新版本，保留安装程序默认的 Tcl/Tk（Tkinter）组件。
2. 下载本仓库 ZIP 并解压，或使用 Git 克隆仓库。
3. 在项目目录运行：

```powershell
pythonw water_reminder.pyw
```

也可以用 `python water_reminder.pyw` 启动并查看控制台错误信息。请把 `water_reminder.pyw` 和 `timer_model.py` 放在同一目录。

当前电脑已创建桌面「喝水提醒」快捷方式；下载到其他电脑后，可为上述启动命令自行创建快捷方式。

## 使用

- 「喝过水了」：记录一次喝水，从确认时重新计时 30 分钟。
- 「5 分钟后提醒」或全屏时按 Esc：退出全屏，5 分钟后再次提醒。
- 「暂停提醒」：保留剩余时间，点击「继续提醒」后接着计时。
- 「测试全屏」：只预览，不增加次数、不改变正式倒计时。
- 关闭主窗口会最小化到任务栏，提醒继续运行。
- 「退出工具」会保存暂停状态并关闭。再次启动后点击「继续提醒」即可恢复。
- 重复启动会唤起已有窗口，不会重复开启多个计时器。

计时不依赖浏览器页面保持打开。电脑关机时无法弹出提醒；重开电脑后需要再次启动工具。本仓库不安装开机自启动或后台计划任务。

## 本地数据

设置和运行状态保存在 `%LOCALAPPDATA%\WaterBreak`，包括计时状态、每日次数和事件日志，均保留在本机。每日次数按北京时间零点重置。

## 源码与测试

- `water_reminder.pyw`：Windows 桌面界面、全屏提醒和单实例运行。
- `timer_model.py`：计时规则及本地状态存储。
- `test_timer.py`：计时逻辑测试。

运行逻辑测试：

```powershell
python -m unittest test_timer -v
```

延时 3 秒显示测试提醒（正式提醒仍为 30 分钟）：

```powershell
pythonw water_reminder.pyw --demo-after 3
```

后台启动检查命令 `pythonw water_reminder.pyw --ensure-running` 可供外部调度器使用：已经运行时不重复启动，保存为暂停状态时不自动恢复。
