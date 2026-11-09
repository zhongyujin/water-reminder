"""A single-instance Windows desktop reminder. No external dependencies."""
import argparse
import ctypes
import json
import math
import msvcrt
import os
from pathlib import Path
import sys
import time
import tkinter as tk
import uuid
from timer_model import INTERVAL, ReminderState, load, save

APP_TITLE = "饮水小憩 · 每30分钟喝水提醒"
DATA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WaterBreak"
STATE = DATA / "state.json"
RUNTIME = DATA / "runtime.json"
COMMANDS = DATA / "commands"
PAPER = "#F3F0E5"
INK = "#304636"
SAGE = "#7D8C69"
RED = "#A9523C"
FONT = "Microsoft YaHei UI"
SERIF = "SimSun"


def event(name, **values):
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / "events.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps({"event": name, "timestamp": time.time(), **values}, ensure_ascii=False) + "\n")


def acquire_lock():
    DATA.mkdir(parents=True, exist_ok=True)
    handle = (DATA / "instance.lock").open("a+b")
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return handle
    except OSError:
        handle.close()
        return None


def send_command(action):
    COMMANDS.mkdir(parents=True, exist_ok=True)
    save(COMMANDS / (str(time.time_ns()) + "-" + uuid.uuid4().hex + ".json"), {"action": action})


def release_lock(handle):
    try:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        handle.close()


class WaterApp:
    def __init__(self, args):
        self.args = args
        self.state = load(STATE)
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.configure(bg=PAPER)
        self.root.geometry("570x510")
        self.root.minsize(520, 480)
        self.root.protocol("WM_DELETE_WINDOW", self.minimize)
        self.overlay = None
        self.test_overlay = False
        self.previous_root_state = "normal"
        self.demo_due = time.monotonic() + args.demo_after if args.demo_after else None
        self.last_runtime = 0
        self.build_dashboard()
        self.root.update_idletasks()
        width = max(570, self.root.winfo_reqwidth())
        height = max(510, self.root.winfo_reqheight())
        self.root.geometry(f"{width}x{height}")
        self.persist()
        event("started", interval_seconds=INTERVAL, enabled=self.state.enabled, pid=os.getpid())
        if args.ensure_running:
            self.root.after(100, self.root.iconify)
        if args.test_reminder:
            self.root.after(500, lambda: self.show_reminder(test=True))
        self.root.after(150, self.tick)

    def label(self, parent, text="", size=12, color=INK, serif=False, **kwargs):
        return tk.Label(parent, text=text, bg=PAPER, fg=color,
                        font=(SERIF if serif else FONT, size), **kwargs)

    def button(self, parent, text, command, primary=False, **kwargs):
        return tk.Button(parent, text=text, command=command, font=(FONT, 11),
                         bg=INK if primary else "#E5E9DA", fg=PAPER if primary else INK,
                         activebackground="#50664A", activeforeground="white", relief="flat",
                         borderwidth=0, padx=18, pady=11, cursor="hand2", takefocus=True, **kwargs)

    def build_dashboard(self):
        outer = self.dashboard = tk.Frame(self.root, bg=PAPER, padx=34, pady=26)
        outer.pack(expand=True, fill="both")
        top = tk.Frame(outer, bg=PAPER)
        top.pack(fill="x")
        self.label(top, "饮 水 小 憩", size=24, serif=True).pack(side="left")
        self.label(top, "每 30 分钟", size=10, color=SAGE).pack(side="right")
        self.label(outer, "把忙碌放一放，记得喝点水。", color=SAGE, size=10).pack(pady=(17, 20))
        self.label(outer, "距离下次全屏提醒", color=SAGE, size=10).pack()
        self.clock = self.label(outer, "30:00", size=58)
        self.clock.pack(pady=(5, 0))
        self.status = self.label(outer, "提醒已开启", color=SAGE, size=10)
        self.status.pack(pady=(0, 16))
        actions = tk.Frame(outer, bg=PAPER)
        actions.pack()
        self.toggle_button = self.button(actions, "暂停提醒", self.toggle, primary=True)
        self.toggle_button.pack(side="left", padx=5)
        self.button(actions, "测试全屏", lambda: self.show_reminder(test=True)).pack(side="left", padx=5)
        self.count_label = self.label(outer, "", color=SAGE, size=10)
        self.count_label.pack(pady=(22, 8))
        self.label(outer, "关闭窗口会最小化，计时继续。\n全屏时按 Esc，可稍后 5 分钟再提醒。", color="#818773", size=9, justify="center").pack()
        footer = tk.Frame(outer, bg=PAPER)
        footer.pack(fill="x", pady=(19, 0))
        self.button(footer, "最小化继续运行", self.minimize).pack(side="left")
        tk.Button(footer, text="退出工具", command=self.quit, relief="flat", bg=PAPER,
                  fg="#8D7667", font=(FONT, 9), cursor="hand2").pack(side="right")

    def persist(self):
        save(STATE, self.state)

    def runtime(self):
        full = bool(self.overlay and self.overlay.winfo_exists())
        info = {"pid": os.getpid(), "running": True, "enabled": self.state.enabled,
                "interval_seconds": INTERVAL, "next_due": self.state.next_due,
                "fullscreen_visible": full, "test_reminder": self.test_overlay,
                "updated_at": time.time()}
        if full:
            info.update({"window_width": self.root.winfo_width(),
                         "window_height": self.root.winfo_height(),
                         "screen_width": self.root.winfo_screenwidth(),
                         "screen_height": self.root.winfo_screenheight(),
                         "fullscreen": bool(self.root.attributes("-fullscreen")),
                         "topmost": bool(self.root.attributes("-topmost"))})
        save(RUNTIME, info)

    def tick(self):
        now = time.time()
        previous_day = self.state.day
        self.state.refresh_day(now)
        if previous_day != self.state.day:
            self.persist()
        left = math.ceil(self.state.seconds_left(now))
        self.clock.config(text=f"{left // 60:02d}:{left % 60:02d}")
        self.status.config(text="提醒已开启 · 到时全屏显示" if self.state.enabled else "已暂停 · 点击继续可恢复计时")
        self.toggle_button.config(text="暂停提醒" if self.state.enabled else "继续提醒")
        self.count_label.config(text=f"今天已确认喝水 {self.state.drinks} 次")
        if self.demo_due and time.monotonic() >= self.demo_due:
            self.demo_due = None
            event("test_timer_fired")
            self.show_reminder(test=True)
        elif self.state.due(now) and self.overlay is None:
            self.show_reminder(test=False)
        if COMMANDS.exists():
            for path in sorted(COMMANDS.glob("*.json")):
                try:
                    command = json.loads(path.read_text(encoding="utf-8")).get("action")
                    path.unlink()
                    if command == "show":
                        self.root.deiconify()
                        self.root.lift()
                    elif command == "test":
                        self.show_reminder(test=True)
                    elif command == "remind" and self.state.enabled:
                        self.show_reminder(test=False)
                except (OSError, ValueError):
                    pass
        if now - self.last_runtime >= 3:
            self.runtime()
            self.last_runtime = now
        self.root.after(250, self.tick)

    def toggle(self):
        now = time.time()
        if self.state.enabled:
            self.state.pause(now)
            event("paused")
        else:
            self.state.resume(now)
            event("resumed")
        self.persist()

    def minimize(self):
        self.root.iconify()

    def draw_glass(self, canvas, width, height):
        cx, cy = width / 2, height / 2
        canvas.create_oval(cx-69, cy+39, cx+69, cy+57, fill="#E1E4D3", outline="")
        canvas.create_polygon(cx-46, cy-45, cx+46, cy-45, cx+34, cy+42, cx-34, cy+42,
                              fill="#E6EBDE", outline=INK, width=3, joinstyle="round")
        canvas.create_polygon(cx-39, cy-5, cx+39, cy-5, cx+33, cy+39, cx-33, cy+39,
                              fill="#AFC7B9", outline="")
        canvas.create_arc(cx-40, cy-13, cx+40, cy+4, start=0, extent=180,
                          style="arc", outline="#6D9584", width=2)
        canvas.create_line(cx-27, cy-70, cx-33, cy-84, cx-25, cy-102, smooth=True, fill=SAGE, width=2)
        canvas.create_line(cx, cy-65, cx-6, cy-83, cx+2, cy-105, smooth=True, fill=SAGE, width=2)
        canvas.create_line(cx+27, cy-70, cx+21, cy-84, cx+29, cy-102, smooth=True, fill=SAGE, width=2)

    def show_reminder(self, test=False):
        if self.overlay is not None:
            self.root.lift()
            return
        self.test_overlay = test
        self.previous_root_state = self.root.state()
        self.previous_geometry = self.root.geometry()
        self.dashboard.pack_forget()
        self.root.deiconify()
        self.root.title("喝水提醒 · 测试" if test else "该喝水了 · 饮水小憩")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.dismiss)
        self.root.bind("<Escape>", lambda _event: self.dismiss())
        window = self.overlay = tk.Frame(self.root, bg=PAPER)
        window.pack(expand=True, fill="both")
        width, height = window.winfo_screenwidth(), window.winfo_screenheight()
        tk.Button(window, text="Esc 退出全屏  ×", command=self.dismiss, bg=PAPER,
                  fg=SAGE, relief="flat", font=(FONT, 11), padx=14, pady=10,
                  cursor="hand2").place(relx=1, x=-30, y=22, anchor="ne")
        self.label(window, "饮 水 小 憩  /  A MOMENT FOR YOURSELF", size=10, color=SAGE).place(relx=.5, rely=.11, anchor="center")
        content = tk.Frame(window, bg=PAPER)
        content.place(relx=.5, rely=.48, anchor="center")
        canvas = tk.Canvas(content, width=240, height=190, bg=PAPER, highlightthickness=0)
        canvas.pack()
        self.draw_glass(canvas, 240, 190)
        self.label(content, "该喝水了", size=max(38, min(72, height // 14)), serif=True).pack(pady=(0, 17))
        self.label(content, "起身，喝几口水。\n也给眼睛和身体留一小会儿休息。", size=max(12, min(17, height // 55)),
                   color=SAGE, justify="center").pack(pady=(0, 30))
        actions = tk.Frame(content, bg=PAPER)
        actions.pack()
        self.confirm_button = self.button(actions, "完成测试" if test else "喝过水了 · 重新计时", self.confirm, primary=True)
        self.confirm_button.pack(side="left", padx=8)
        self.button(actions, "返回计时" if test else "5 分钟后提醒", self.dismiss).pack(side="left", padx=8)
        self.label(window, "测试提醒 · 不记录喝水次数，也不改变正式计时" if test else "每 30 分钟，记得照顾自己。", size=10, color=SAGE).place(relx=.5, rely=.88, anchor="center")
        self.confirm_button.focus_set()
        window.lift()
        self.root.after(200, self.runtime)
        event("fullscreen_opened", test=test)
        try:
            window.bell()
        except tk.TclError:
            pass

    def close_overlay(self):
        if self.overlay:
            self.overlay.destroy()
            self.overlay = None
        self.root.attributes("-fullscreen", False)
        self.root.attributes("-topmost", False)
        self.root.unbind("<Escape>")
        self.root.title(APP_TITLE)
        self.root.protocol("WM_DELETE_WINDOW", self.minimize)
        self.root.geometry(self.previous_geometry)
        self.dashboard.pack(expand=True, fill="both")
        if self.previous_root_state == "iconic":
            self.root.iconify()
        else:
            self.root.deiconify()
        self.test_overlay = False
        self.runtime()

    def confirm(self):
        test = self.test_overlay
        if not test:
            self.state.drank(time.time())
            self.persist()
        event("reminder_confirmed", test=test, next_due=self.state.next_due)
        self.close_overlay()

    def dismiss(self):
        test = self.test_overlay
        if not test:
            self.state.snooze(time.time())
            self.persist()
        event("reminder_dismissed", test=test, snooze_seconds=0 if test else 300)
        self.close_overlay()

    def quit(self):
        self.state.pause(time.time())
        self.persist()
        event("exited_by_user")
        save(RUNTIME, {"running": False, "enabled": False, "updated_at": time.time()})
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ensure-running", action="store_true")
    parser.add_argument("--test-reminder", action="store_true")
    parser.add_argument("--remind-now", action="store_true")
    parser.add_argument("--demo-after", type=float)
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    if args.ensure_running and STATE.exists() and not load(STATE).enabled:
        return
    lock = acquire_lock()
    if lock is None:
        if args.test_reminder or args.demo_after:
            send_command("test")
        elif args.remind_now:
            send_command("remind")
        elif not args.ensure_running:
            send_command("show")
        return
    try:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
        app = WaterApp(args)
        if args.remind_now:
            app.root.after(500, lambda: app.show_reminder(test=False))
        app.root.mainloop()
    except Exception as error:
        event("error", error=repr(error))
        raise
    finally:
        release_lock(lock)


if __name__ == "__main__":
    main()
