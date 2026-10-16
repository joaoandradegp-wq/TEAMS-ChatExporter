import configparser
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from playwright.sync_api import sync_playwright

try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

def _exe_from_command(cmd: str) -> str:
    cmd = cmd.strip()
    if cmd.startswith('"'):
        return cmd[1:].split('"', 1)[0]
    m = re.match(r"(.+?\.exe)", cmd, re.IGNORECASE)
    return m.group(1) if m else cmd.split(" ", 1)[0]


def find_default_browser() -> str:
    try:
        import winreg
        with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice") as k:
            prog_id = winreg.QueryValueEx(k, "ProgId")[0]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,
                            rf"{prog_id}\shell\open\command") as k:
            exe = _exe_from_command(winreg.QueryValueEx(k, "")[0])
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass
    local = os.environ.get("LOCALAPPDATA", "")
    for p in (Path(local) / "Programs" / "Opera" / "opera.exe",
              Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
              Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
              Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe")):
        if p.exists():
            return str(p)
    return ""


INI_PATH = APP_DIR / "teams_export.ini"
DEFAULT_CDP = "http://localhost:9222"


def load_config():
    if not INI_PATH.exists():
        return None
    cfg = configparser.ConfigParser(interpolation=None)
    try:
        cfg.read(INI_PATH, encoding="utf-8")
        return {"browser": cfg.get("config", "browser", fallback=""),
                "cdp": cfg.get("config", "cdp", fallback=DEFAULT_CDP)}
    except configparser.Error:
        return None


def save_config(browser: str, cdp: str):
    cfg = configparser.ConfigParser(interpolation=None)
    cfg["config"] = {"browser": browser, "cdp": cdp}
    try:
        with open(INI_PATH, "w", encoding="utf-8") as f:
            cfg.write(f)
    except OSError:
        pass


class ExportError(Exception):
    pass


class Cancelled(Exception):
    pass


ITEM_SELECTORS = ['[data-tid="chat-pane-item"]', '[data-tid="chat-pane-message"]']
VIEWPORT_SELECTOR = '[data-tid="message-pane-list-viewport"]'

JS_EXTRACT = r"""
(itemSelectors) => {
  let items = [];
  for (const sel of itemSelectors) {
    items = Array.from(document.querySelectorAll(sel));
    if (items.length) break;
  }

  const bodySelectors = [
    '[data-tid="message-body"]',
    '[data-tid="chat-message-content"]',
    '[id^="content-"]'
  ];

  const toText = (node) => {
    const c = node.cloneNode(true);
    c.querySelectorAll('img[alt]').forEach(i => i.replaceWith(document.createTextNode(i.alt)));
    c.querySelectorAll('br').forEach(b => b.replaceWith(document.createTextNode('\n')));
    c.querySelectorAll('p,div,li').forEach(b => b.append(document.createTextNode('\n')));
    return c.textContent.replace(/\u00a0/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
  };

  const out = [];
  let lastAuthor = null;
  for (const el of items) {
    const midEl = el.hasAttribute('data-mid') ? el : el.querySelector('[data-mid]');
    const mid = midEl ? midEl.getAttribute('data-mid') : '';

    const aEl = el.querySelector('[data-tid="message-author-name"]');
    if (aEl) lastAuthor = aEl.textContent.trim();

    const tEl = el.querySelector('time[datetime]');
    const time = tEl ? tEl.getAttribute('datetime') : '';

    let text = '';
    for (const bs of bodySelectors) {
      const b = el.querySelector(bs);
      if (b) { text = toText(b); break; }
    }

    const files = Array.from(el.querySelectorAll('[data-tid*="attachment"] [title], [data-tid*="file"] [title]'))
      .map(n => n.getAttribute('title')).filter(Boolean);

    out.push({ mid, author: lastAuthor, time, text, files: Array.from(new Set(files)) });
  }
  return out;
}
"""

JS_SCROLL_TOP = r"""
([itemSelectors, viewportSel]) => {
  let el = document.querySelector(viewportSel);
  if (!el) {
    let first = null;
    for (const sel of itemSelectors) { first = document.querySelector(sel); if (first) break; }
    el = first ? first.parentElement : null;
    while (el && el.scrollHeight <= el.clientHeight + 5) el = el.parentElement;
  }
  if (!el) return null;
  el.scrollTop = 400;
  return el.scrollHeight;
}
"""

JS_SCROLL_ZERO = r"""
([itemSelectors, viewportSel]) => {
  let el = document.querySelector(viewportSel);
  if (!el) {
    let first = null;
    for (const sel of itemSelectors) { first = document.querySelector(sel); if (first) break; }
    el = first ? first.parentElement : null;
    while (el && el.scrollHeight <= el.clientHeight + 5) el = el.parentElement;
  }
  if (!el) return null;
  el.scrollTop = 0;
  return el.scrollHeight;
}
"""

JS_DEBUG_HTML = (
    "(sels) => { for (const s of sels) { const n = document.querySelectorAll(s);"
    " if (n.length) return Array.from(n).slice(0, 5).map(e => e.outerHTML).join('\\n\\n<!-- ---- -->\\n\\n'); }"
    " return document.body.innerHTML.slice(0, 20000); }"
)


def parse_iso(s: str):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)
    try:
        return datetime.fromisoformat(s).astimezone()
    except ValueError:
        return None


def parse_user_date(s: str, end_of_day: bool = False) -> datetime:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            d = datetime.strptime(s, fmt)
            if end_of_day:
                d = d.replace(hour=23, minute=59, second=59)
            return d.astimezone()
        except ValueError:
            continue
    raise ExportError(f"Data inválida: {s!r}. Use AAAA-MM-DD ou DD/MM/AAAA.")


def msg_datetime(m: dict):
    dt = parse_iso(m.get("time"))
    if dt:
        return dt
    mid = m.get("mid", "")
    if mid.isdigit() and len(mid) >= 12:
        return datetime.fromtimestamp(int(mid) / 1000).astimezone()
    return None


def sort_key(m: dict):
    mid = m.get("mid", "")
    if mid.isdigit():
        return (0, int(mid))
    dt = msg_datetime(m)
    return (1, dt.timestamp() if dt else 0)


def save_debug_html(page):
    html = page.evaluate(JS_DEBUG_HTML, ITEM_SELECTORS)
    path = APP_DIR / "teams_debug.html"
    path.write_text(html, encoding="utf-8")
    print(f"HTML de debug salvo em {path}")


def check_stop(stop_event: threading.Event):
    if stop_event.is_set():
        raise Cancelled()


def collect(page, pause: float, max_stable: int, since, stop_event) -> dict:
    msgs: dict = {}
    stable = 0
    last_height = -1
    round_no = 0

    while stable < max_stable:
        check_stop(stop_event)
        round_no += 1
        page.evaluate(JS_SCROLL_TOP, [ITEM_SELECTORS, VIEWPORT_SELECTOR])
        time.sleep(0.3)
        height = page.evaluate(JS_SCROLL_ZERO, [ITEM_SELECTORS, VIEWPORT_SELECTOR])
        if height is None:
            raise ExportError("Não encontrei a área de mensagens. Confira se o chat "
                              "está aberto no navegador.")
        if stop_event.wait(pause):
            raise Cancelled()

        before = len(msgs)
        for m in page.evaluate(JS_EXTRACT, ITEM_SELECTORS):
            key = m["mid"] or f"{m['time']}|{m['author']}|{m['text'][:40]}"
            old = msgs.get(key)
            if old:
                if not m["author"]:
                    m["author"] = old["author"]
                if not m["text"]:
                    m["text"] = old["text"]
            msgs[key] = m

        grew = len(msgs) > before or height != last_height
        last_height = height
        stable = 0 if grew else stable + 1
        print(f"  rodada {round_no}: {len(msgs)} mensagens coletadas", end="\r")

        if since:
            dts = [d for d in (msg_datetime(m) for m in msgs.values()) if d]
            if dts and min(dts) < since:
                print(f"\n  Chegou em {min(dts):%d/%m/%Y %H:%M}, anterior a {since:%d/%m/%Y}. "
                      "Parando a rolagem.")
                break

    print()
    return msgs


def export_chat(opts: dict, stop_event: threading.Event) -> Path:
    since = parse_user_date(opts["since"]) if opts.get("since") else None
    until = parse_user_date(opts["until"], end_of_day=True) if opts.get("until") else None
    pause = opts["pause"]
    max_stable = 4

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(opts["cdp"])
        try:
            ctx = browser.contexts[0]
            page = next((pg for pg in ctx.pages if "teams" in pg.url), None) \
                or (ctx.pages[0] if ctx.pages else ctx.new_page())
            print(f"Conectado ao navegador. Aba: {page.url[:80]}")

            try:
                title = page.locator('[data-tid="chat-title"]').first.inner_text(timeout=3000).strip()
            except Exception:
                title = page.title()

            if since:
                print(f"Rolando o histórico até {since:%d/%m/%Y}...")
            else:
                print("Rolando o histórico até o começo (pode demorar em grupos grandes)...")
            msgs = collect(page, pause, max_stable, since, stop_event)

            if not any(m["text"].strip() for m in msgs.values()):
                print("Nenhuma mensagem com texto foi extraída; gerando debug automaticamente.")
                save_debug_html(page)
        finally:
            try:
                browser.close()
            except Exception:
                pass

    ordered = sorted(msgs.values(), key=sort_key)

    print(f"DIAG: total={len(ordered)} "
          f"| com texto={sum(1 for m in ordered if m['text'].strip())} "
          f"| com anexo={sum(1 for m in ordered if m['files'])} "
          f"| com data={sum(1 for m in ordered if msg_datetime(m))} "
          f"| com autor={sum(1 for m in ordered if m['author'])}")
    datas = [d for d in (msg_datetime(m) for m in ordered) if d]
    if datas:
        print(f"DIAG: datas de {min(datas):%d/%m/%Y %H:%M} a {max(datas):%d/%m/%Y %H:%M}")

    def in_range(m):
        dt = msg_datetime(m)
        if dt is None:
            return True
        return (not since or dt >= since) and (not until or dt <= until)

    ordered = [m for m in ordered if in_range(m)]
    print(f"DIAG: após filtro de período={len(ordered)}")

    last_author = None
    for m in ordered:
        if m["author"]:
            last_author = m["author"]
        else:
            m["author"] = last_author or "(desconhecido)"

    linhas = []
    for m in ordered:
        text = m["text"]
        if m["files"]:
            text += ("\n" if text else "") + "[Anexos: " + ", ".join(m["files"]) + "]"
        if not text.strip():
            continue
        dt = msg_datetime(m)
        when = dt.strftime("%d/%m/%Y %H:%M") if dt else "??/??/???? ??:??"
        linhas.append(f"[{when}] {m['author']}: {text}")

    safe = re.sub(r'[\\/:*?"<>|]', "_", title or "chat")[:60]
    out = Path(opts["out"]) if opts.get("out") else \
        APP_DIR / f"teams_{safe}_{datetime.now():%Y%m%d_%H%M}.txt"
    if not out.is_absolute():
        out = APP_DIR / out

    with open(out, "w", encoding="utf-8") as f:
        f.write(f"Chat: {title}\n")
        f.write(f"Exportado em: {datetime.now():%d/%m/%Y %H:%M}\n")
        if since or until:
            ini = f"{since:%d/%m/%Y}" if since else "início"
            fim = f"{until:%d/%m/%Y}" if until else "hoje"
            f.write(f"Período: {ini} a {fim}\n")
        f.write(f"Total de mensagens: {len(linhas)}\n")
        f.write("=" * 60 + "\n\n")
        f.write("\n\n".join(linhas))

    print(f"Pronto! {len(linhas)} mensagens salvas em: {out}")
    return out


class QueueWriter:

    def __init__(self, q: queue.Queue):
        self.q = q

    def write(self, s):
        if s:
            self.q.put(("text", s))
        return len(s) if s else 0

    def flush(self):
        pass

    def isatty(self):
        return False


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Exportar chat do Teams")
        self.geometry("720x560")
        self.minsize(640, 480)

        self.q = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.result_path = None

        pad = dict(padx=8, pady=4)

        fb = ttk.LabelFrame(self, text="1) Navegador (modo --cdp)")
        fb.pack(fill="x", **pad)
        fb.columnconfigure(1, weight=1)

        ttk.Label(fb, text="Navegador:").grid(row=0, column=0, sticky="w", **pad)
        conf = load_config()
        if conf is None:
            conf = {"browser": find_default_browser(), "cdp": DEFAULT_CDP}
            save_config(conf["browser"], conf["cdp"])
        self.browser_var = tk.StringVar(value=conf["browser"])
        ttk.Entry(fb, textvariable=self.browser_var).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(fb, text="...", width=3, command=self.pick_browser).grid(row=0, column=2, **pad)

        ttk.Label(fb, text="Endereço CDP:").grid(row=1, column=0, sticky="w", **pad)
        self.cdp_var = tk.StringVar(value=conf["cdp"])
        ttk.Entry(fb, textvariable=self.cdp_var).grid(row=1, column=1, sticky="ew", **pad)
        self.browser_var.trace_add("write", self._save_cfg)
        self.cdp_var.trace_add("write", self._save_cfg)

        bb = ttk.Frame(fb)
        bb.grid(row=2, column=0, columnspan=3, sticky="w", **pad)
        ttk.Button(bb, text="Abrir navegador", command=self.open_browser).pack(side="left")
        ttk.Button(bb, text="Testar conexão", command=self.test_cdp).pack(side="left", padx=6)
        self.cdp_status = ttk.Label(bb, text="")
        self.cdp_status.pack(side="left", padx=6)

        fp = ttk.LabelFrame(self, text="2) Período")
        fp.pack(fill="x", **pad)

        self.all_var = tk.BooleanVar(value=False)
        self.today_var = tk.BooleanVar(value=True)

        ttk.Label(fp, text="De:").grid(row=0, column=0, sticky="w", **pad)
        self.since = self._date_widget(fp)
        self.since.grid(row=0, column=1, sticky="w", **pad)
        self._set(self.since, date.today() - timedelta(days=7))
        ttk.Checkbutton(fp, text="Desde o início", variable=self.all_var,
                        command=self._toggle).grid(row=0, column=2, sticky="w", **pad)

        ttk.Label(fp, text="Até:").grid(row=1, column=0, sticky="w", **pad)
        self.until = self._date_widget(fp)
        self.until.grid(row=1, column=1, sticky="w", **pad)
        ttk.Checkbutton(fp, text="Até hoje", variable=self.today_var,
                        command=self._toggle).grid(row=1, column=2, sticky="w", **pad)

        qf = ttk.Frame(fp)
        qf.grid(row=2, column=0, columnspan=3, sticky="w", **pad)
        ttk.Label(qf, text="Atalhos:").pack(side="left")
        for txt, days in (("Hoje", 0), ("7 dias", 7), ("30 dias", 30), ("90 dias", 90)):
            ttk.Button(qf, text=txt, command=lambda d=days: self.quick(d)).pack(side="left", padx=3)
        ttk.Button(qf, text="Mês atual", command=self.quick_month).pack(side="left", padx=3)
        self._toggle()

        fo = ttk.LabelFrame(self, text="Opções")
        fo.pack(fill="x", **pad)
        fo.columnconfigure(1, weight=1)

        ttk.Label(fo, text="Salvar em:").grid(row=0, column=0, sticky="w", **pad)
        self.out_var = tk.StringVar(value="")
        ttk.Entry(fo, textvariable=self.out_var).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(fo, text="...", width=3, command=self.pick_out).grid(row=0, column=2, **pad)
        ttk.Label(fo, text="(vazio = nome automático na pasta do programa)",
                  foreground="gray").grid(row=1, column=1, sticky="w", padx=8)

        ttk.Label(fo, text="Pausa (s):").grid(row=2, column=0, sticky="w", **pad)
        self.pause_var = tk.StringVar(value="1.5")
        ttk.Spinbox(fo, from_=0.5, to=10, increment=0.5, width=6,
                    textvariable=self.pause_var).grid(row=2, column=1, sticky="w", **pad)

        fa = ttk.Frame(self)
        fa.pack(fill="x", **pad)
        self.run_btn = ttk.Button(fa, text="▶ Executar", command=self.run)
        self.run_btn.pack(side="left")
        self.stop_btn = ttk.Button(fa, text="■ Parar", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=6)
        self.open_btn = ttk.Button(fa, text="Abrir arquivo gerado", command=self.open_result,
                                   state="disabled")
        self.open_btn.pack(side="left", padx=6)
        self.folder_btn = ttk.Button(fa, text="Abrir pasta", command=self.open_folder,
                                     state="disabled")
        self.folder_btn.pack(side="left")

        fl = ttk.LabelFrame(self, text="Log")
        fl.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(fl, height=10, wrap="word", state="disabled",
                           font=("Consolas", 9))
        sb = ttk.Scrollbar(fl, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        self.log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self._poll)

    def _date_widget(self, parent):
        if DateEntry:
            try:
                return DateEntry(parent, date_pattern="dd/mm/yyyy", width=12, locale="pt_BR")
            except Exception:
                return DateEntry(parent, date_pattern="dd/mm/yyyy", width=12)
        return ttk.Entry(parent, width=14)

    def _set(self, w, d: date):
        if DateEntry and isinstance(w, DateEntry):
            w.set_date(d)
        else:
            w.delete(0, "end")
            w.insert(0, d.strftime("%d/%m/%Y"))

    def _toggle(self):
        self.since.configure(state="disabled" if self.all_var.get() else "normal")
        self.until.configure(state="disabled" if self.today_var.get() else "normal")

    def quick(self, days: int):
        self.all_var.set(False)
        self.today_var.set(True)
        self._toggle()
        self._set(self.since, date.today() - timedelta(days=days))

    def quick_month(self):
        self.all_var.set(False)
        self.today_var.set(True)
        self._toggle()
        self._set(self.since, date.today().replace(day=1))

    def _save_cfg(self, *_):
        save_config(self.browser_var.get().strip(), self.cdp_var.get().strip())

    def pick_browser(self):
        p = filedialog.askopenfilename(title="Selecione o executável do navegador",
                                       filetypes=[("Executável", "*.exe"), ("Todos", "*.*")])
        if p:
            self.browser_var.set(p)

    def pick_out(self):
        p = filedialog.asksaveasfilename(defaultextension=".txt",
                                         filetypes=[("Texto", "*.txt")])
        if p:
            self.out_var.set(p)

    def _port(self) -> str:
        url = self.cdp_var.get().strip()
        return url.rsplit(":", 1)[-1].strip("/") or "9222"

    def open_browser(self):
        exe = self.browser_var.get().strip()
        if not exe or not Path(exe).exists():
            messagebox.showerror("Navegador", "Informe o caminho do executável do navegador.")
            return
        args = [exe, f"--remote-debugging-port={self._port()}"]
        if "opera" not in Path(exe).stem.lower() and Path(exe).stem.lower() != "launcher":
            profile = APP_DIR / f"teams_profile_{Path(exe).stem.lower()}"
            args.append(f"--user-data-dir={profile}")
        try:
            subprocess.Popen(args)
            self.cdp_status.config(text="Navegador iniciado. Abra o chat no Teams.",
                                   foreground="gray")
        except Exception as e:
            messagebox.showerror("Navegador", str(e))

    def test_cdp(self):
        url = self.cdp_var.get().strip().rstrip("/") + "/json/version"
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                r.read()
            self.cdp_status.config(text="✔ Conectado", foreground="green")
        except Exception:
            self.cdp_status.config(
                text="✘ Sem resposta (feche o navegador e use 'Abrir navegador')", foreground="red")

    def append(self, text: str):
        self.log.configure(state="normal")
        parts = text.replace("\r\n", "\n").split("\r")
        for i, part in enumerate(parts):
            if i > 0:
                self.log.delete("end-1c linestart", "end-1c")
            self.log.insert("end", part)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "text":
                    self.append(payload)
                elif kind == "done":
                    self._finished(payload)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    @staticmethod
    def _valid(s: str) -> bool:
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                datetime.strptime(s, fmt)
                return True
            except ValueError:
                pass
        return False

    def run(self):
        if self.worker and self.worker.is_alive():
            return

        try:
            pause = float(self.pause_var.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Pausa", "Valor de pausa inválido.")
            return

        opts = {"cdp": self.cdp_var.get().strip(), "pause": pause,
                "since": None, "until": None, "out": self.out_var.get().strip() or None}

        if not self.all_var.get():
            s = self.since.get().strip()
            if not self._valid(s):
                messagebox.showerror("Data", "Data inicial inválida. Use DD/MM/AAAA.")
                return
            opts["since"] = s
        if not self.today_var.get():
            u = self.until.get().strip()
            if not self._valid(u):
                messagebox.showerror("Data", "Data final inválida. Use DD/MM/AAAA.")
                return
            opts["until"] = u

        self.result_path = None
        self.stop_event.clear()
        self.open_btn.config(state="disabled")
        self.folder_btn.config(state="disabled")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.run_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        self.worker = threading.Thread(target=self._worker, args=(opts,), daemon=True)
        self.worker.start()

    def _worker(self, opts: dict):
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = QueueWriter(self.q)
        result = None
        try:
            result = export_chat(opts, self.stop_event)
        except Cancelled:
            print("\nCancelado pelo usuário.")
        except ExportError as e:
            print(f"\nErro: {e}")
        except Exception:
            print("\nErro inesperado:")
            traceback.print_exc()
        finally:
            sys.stdout, sys.stderr = old_out, old_err
            self.q.put(("done", result))

    def _finished(self, result):
        self.run_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.append("\n[processo finalizado]\n")
        if result and Path(result).exists():
            self.result_path = Path(result)
            self.open_btn.config(state="normal")
            self.folder_btn.config(state="normal")

    def stop(self):
        if self.worker and self.worker.is_alive():
            self.stop_event.set()

    def open_result(self):
        if self.result_path and self.result_path.exists():
            os.startfile(self.result_path)

    def open_folder(self):
        if self.result_path:
            os.startfile(self.result_path.parent)

    def on_close(self):
        self.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
