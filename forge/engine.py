from __future__ import annotations
import os, shutil, signal, subprocess, sys, threading, time, urllib.error, urllib.request
from pathlib import Path
from typing import Callable
from .models import Step,Workflow

class WorkflowStopped(RuntimeError): pass

class WorkflowRunner:
    def __init__(self,logger:Callable[[str],None]|None=None): self.logger=logger or (lambda _:None); self.stop_event=threading.Event(); self._process=None
    def stop(self):
        self.stop_event.set()
        if self._process and self._process.poll() is None: self._kill_tree(self._process)
    @staticmethod
    def _kill_tree(process):
        # Commands run through a shell, so terminating only the shell would leave
        # the real command running and holding the output pipe open.
        try:
            if os.name=="nt": subprocess.run(["taskkill","/T","/F","/PID",str(process.pid)],capture_output=True,check=False)
            else: os.killpg(process.pid,signal.SIGTERM)
        except (OSError,ProcessLookupError):
            try:process.terminate()
            except OSError:pass
    def _halt(self,reader):
        self._kill_tree(self._process)
        try:self._process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            if os.name!="nt":
                try:os.killpg(self._process.pid,signal.SIGKILL)
                except OSError:pass
            self._process.kill(); self._process.wait(timeout=3)
        reader.join(timeout=3)
    def run(self,workflow:Workflow):
        self.stop_event.clear(); self.logger(f"▶ {workflow.name} — {len(workflow.steps)} step(s)")
        for i,step in enumerate(workflow.steps,1):
            if self.stop_event.is_set(): self.logger("■ Stopped"); return False
            self.logger(f"[{i}/{len(workflow.steps)}] {step.label()}")
            try:self._run_step(step); self.logger("  ✓ done")
            except WorkflowStopped:self.logger("■ Stopped"); return False
            except Exception as exc:
                self.logger(f"  ✕ {exc}")
                if not step.continue_on_error:self.logger("Workflow halted"); return False
                self.logger("  ↳ continuing because continue-on-error is enabled")
        self.logger("✓ Workflow complete"); return True
    def _run_step(self,step): getattr(self,f"_step_{step.type}")(step)
    def _step_command(self,step):
        cmd=str(step.config.get("command","")).strip(); cwd=str(step.config.get("cwd","")).strip() or None
        if not cmd: raise ValueError("Command is empty")
        group={"creationflags":subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=="nt" else {"start_new_session":True}
        self._process=subprocess.Popen(cmd,cwd=cwd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",**group); start=time.monotonic(); assert self._process.stdout is not None
        def pump():
            assert self._process and self._process.stdout
            for line in self._process.stdout:self.logger("    "+line.rstrip())
        reader=threading.Thread(target=pump,daemon=True); reader.start()
        while True:
            if self.stop_event.is_set(): self._halt(reader); raise WorkflowStopped()
            code=self._process.poll()
            if code is not None:
                reader.join(timeout=1); self._process.stdout.close()
                if code!=0: raise RuntimeError(f"Command exited with code {code}")
                return
            if step.timeout and time.monotonic()-start>step.timeout:self._halt(reader); raise TimeoutError(f"Command exceeded {step.timeout:g}s timeout")
            time.sleep(.05)
    def _step_copy(self,step):
        s=Path(str(step.config.get("source",""))).expanduser(); t=Path(str(step.config.get("target",""))).expanduser()
        if s.is_dir(): shutil.copytree(s,t,dirs_exist_ok=True)
        else:t.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(s,t)
    def _step_move(self,step):
        s=Path(str(step.config.get("source",""))).expanduser(); t=Path(str(step.config.get("target",""))).expanduser(); t.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(s),str(t))
    def _step_mkdir(self,step): Path(str(step.config.get("path",""))).expanduser().mkdir(parents=True,exist_ok=True)
    def _step_write(self,step):
        p=Path(str(step.config.get("path",""))).expanduser(); p.parent.mkdir(parents=True,exist_ok=True); mode="a" if bool(step.config.get("append",False)) else "w"
        with p.open(mode,encoding="utf-8") as h:h.write(str(step.config.get("content","")))
    def _step_delete(self,step):
        p=Path(str(step.config.get("path",""))).expanduser()
        if not p.exists(): return
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    def _step_http(self,step):
        url=str(step.config.get("url","")).strip(); method=str(step.config.get("method","GET")).upper(); headers=step.config.get("headers",{}); body=str(step.config.get("body",""))
        if not isinstance(headers,dict): raise ValueError("HTTP headers must be an object")
        req=urllib.request.Request(url,data=body.encode() if body and method not in {"GET","HEAD"} else None,headers={str(k):str(v) for k,v in headers.items()},method=method)
        try:
            with urllib.request.urlopen(req,timeout=step.timeout or 30) as r:
                payload=r.read(4096).decode("utf-8",errors="replace"); self.logger(f"    HTTP {r.status} {r.reason}");
                if payload:self.logger("    "+payload.replace("\n"," ")[:300])
        except urllib.error.HTTPError as exc: raise RuntimeError(f"HTTP {exc.code} {exc.reason}") from exc
    def _step_wait(self,step):
        end=time.monotonic()+max(0,float(step.config.get("seconds",1)))
        while time.monotonic()<end:
            if self.stop_event.wait(min(.1,max(0,end-time.monotonic()))): raise WorkflowStopped()
    def _step_open(self,step):
        path=str(step.config.get("path","")).strip()
        if not path: raise ValueError("Open path is empty")
        if os.name=="nt":os.startfile(path)
        elif sys.platform=="darwin":subprocess.Popen(["open",path])
        else:subprocess.Popen(["xdg-open",path])
