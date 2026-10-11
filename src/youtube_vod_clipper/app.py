import os
import re
import sys
import json
import shutil
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from queue import Queue, Empty
from tkinter import filedialog, messagebox

import customtkinter as ctk
import yt_dlp
from yt_dlp.utils import download_range_func
import imageio_ffmpeg

try:
    from tkwry import WebView
except Exception as exc:
    WebView = None
    WEBVIEW_IMPORT_ERROR = exc
else:
    WEBVIEW_IMPORT_ERROR = None

APP_NAME = "YouTube VOD Clipper"
VERSION = "4.0.0"
BG = "#101216"
PANEL = "#191d24"
PANEL_ALT = "#202631"
ACCENT = "#3985ff"
TEXT = "#f1f4f8"
MUTED = "#9ca7b7"


def resource_path(name):
    return os.path.join(getattr(sys, "_MEIPASS", os.path.abspath(".")), name)


def get_ffmpeg():
    bundled = resource_path("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if os.path.isfile(bundled):
        return bundled
    return imageio_ffmpeg.get_ffmpeg_exe()


def parse_timestamp(value):
    value = value.strip().replace(" ", "")
    if not value:
        raise ValueError("Timestamp cannot be empty.")
    if value.isdigit():
        if len(value) <= 2:
            return int(value)
        value = value.zfill(6)
        h, m, s = int(value[:-4]), int(value[-4:-2]), int(value[-2:])
        if m > 59 or s > 59:
            raise ValueError("Invalid compact timestamp. Example: 001929 = 00:19:29.")
        return h * 3600 + m * 60 + s
    parts = value.split(":")
    if len(parts) == 2:
        m, s = map(float, parts)
        if s >= 60 or m < 0:
            raise ValueError("Invalid MM:SS timestamp.")
        return m * 60 + s
    if len(parts) == 3:
        h, m, s = map(float, parts)
        if min(h, m, s) < 0 or m >= 60 or s >= 60:
            raise ValueError("Invalid HH:MM:SS timestamp.")
        return h * 3600 + m * 60 + s
    raise ValueError("Use seconds, MM:SS, HH:MM:SS, or compact HHMMSS.")


def format_time(value):
    value = max(0, int(float(value)))
    return f"{value//3600:02d}:{(value%3600)//60:02d}:{value%60:02d}"


def video_id(url):
    p = urlparse(url.strip())
    host = p.netloc.lower().split(":")[0]
    if host == "youtu.be":
        return p.path.strip("/").split("/")[0] or None
    if host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
        if p.path == "/watch":
            return parse_qs(p.query).get("v", [None])[0]
        bits = p.path.split("/")
        if len(bits) > 2 and bits[1] in ("embed", "shorts", "live"):
            return bits[2]
    return None


def preview_page(vid):
    # YouTube handles playback/audio. The timeline is an overlay in the same WebView.
    return r'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}html,body,#wrap{margin:0;width:100%;height:100%;overflow:hidden;background:#080a0d;color:#fff;font-family:Segoe UI,Arial}
#player{position:absolute;inset:0;width:100%;height:100%;border:0}
#shade{position:absolute;bottom:0;left:0;right:0;height:112px;background:linear-gradient(transparent,rgba(0,0,0,.96));pointer-events:none}
#bar{position:absolute;bottom:10px;left:18px;right:18px;z-index:5}
#labels{display:flex;justify-content:space-between;font-size:12px;color:#fff;margin-bottom:7px;font-variant-numeric:tabular-nums}
#track{height:24px;position:relative;display:flex;align-items:center;cursor:pointer}
#line{height:5px;position:absolute;left:0;right:0;background:#555;border-radius:4px}
#sel{height:7px;position:absolute;background:#3985ff;border-radius:4px;pointer-events:none}
.handle{position:absolute;top:1px;width:15px;height:22px;margin-left:-7px;background:white;border-radius:4px;cursor:ew-resize;box-shadow:0 1px 5px #000}
.handle:after{content:"";position:absolute;left:5px;top:4px;width:5px;height:14px;background:#3985ff;border-radius:2px}
#hint{position:absolute;top:10px;left:12px;padding:7px 10px;background:#000a;border-radius:6px;color:#dce5f2;font-size:12px;z-index:6}
</style></head><body><div id="wrap">
<iframe id="player" src="https://www.youtube.com/embed/VIDEO_ID?enablejsapi=1&origin=https%3A%2F%2Ftkwry.localhost&playsinline=1&rel=0" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen></iframe>
<div id="shade"></div><div id="hint">Loading YouTube player…</div>
<div id="bar"><div id="labels"><span id="st">Start 00:00:00</span><span id="en">End 00:00:30</span></div>
<div id="track"><div id="line"></div><div id="sel"></div><div id="hs" class="handle"></div><div id="he" class="handle"></div></div></div></div>
<script src="https://www.youtube.com/iframe_api"></script><script>
let p=null,d=0,s=0,e=30,drag=null;
const fmt=n=>{n=Math.max(0,Math.floor(n));return String(Math.floor(n/3600)).padStart(2,'0')+':'+String(Math.floor(n%3600/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0')};
function emit(o){try{if(window.ipc)window.ipc.postMessage(JSON.stringify(o))}catch(_){}}
function draw(){if(!d)return;let r=track.getBoundingClientRect(),a=s/d*r.width,b=e/d*r.width;sel.style.left=a+'px';sel.style.width=Math.max(2,b-a)+'px';hs.style.left=a+'px';he.style.left=b+'px';st.textContent='Start '+fmt(s);en.textContent='End '+fmt(e)}
function choose(which,x){let r=track.getBoundingClientRect(),t=Math.max(0,Math.min(1,(x-r.left)/r.width))*d;if(which==='s')s=Math.min(t,e-1);else e=Math.max(t,s+1);s=Math.max(0,s);e=Math.min(d,e);draw();emit({type:'selection',start:s,end:e,duration:d})}
hs.onpointerdown=ev=>{drag='s';hs.setPointerCapture(ev.pointerId)};he.onpointerdown=ev=>{drag='e';he.setPointerCapture(ev.pointerId)};
track.onpointermove=ev=>{if(drag)choose(drag,ev.clientX)};track.onpointerup=()=>drag=null;track.onclick=ev=>{if(!drag&&p)p.seekTo(Math.max(0,Math.min(1,ev.offsetX/track.clientWidth))*d,true)};
function onYouTubeIframeAPIReady(){try{p=new YT.Player('player',{events:{onReady:ready,onError:err}})}catch(e){hint.textContent='Player error: '+e}}
function ready(){d=p.getDuration()||0;if(!d){setTimeout(ready,500);return}e=Math.min(30,d);draw();hint.textContent='Drag the blue handles to set clip start/end. Click the timeline to seek.';emit({type:'ready',duration:d})}
function err(ev){hint.textContent='YouTube embed error '+ev.data;emit({type:'error',code:ev.data})}
setTimeout(()=>{if(!d)emit({type:'timeout'})},25000);
setInterval(()=>{if(p&&d&&p.getCurrentTime&&p.getCurrentTime()>=e){p.pauseVideo();p.seekTo(s,true)}},300);
</script></body></html>'''.replace("VIDEO_ID", vid)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME}  ·  v{VERSION}")
        self.geometry("1180x850")
        self.minsize(960, 720)
        self.configure(fg_color=BG)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.url = ctk.StringVar()
        self.start = ctk.StringVar(value="00:00:00")
        self.end = ctk.StringVar(value="00:00:30")
        self.quality = ctk.StringVar(value="Best Available")
        self.mode = ctk.StringVar(value="Fast")
        self.output = ctk.StringVar(value=str(Path.home() / "Videos" / "YouTube Clips"))
        self.status = ctk.StringVar(value="Ready")
        self.progress = ctk.DoubleVar(value=0)
        self.queue = Queue()
        self.running = False
        self.cancel = False
        self.proc = None
        self.duration = 0
        self.web = None
        self.preview_dir = None
        self._build()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def panel(self, parent, **kwargs):
        return ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=12, **kwargs)

    def label(self, parent, text, **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=TEXT, **kwargs)

    def button(self, parent, text, command, primary=False, **kwargs):
        return ctk.CTkButton(parent, text=text, command=command, height=36,
            corner_radius=8, fg_color=ACCENT if primary else PANEL_ALT,
            hover_color="#2e6bd0" if primary else "#303947", **kwargs)

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        nav = ctk.CTkFrame(self, width=205, fg_color="#14171c", corner_radius=0)
        nav.grid(row=0, column=0, sticky="nsew")
        nav.grid_propagate(False)
        self.label(nav, "JTG  /  CLIPPER", font=ctk.CTkFont(size=19, weight="bold")).pack(anchor="w", padx=20, pady=(25, 2))
        self.label(nav, "YOUTUBE VOD TOOLS", font=ctk.CTkFont(size=10, weight="bold"), text_color=MUTED).pack(anchor="w", padx=20, pady=(0, 28))
        self.button(nav, "▶   Clip Studio", lambda: None, primary=True).pack(fill="x", padx=12, pady=4)
        self.button(nav, "▤   Queue & Activity", lambda: self.log("Activity view is shown below.")).pack(fill="x", padx=12, pady=4)
        self.button(nav, "⚙   Settings", lambda: self.log("Choose output and quality in Clip Settings.")).pack(fill="x", padx=12, pady=4)
        self.label(nav, "WINDOWS DESKTOP", text_color=MUTED, font=ctk.CTkFont(size=10, weight="bold")).pack(side="bottom", anchor="w", padx=20, pady=(0, 20))
        main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=22, pady=18)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)
        head = ctk.CTkFrame(main, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.label(head, "Clip Studio", font=ctk.CTkFont(size=25, weight="bold")).pack(anchor="w")
        self.label(head, "Preview a VOD, mark a moment, and export only the section you need.", text_color=MUTED).pack(anchor="w", pady=(3, 0))
        source = self.panel(main)
        source.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        source.grid_columnconfigure(0, weight=1)
        self.label(source, "VIDEO SOURCE", font=ctk.CTkFont(size=11, weight="bold"), text_color=MUTED).grid(row=0, column=0, sticky="w", padx=15, pady=(12, 5))
        row = ctk.CTkFrame(source, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(row, textvariable=self.url, placeholder_text="Paste YouTube VOD URL…", height=38).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.button(row, "Load YouTube", self.load_preview, primary=True, width=130).grid(row=0, column=1)
        preview = self.panel(main)
        preview.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_rowconfigure(1, weight=1)
        self.label(preview, "PREVIEW  /  TIMELINE", font=ctk.CTkFont(size=11, weight="bold"), text_color=MUTED).grid(row=0, column=0, sticky="w", padx=15, pady=(12, 8))
        self.preview_host = ctk.CTkFrame(preview, fg_color="#050608", corner_radius=8, height=330)
        self.preview_host.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.preview_host.grid_propagate(False)
        self.placeholder = self.label(self.preview_host, "Paste a YouTube URL above, then select  Load YouTube.", text_color=MUTED)
        self.placeholder.place(relx=.5, rely=.5, anchor="center")
        settings = self.panel(main)
        settings.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        for i in range(4): settings.grid_columnconfigure(i, weight=1)
        self.label(settings, "CLIP SETTINGS", font=ctk.CTkFont(size=11, weight="bold"), text_color=MUTED).grid(row=0, column=0, columnspan=4, sticky="w", padx=15, pady=(11, 5))
        for col, title, var in [(0,"START TIME",self.start),(1,"END TIME",self.end)]:
            self.label(settings, title, text_color=MUTED, font=ctk.CTkFont(size=10, weight="bold")).grid(row=1,column=col,sticky="w",padx=14,pady=(3,4))
            ctk.CTkEntry(settings,textvariable=var,height=34).grid(row=2,column=col,sticky="ew",padx=12,pady=(0,10))
        self.label(settings, "QUALITY", text_color=MUTED, font=ctk.CTkFont(size=10, weight="bold")).grid(row=1,column=2,sticky="w",padx=14,pady=(3,4))
        ctk.CTkOptionMenu(settings, variable=self.quality, values=["Best Available","1080p","720p","480p"], height=34).grid(row=2,column=2,sticky="ew",padx=12,pady=(0,10))
        self.label(settings, "MODE", text_color=MUTED, font=ctk.CTkFont(size=10, weight="bold")).grid(row=1,column=3,sticky="w",padx=14,pady=(3,4))
        ctk.CTkOptionMenu(settings, variable=self.mode, values=["Fast","Exact"], height=34).grid(row=2,column=3,sticky="ew",padx=12,pady=(0,10))
        self.label(settings, "OUTPUT FOLDER", text_color=MUTED, font=ctk.CTkFont(size=10, weight="bold")).grid(row=3,column=0,columnspan=4,sticky="w",padx=14,pady=(0,4))
        out = ctk.CTkFrame(settings, fg_color="transparent")
        out.grid(row=4,column=0,columnspan=4,sticky="ew",padx=12,pady=(0,12))
        out.grid_columnconfigure(0,weight=1)
        ctk.CTkEntry(out,textvariable=self.output,height=34).grid(row=0,column=0,sticky="ew",padx=(0,8))
        self.button(out,"Browse…",self.browse,width=95).grid(row=0,column=1)
        bottom = self.panel(main)
        bottom.grid(row=4,column=0,sticky="ew")
        bottom.grid_columnconfigure(0,weight=1)
        self.label(bottom, "ACTIVITY", font=ctk.CTkFont(size=11, weight="bold"), text_color=MUTED).grid(row=0,column=0,sticky="w",padx=14,pady=(10,4))
        self.logbox = ctk.CTkTextbox(bottom,height=65,fg_color="#111419",text_color="#c9d3e1",corner_radius=7)
        self.logbox.grid(row=1,column=0,columnspan=3,sticky="ew",padx=12,pady=(0,8))
        self.progressbar = ctk.CTkProgressBar(bottom,variable=self.progress,height=7,progress_color=ACCENT)
        self.progressbar.grid(row=2,column=0,sticky="ew",padx=12,pady=(0,8))
        self.status_label = self.label(bottom,textvariable=self.status,text_color=MUTED)
        self.status_label.grid(row=3,column=0,sticky="w",padx=13,pady=(0,10))
        actions=ctk.CTkFrame(bottom,fg_color="transparent")
        actions.grid(row=3,column=1,columnspan=2,sticky="e",padx=10,pady=(0,8))
        self.cancel_button=self.button(actions,"Cancel",self.cancel_download,width=85)
        self.cancel_button.pack(side="left",padx=(0,7));self.cancel_button.configure(state="disabled")
        self.clip_button=self.button(actions,"Export Clip",self.start_clip,primary=True,width=125)
        self.clip_button.pack(side="left")
        self.log("Ready. The embedded YouTube player supplies preview playback; preview media is not downloaded.")

    def log(self, text):
        self.queue.put(("log", str(text)))

    def load_preview(self):
        vid=video_id(self.url.get())
        if not vid:
            messagebox.showerror(APP_NAME,"Enter a valid YouTube video or VOD URL.")
            return
        if WebView is None:
            messagebox.showerror(APP_NAME,"The embedded WebView package could not be loaded.\n\nInstall Microsoft Edge WebView2 Runtime and run install.bat again.\n\n"+str(WEBVIEW_IMPORT_ERROR))
            return
        if self.web:
            try:self.web.destroy()
            except Exception:pass
        if self.preview_dir:shutil.rmtree(self.preview_dir,ignore_errors=True)
        self.preview_dir=tempfile.mkdtemp(prefix="yvc_preview_")
        Path(self.preview_dir,"index.html").write_text(preview_page(vid),encoding="utf-8")
        self.placeholder.place_forget()
        self.status.set("Loading YouTube player…")
        self.log("Opening embedded YouTube player…")
        try:
            self.web=WebView(self.preview_host,app=self.preview_dir,ipc_handler=self.preview_message,bridge_origins=["https://tkwry.localhost"],devtools=False)
            try:self.web.when_failed(lambda exc:self.preview_failed(exc))
            except Exception:pass
        except Exception as exc:self.preview_failed(exc)

    def preview_failed(self, exc):
        self.status.set("Preview failed");self.log("WebView error: "+str(exc))
        self.after(0,lambda:messagebox.showerror(APP_NAME,"Could not create the embedded player:\n\n"+str(exc)))

    def preview_message(self, msg):
        try:data=json.loads(msg)
        except Exception:return
        kind=data.get("type")
        if kind=="ready":
            self.duration=float(data.get("duration",0))
            self.start.set("00:00:00");self.end.set(format_time(min(30,self.duration)))
            self.status.set("Preview ready");self.log("YouTube player ready. Duration "+format_time(self.duration))
        elif kind=="selection":
            self.start.set(format_time(data.get("start",0)));self.end.set(format_time(data.get("end",0)))
        elif kind=="error":
            self.status.set("YouTube embed error");self.log("YouTube embed error code "+str(data.get("code")))
        elif kind=="timeout":
            self.status.set("Player timed out");self.log("The player did not report ready within 25 seconds.")

    def browse(self):
        folder=filedialog.askdirectory(initialdir=self.output.get())
        if folder:self.output.set(folder)

    def start_clip(self):
        if self.running:return
        url=self.url.get().strip()
        try:s=parse_timestamp(self.start.get());e=parse_timestamp(self.end.get())
        except ValueError as exc:messagebox.showerror(APP_NAME,str(exc));return
        if e<=s:messagebox.showerror(APP_NAME,"End time must be greater than start time.");return
        if self.duration and e>self.duration:messagebox.showerror(APP_NAME,"End time exceeds video duration.");return
        folder=Path(self.output.get()).expanduser()
        try:folder.mkdir(parents=True,exist_ok=True)
        except Exception as exc:messagebox.showerror(APP_NAME,"Cannot create output folder:\n"+str(exc));return
        self.running=True;self.cancel=False;self.progress.set(0);self.status.set("Starting…")
        self.clip_button.configure(state="disabled");self.cancel_button.configure(state="normal")
        threading.Thread(target=self._clip_worker,args=(url,s,e,folder,self.mode.get(),self.quality.get()),daemon=True).start()

    def _clip_worker(self,url,start,end,folder,mode,quality):
        tmp=folder/".yvc_temp";tmp.mkdir(exist_ok=True)
        try:
            ffmpeg=get_ffmpeg()
            os.environ["PATH"]=str(Path(ffmpeg).parent)+os.pathsep+os.environ.get("PATH","")
            def hook(d):
                if self.cancel:raise yt_dlp.utils.DownloadCancelled()
                if d.get("status")=="downloading":
                    total=d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    if total:self.queue.put(("progress",min(.85,d.get("downloaded_bytes",0)/total*.85),"Downloading clip…"))
                elif d.get("status")=="finished":self.queue.put(("progress",.9,"Finalizing clip…"))
            h=quality
            fmt="bv*+ba/b" if h=="Best Available" else f"bv*[height<={int(h[:-1])}]+ba/b[height<={int(h[:-1])}]/bv*+ba/b"
            opts={"format":fmt,"noplaylist":True,"quiet":True,"no_warnings":True,"ffmpeg_location":ffmpeg,"progress_hooks":[hook],"download_ranges":download_range_func(None,[(start,end)]),"outtmpl":str(tmp/"%(title).180B_%(id)s.%(ext)s"),"merge_output_format":"mp4","force_keyframes_at_cuts":mode=="Exact"}
            if mode=="Exact":opts["postprocessor_args"]={"ffmpeg":["-c:v","libx264","-preset","medium","-crf","18","-c:a","aac","-b:a","192k"]}
            with yt_dlp.YoutubeDL(opts) as ydl:info=ydl.extract_info(url,download=True)
            if self.cancel:raise RuntimeError("Operation cancelled.")
            candidates=[p for p in tmp.iterdir() if p.is_file() and p.suffix.lower() in (".mp4",".mkv",".webm",".mov")]
            if not candidates:raise RuntimeError("yt-dlp completed without producing a clip file.")
            title=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',info.get("title") or "clip")[:140]
            target=folder/f"{title}_{int(start):06d}-{int(end):06d}.mp4"
            if target.exists():target.unlink()
            max(candidates,key=lambda p:p.stat().st_mtime).replace(target)
            self.queue.put(("done",str(target)))
        except Exception as exc:
            if self.cancel:self.queue.put(("cancelled",))
            else:self.queue.put(("error",str(exc)))
        finally:
            shutil.rmtree(tmp,ignore_errors=True)

    def cancel_download(self):
        if self.running:self.cancel=True;self.status.set("Cancelling…");self.log("Cancellation requested.")

    def _poll(self):
        try:
            while True:
                item=self.queue.get_nowait()
                if item[0]=="log":
                    self.logbox.insert("end",item[1]+"\n");self.logbox.see("end")
                elif item[0]=="progress":
                    self.progress.set(item[1]);self.status.set(item[2])
                elif item[0]=="done":
                    self.running=False;self.clip_button.configure(state="normal");self.cancel_button.configure(state="disabled");self.progress.set(1);self.status.set("Completed")
                    self.log("Clip saved: "+item[1]);messagebox.showinfo(APP_NAME,"Clip saved successfully:\n\n"+item[1])
                elif item[0]=="cancelled":
                    self.running=False;self.clip_button.configure(state="normal");self.cancel_button.configure(state="disabled");self.status.set("Cancelled");self.log("Clip operation cancelled.")
                elif item[0]=="error":
                    self.running=False;self.clip_button.configure(state="normal");self.cancel_button.configure(state="disabled");self.status.set("Failed");self.log("ERROR: "+item[1]);messagebox.showerror(APP_NAME,item[1])
        except Empty:pass
        self.after(100,self._poll)

    def _close(self):
        if self.web:
            try:self.web.destroy()
            except Exception:pass
        if self.preview_dir:shutil.rmtree(self.preview_dir,ignore_errors=True)
        self.destroy()


if __name__ == "__main__":
    app=App()
    app.mainloop()
