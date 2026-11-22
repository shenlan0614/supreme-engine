#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UNG220Z 光猫工具 - Android 原生界面（Kivy）。"""
import re
import threading
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

import ung220z as U

LABELS = [
    ("telnet", "Telnet / root shell"),
    ("web_admin", "Web 超管"),
    ("web_user", "Web 普通用户"),
    ("pppoe", "PPPoE 宽带"),
    ("root", "Linux root"),
]


class Field(BoxLayout):
    def __init__(self, label, value="", password=False, width=dp(108), **kw):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(46), spacing=dp(6), **kw)
        self.add_widget(Label(text=label, size_hint_x=None, width=width,
                              font_size=dp(13), halign="left"))
        self.input = TextInput(text=value, password=password, multiline=False,
                               font_size=dp(15))
        self.add_widget(self.input)


class Check(BoxLayout):
    def __init__(self, label, checked=False, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(38), spacing=dp(4), **kw)
        self.cb = CheckBox(active=checked, size_hint_x=None, width=dp(34))
        self.add_widget(self.cb)
        self.add_widget(Label(text=label, font_size=dp(13), halign="left"))


class Root(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(6), **kw)
        self.running = False

        scroll = ScrollView()
        box = BoxLayout(orientation="vertical", spacing=dp(7),
                        size_hint_y=None, pad=dp(4))
        box.bind(minimum_height=box.setter("height"))
        scroll.add_widget(box)
        self.add_widget(scroll)

        box.add_widget(Label(
            text="UNG220Z 光猫工具\n用户名/密码在光猫背面贴纸上",
            font_size=dp(15), size_hint_y=None, height=dp(52),
            halign="center"))

        self.f_ip = Field("光猫地址", "192.168.1.1")
        self.f_user = Field("用户名", "user")
        self.f_pw = Field("密码", password=True)
        self.f_tu = Field("Telnet 用户", "CMCCAdmin")
        self.f_tp = Field("Telnet 口令", password=True)
        for f in (self.f_ip, self.f_user, self.f_pw, self.f_tu, self.f_tp):
            box.add_widget(f)

        self.c_release = Check("释放残留 Web 会话（推荐）", True)
        self.c_unlock = Check("会话锁住时重启 httpd")
        box.add_widget(self.c_release)
        box.add_widget(self.c_unlock)

        self.btn = Button(text="开始提取", size_hint_y=None, height=dp(50),
                          font_size=dp(17))
        self.btn.bind(on_press=self.on_run)
        box.add_widget(self.btn)

        self.status = Label(text="等待开始", size_hint_y=None, height=dp(30),
                            font_size=dp(13))
        box.add_widget(self.status)

        box.add_widget(Label(text="实时日志", size_hint_y=None, height=dp(26),
                             font_size=dp(13), halign="left"))
        self.logs = Label(text="尚未开始", font_size=dp(11),
                          size_hint_y=None, height=dp(180),
                          text_size=(None, None), valign="top", halign="left")
        self.logs.bind(width=lambda _, w: setattr(self.logs, "text_size", (w - dp(8), None)))
        box.add_widget(self.logs)

        box.add_widget(Label(text="凭据汇总（点击条目复制）", size_hint_y=None,
                             height=dp(28), font_size=dp(13), halign="left"))
        self.results = GridLayout(cols=1, size_hint_y=None, spacing=dp(2))
        self.results.bind(minimum_height=self.results.setter("height"))
        box.add_widget(self.results)

        box.add_widget(Label(
            text="仅用于你自己的设备。口令约 15 分钟轮换，失效后重跑即可。",
            font_size=dp(11), size_hint_y=None, height=dp(40), halign="center"))

    # ---------- UI ----------
    def say(self, text):
        Clock.schedule_once(lambda dt: setattr(self.status, "text", text), 0)

    def append_log(self, line):
        def upd(dt):
            self.logs.text = (self.logs.text if self.logs.text != "尚未开始" else "") + line + "\n"
        Clock.schedule_once(upd, 0)

    def log(self, tag, msg):
        self.append_log("[%s] %-6s %s" % (time.strftime("%H:%M:%S"), tag, msg))

    def show_results(self, rows):
        def upd(dt):
            self.results.clear_widgets()
            for label, user, pw in rows:
                row = BoxLayout(orientation="horizontal", size_hint_y=None,
                                height=dp(42), spacing=dp(2))
                txt = ("%s  %s" % (user, pw)).strip()
                row.bind(on_touch_down=lambda w, touch, t=txt:
                         self.copy(t) if w.collide_point(*touch.pos) and touch.is_tap
                         else False)
                row.add_widget(Label(text=label, font_size=dp(11),
                                     size_hint_x=0.35, halign="left"))
                row.add_widget(Label(text=user, font_size=dp(11),
                                     size_hint_x=0.22, halign="left"))
                row.add_widget(Label(text=pw, font_size=dp(11),
                                     halign="left", shorten=True))
                self.results.add_widget(row)
            self.results.height = max(dp(42) * len(rows), dp(42))
        Clock.schedule_once(upd, 0)

    def copy(self, text):
        try:
            Clipboard.copy(text)
            self.say("✓ 已复制：" + text[:28])
        except Exception as exc:
            self.say("复制失败：" + str(exc))

    # ---------- 流程 ----------
    def on_run(self, _):
        if self.running:
            return
        pw = self.f_pw.input.text.strip()
        if not pw:
            self.say("请先输入密码")
            return
        self.running = True
        self.btn.disabled = True
        self.btn.text = "提取中…"
        self.logs.text = ""
        self.results.clear_widgets()
        self.say("正在连接光猫…")

        params = dict(
            ip=self.f_ip.input.text.strip() or "192.168.1.1",
            user=self.f_user.input.text.strip() or "user",
            password=pw,
            telnet_user=self.f_tu.input.text.strip() or U.TELNET_USER,
            telnet_password=self.f_tp.input.text.strip(),
            no_release=not self.c_release.cb.active,
            unlock=self.c_unlock.cb.active,
        )
        threading.Thread(target=self.work, args=(params,), daemon=True).start()

    def work(self, p):
        U.log = self.log
        try:
            rows = self.extract(p)
            self.show_results(rows)
            self.say("✅ 提取完成，共 %d 条" % len(rows))
        except Exception as exc:
            self.log("ERROR", str(exc) or repr(exc))
            self.say("❌ 提取失败：" + str(exc))
        finally:
            def done(dt):
                self.running = False
                self.btn.disabled = False
                self.btn.text = "开始提取"
            Clock.schedule_once(done, 0)

    def extract(self, p):
        ip, user, pw = p["ip"], p["user"], p["password"]
        self.log("INFO", "会话开始  目标=%s  账户=%s" % (ip, user))

        if not U.probe_port(ip, 80):
            raise RuntimeError("网关不可达，请确认手机已连接该光猫 WiFi")
        self.log("PROBE", "TCP 80 → open")

        if not p.get("no_release"):
            self.log("INFO", "释放残留会话 → %s" %
                     ("ok" if U.release_session(ip) else "skip"))

        self.log("INFO", "请求开启 Telnet")
        U.enable_telnet(ip, user, pw, open_browser=False)

        if not U.probe_port(ip, 23):
            raise RuntimeError("23 端口未开放，请核对贴纸密码后重试")
        self.log("PROBE", "TCP 23 → open")

        tn = U.Telnet(ip)
        cands = [x for x in (p.get("telnet_password"),) if x]
        if pw not in cands:
            cands.append(pw)
        if not tn.login(p["telnet_user"], cands):
            tn.close()
            raise RuntimeError("Telnet 登录失败")
        if p.get("unlock") or U.web_state(ip) == "busy":
            if U.web_state(ip) == "busy":
                U.unlock_web(ip, tn)

        tn.run("sidbg 1 DB decry %s" % U.CFG_ENC)
        if not tn.run("ls %s" % U.CFG_DEC).strip():
            tn.close()
            raise RuntimeError("配置解密失败，设备型号可能不匹配")

        creds, wifi = {}, []
        for r in U.parse_rows(U.grab_table(tn, "DevAuthInfo")):
            self.log("DATA", "DevAuthInfo %s / %s" % (r.get("User"), r.get("Pass")))
            creds["web_admin" if r.get("Level") == "1" else "web_user"] = (
                r.get("User"), r.get("Pass"))
        for r in U.parse_rows(U.grab_table(tn, "TelnetUser")):
            self.log("DATA", "TelnetUser %s / %s" % (r.get("Username"), r.get("Password")))
        ts = U.grab_scalar(tn, "TS_UPwd")
        if ts:
            self.log("DATA", "TS_UPwd %s / %s" % (U.TELNET_USER, ts))
            creds["telnet"] = (U.TELNET_USER, ts)
        for r in U.parse_rows(U.grab_table(tn, "WANCPPP")):
            if r.get("UserName"):
                self.log("DATA", "WANCPPP %s / %s" % (r["UserName"], r.get("Password")))
                creds["pppoe"] = (r["UserName"], r.get("Password"))

        essid = {}
        for r in U.parse_rows(U.grab_table(tn, "WLANCfg")):
            if r.get("ESSID"):
                essid[r.get("ViewName", "")] = r["ESSID"]
        for r in U.parse_rows(U.grab_table(tn, "WLANPSK")):
            psk = r.get("KeyPassphrase")
            if not psk:
                continue
            vn = r.get("ViewName", "")
            ssid = essid.get(vn.rsplit(".PSK", 1)[0], vn)
            self.log("DATA", "WLANPSK %s / %s" % (ssid, psk))
            wifi.append((ssid, psk))

        shadow = tn.run("grep root /etc/shadow | head -1")
        m = re.search(r"root:(\$[0-9]\$[^:]+):", shadow)
        if m:
            found = U.crack_root(m.group(1),
                                 ["aDm8H%MdA", "admin", "root", "123456", "CMCCAdmin"])
            creds["root"] = ("root", found or m.group(1)[:32] + "…")
        tn.close()

        rows = []
        for key, label in LABELS:
            if key in creds:
                u, pv = creds[key]
                rows.append([label, u or "", pv or ""])
        for ssid, psk in wifi:
            note = "（出厂占位）" if psk == U.PLACEHOLDER_PSK else ""
            rows.append(["WiFi " + ssid, "", psk + note])
        if not rows:
            raise RuntimeError("未提取到凭据，请确认设备型号")
        return rows


class UngApp(App):
    title = "UNG220Z 光猫工具"

    def build(self):
        return Root()


if __name__ == "__main__":
    UngApp().run()
