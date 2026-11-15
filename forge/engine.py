from __future__ import annotations
import os, shutil, signal, subprocess, sys, threading, time, urllib.error, urllib.request
from pathlib import Path
from typing import Any, Callable
from .models import Step,Workflow

class WorkflowStopped(RuntimeError): pass

class WorkflowRunner:
    """Runs a workflow's steps in order.

    ``logger`` receives human-readable log lines. ``on_event`` (optional)
    receives structured progress for programs that drive Forge, such as Depot:
    ``on_event(kind, data)`` with kind one of ``step_started``,
    ``step_succeeded``, ``step_failed`` or ``run_finished`` (``outcome`` is
    ``completed``, ``failed`` or ``stopped``, with a ``failed_steps`` count, so a
    run that continued past errors is ``completed`` with ``failed_steps`` > 0).
    ``data`` is a
    plain dict (see ``_emit`` calls below); ``step_failed`` includes the PID
    of the command that failed, or ``None`` for non-command steps.
    """
    def __init__(self,logger:Callable[[str],None]|None=None,on_event:Callable[[str,dict[str,Any]],None]|None=None):
        self.logger=logger or (lambda _:None); self.on_event=on_event; self.stop_event=threading.Event(); self._process=None; self._last_pid=None
    def _emit(self,kind:str,**data:Any)->None:
        if self.on_event is None: return
        try: self.on_event(kind,data)
        except Exception as exc: self.logger(f"  (event handler failed: {exc})")
    def stop(self):
        """Stop the current run, or the next one if none has started yet. The
        stop sticks until ``reset()``, so a run starting after a stop request
        stops at once instead of clearing it."""
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
    def reset(self):
        """Allow another run after ``stop()``. Call before reusing a runner."""
        self.stop_event.clear()
    @staticmethod
    def _group_alive(pgid):
        try: os.killpg(pgid,0)
        except ProcessLookupError: return False
        except PermissionError: return True
        return True
    def _halt(self,reader,grace=3.0):
        # Wait for the command's whole process group, not just its shell: a
        # shell can exit on SIGTERM while a child that ignores it lives on.
        self._kill_tree(self._process)
        if os.name!="nt":
            pgid=self._process.pid; deadline=time.monotonic()+grace
            while time.monotonic()<deadline and self._group_alive(pgid):
                self._process.poll(); time.sleep(.05)
            if self._group_alive(pgid):
                try:os.killpg(pgid,signal.SIGKILL)
                except OSError:pass
            deadline=time.monotonic()+grace
            while time.monotonic()<deadline and self._group_alive(pgid):
                self._process.poll(); time.sleep(.05)
        try:self._process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            self._process.kill(); self._process.wait(timeout=grace)
        reader.join(timeout=3)
    def run(self,workflow:Workflow):
        self.logger(f"▶ {workflow.name} — {len(workflow.steps)} step(s)")
        failed_steps=0
        for i,step in enumerate(workflow.steps,1):
            if self.stop_event.is_set(): self.logger("■ Stopped"); self._emit("run_finished",outcome="stopped",failed_steps=failed_steps); return False
            self.logger(f"[{i}/{len(workflow.steps)}] {step.label()}")
            self._last_pid=None; started=time.monotonic()
            self._emit("step_started",index=i-1,step_id=step.id,type=step.type,label=step.label())
            try:
                self._run_step(step); self.logger("  ✓ done")
                self._emit("step_succeeded",index=i-1,step_id=step.id,duration_ms=round((time.monotonic()-started)*1000))
            except WorkflowStopped:self.logger("■ Stopped"); self._emit("run_finished",outcome="stopped",failed_steps=failed_steps); return False
            except Exception as exc:
                self.logger(f"  ✕ {exc}")
                code=self._process.returncode if step.type=="command" and self._process is not None else None
                self._emit("step_failed",index=i-1,step_id=step.id,label=step.label(),error=str(exc),pid=self._last_pid,exit_code=code)
                failed_steps+=1
                if not step.continue_on_error:self.logger("Workflow halted"); self._emit("run_finished",outcome="failed",failed_steps=failed_steps); return False
                self.logger("  ↳ continuing because continue-on-error is enabled")
        self.logger("✓ Workflow complete"); self._emit("run_finished",outcome="completed",failed_steps=failed_steps); return True
    def _run_step(self,step): getattr(self,f"_step_{step.type}")(step)
    def _step_command(self,step):
        cmd=str(step.config.get("command","")).strip(); cwd=str(step.config.get("cwd","")).strip() or None
        if not cmd: raise ValueError("Command is empty")
        group={"creationflags":subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=="nt" else {"start_new_session":True}
        # stdin=DEVNULL: a command must not read whatever drives Forge (Depot
        # sends its requests on depot-core's stdin).
        self._process=subprocess.Popen(cmd,cwd=cwd,shell=True,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",**group); self._last_pid=self._process.pid; start=time.monotonic(); assert self._process.stdout is not None
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
    @staticmethod
    def _path(step,key):
        """A path from a step's config. An empty value is refused: Path("") means
        the current folder, so a blank field would otherwise act on wherever
        Forge happens to be running."""
        raw=str(step.config.get(key,"") or "").strip()
        if not raw: raise ValueError(f"{key.capitalize()} is empty")
        return Path(raw).expanduser()
    @staticmethod
    def _refuse_dangerous_delete(p):
        """A delete may not take out a drive root, your home folder, the folder
        Forge runs in, or any folder that contains one of those."""
        resolved=p.resolve()
        for keep in (Path.home().resolve(),Path.cwd().resolve()):
            if keep.is_relative_to(resolved):
                raise ValueError(f"Refusing to delete {resolved}: it contains your home folder or the folder Forge is running in")
        if resolved==Path(resolved.anchor):
            raise ValueError(f"Refusing to delete {resolved}: it is a drive root")
    def _step_copy(self,step):
        s=self._path(step,"source"); t=self._path(step,"target")
        if s.is_dir(): shutil.copytree(s,t,dirs_exist_ok=True)
        else:t.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(s,t)
    def _step_move(self,step):
        s=self._path(step,"source"); t=self._path(step,"target"); t.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(s),str(t))
    def _step_mkdir(self,step): self._path(step,"path").mkdir(parents=True,exist_ok=True)
    def _step_write(self,step):
        p=self._path(step,"path"); p.parent.mkdir(parents=True,exist_ok=True); mode="a" if bool(step.config.get("append",False)) else "w"
        with p.open(mode,encoding="utf-8") as h:h.write(str(step.config.get("content","")))
    def _step_delete(self,step):
        p=self._path(step,"path")
        if not p.exists(): return
        self._refuse_dangerous_delete(p)
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
        elif sys.platform=="darwin":subprocess.Popen(["open",path],stdin=subprocess.DEVNULL)
        else:subprocess.Popen(["xdg-open",path],stdin=subprocess.DEVNULL)
