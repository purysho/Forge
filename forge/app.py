from __future__ import annotations
import json, threading, tkinter as tk
from pathlib import Path
from tkinter import filedialog,messagebox,simpledialog,ttk
from .engine import WorkflowRunner
from .models import STEP_TYPES,Step,Workflow
from .storage import ForgeStore

BG="#0c0e12"; PANEL="#15191f"; PANEL2="#1e242c"; TEXT="#f0f1f3"; MUTED="#8e99a5"; ACCENT="#f0a33a"
FIELDS={"command":[("command","Command"),("cwd","Working directory")],"copy":[("source","Source"),("target","Target")],"move":[("source","Source"),("target","Target")],"mkdir":[("path","Folder path")],"write":[("path","File path"),("content","Content")],"delete":[("path","Path to delete")],"http":[("method","Method"),("url","URL"),("headers","Headers JSON"),("body","Body")],"wait":[("seconds","Seconds")],"open":[("path","Path / URL")]}

class StepDialog(tk.Toplevel):
    def __init__(self,parent,step=None):
        super().__init__(parent); self.title("Edit step" if step else "Add step"); self.configure(bg=BG); self.result=None; self.original=step; self.type_var=tk.StringVar(value=step.type if step else "command"); self.name_var=tk.StringVar(value=step.name if step else ""); self.timeout_var=tk.StringVar(value=str(step.timeout or "")); self.continue_var=tk.BooleanVar(value=step.continue_on_error if step else False); self.inputs={}; self._build(); self.transient(parent); self.grab_set(); self.wait_visibility(); self.focus_set()
    def _build(self):
        o=tk.Frame(self,bg=BG,padx=18,pady=18); o.pack(fill="both",expand=True); tk.Label(o,text="Step type",bg=BG,fg=MUTED).grid(row=0,column=0,sticky="w"); c=ttk.Combobox(o,textvariable=self.type_var,values=STEP_TYPES,state="readonly",width=18); c.grid(row=1,column=0,sticky="ew",pady=(4,10)); c.bind("<<ComboboxSelected>>",lambda _:self._fields()); tk.Label(o,text="Label (optional)",bg=BG,fg=MUTED).grid(row=0,column=1,sticky="w",padx=(12,0)); tk.Entry(o,textvariable=self.name_var,bg=PANEL2,fg=TEXT,insertbackground=TEXT,relief="flat",width=34).grid(row=1,column=1,sticky="ew",padx=(12,0),pady=(4,10),ipady=5); self.field_frame=tk.Frame(o,bg=BG); self.field_frame.grid(row=2,column=0,columnspan=2,sticky="nsew"); self._fields(); opts=tk.Frame(o,bg=BG); opts.grid(row=3,column=0,columnspan=2,sticky="ew",pady=(12,6)); tk.Label(opts,text="Timeout (seconds)",bg=BG,fg=MUTED).pack(side="left"); tk.Entry(opts,textvariable=self.timeout_var,bg=PANEL2,fg=TEXT,insertbackground=TEXT,relief="flat",width=8).pack(side="left",padx=(8,16),ipady=4); tk.Checkbutton(opts,text="Continue on error",variable=self.continue_var,bg=BG,fg=TEXT,selectcolor=PANEL2,activebackground=BG,activeforeground=TEXT).pack(side="left"); b=tk.Frame(o,bg=BG); b.grid(row=4,column=0,columnspan=2,sticky="e",pady=(12,0)); ttk.Button(b,text="Cancel",command=self.destroy).pack(side="left",padx=(0,8)); ttk.Button(b,text="Save",command=self._save).pack(side="left")
    def _fields(self):
        previous=dict(self.original.config) if self.original and self.original.type==self.type_var.get() else {}
        for child in self.field_frame.winfo_children():child.destroy()
        self.inputs.clear()
        for row,(key,label) in enumerate(FIELDS[self.type_var.get()]):
            tk.Label(self.field_frame,text=label,bg=BG,fg=MUTED).grid(row=row*2,column=0,sticky="w",pady=(5,0)); multi=key in {"content","body","headers"}
            if multi:
                w=tk.Text(self.field_frame,height=4,width=58,bg=PANEL2,fg=TEXT,insertbackground=TEXT,relief="flat",font=("Cascadia Mono",9)); v=previous.get(key,""); v=json.dumps(v,indent=2) if key=="headers" and isinstance(v,dict) else v; w.insert("1.0",str(v))
            else:
                w=tk.Entry(self.field_frame,width=60,bg=PANEL2,fg=TEXT,insertbackground=TEXT,relief="flat"); w.insert(0,str(previous.get(key,"GET" if key=="method" else "1" if key=="seconds" else "")))
            w.grid(row=row*2+1,column=0,sticky="ew",pady=(3,4),ipady=5 if not multi else 0); self.inputs[key]=w
    def _save(self):
        cfg={}
        for key,w in self.inputs.items():
            value=w.get("1.0","end-1c") if isinstance(w,tk.Text) else w.get()
            if key=="headers":
                try:value=json.loads(value or "{}"); assert isinstance(value,dict)
                except Exception:messagebox.showerror("Forge","Headers must be a JSON object.",parent=self); return
            elif key=="seconds":
                try:value=float(value)
                except ValueError:messagebox.showerror("Forge","Seconds must be a number.",parent=self); return
            cfg[key]=value
        try:timeout=float(self.timeout_var.get() or 0)
        except ValueError:messagebox.showerror("Forge","Timeout must be a number.",parent=self); return
        self.result=Step(self.type_var.get(),cfg,self.name_var.get(),timeout,self.continue_var.get(),self.original.id if self.original else "")
        if not self.result.id:
            import uuid; self.result.id=uuid.uuid4().hex[:10]
        self.destroy()

class ForgeApp(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("Forge — local workflow runner"); self.geometry("1160x760"); self.minsize(900,620); self.configure(bg=BG); self.store=ForgeStore(); self.workflows=self.store.load() or [Workflow("Build release",[Step("command",{"command":"python --version"},"Check Python"),Step("wait",{"seconds":1},"Brief pause")],"Example workflow — edit or replace it.")]; self.runner=WorkflowRunner(self._log_threadsafe); self.running=False; self._style(); self._build(); self._refresh_workflows(0)
    def _style(self):
        s=ttk.Style(self); s.theme_use("clam"); s.configure("TFrame",background=BG); s.configure("TLabel",background=BG,foreground=TEXT); s.configure("Title.TLabel",background=BG,foreground=TEXT,font=("Segoe UI Semibold",22)); s.configure("Muted.TLabel",background=BG,foreground=MUTED); s.configure("TButton",background=PANEL2,foreground=TEXT,borderwidth=0,padding=(11,8)); s.configure("Accent.TButton",background=ACCENT,foreground="#171009",padding=(15,9),font=("Segoe UI Semibold",10)); s.configure("Danger.TButton",background="#54252a",foreground="#ffdadd"); s.configure("Treeview",background=PANEL,fieldbackground=PANEL,foreground=TEXT,rowheight=30,borderwidth=0); s.configure("Treeview.Heading",background=PANEL2,foreground=MUTED,borderwidth=0); s.map("Treeview",background=[("selected","#41301c")])
    def _build(self):
        h=ttk.Frame(self); h.pack(fill="x",padx=20,pady=(18,10)); ttk.Label(h,text="Forge",style="Title.TLabel").pack(side="left"); ttk.Label(h,text="  turn repeated work into a local workflow",style="Muted.TLabel").pack(side="left",pady=(7,0)); ttk.Button(h,text="Run",style="Accent.TButton",command=self._run).pack(side="right"); ttk.Button(h,text="Stop",style="Danger.TButton",command=self.runner.stop).pack(side="right",padx=(0,8)); p=ttk.Panedwindow(self,orient="horizontal"); p.pack(fill="both",expand=True,padx=18,pady=(0,18)); left=ttk.Frame(p); center=ttk.Frame(p); p.add(left,weight=1); p.add(center,weight=4); ttk.Label(left,text="WORKFLOWS",style="Muted.TLabel").pack(anchor="w",pady=(0,6)); self.workflow_list=tk.Listbox(left,bg=PANEL,fg=TEXT,selectbackground="#5c421f",selectforeground=TEXT,relief="flat",highlightthickness=0); self.workflow_list.pack(fill="both",expand=True); self.workflow_list.bind("<<ListboxSelect>>",lambda _:self._workflow_changed()); r=ttk.Frame(left); r.pack(fill="x",pady=(8,0)); ttk.Button(r,text="New",command=self._new).pack(side="left",expand=True,fill="x"); ttk.Button(r,text="Delete",command=self._delete).pack(side="left",expand=True,fill="x",padx=(6,0)); ttk.Button(left,text="Import .forge.json",command=self._import).pack(fill="x",pady=(6,0)); ttk.Button(left,text="Export selected",command=self._export).pack(fill="x",pady=(6,0)); self.workflow_name=tk.StringVar(); self.name=tk.Entry(center,textvariable=self.workflow_name,bg=PANEL2,fg=TEXT,insertbackground=TEXT,relief="flat",font=("Segoe UI Semibold",13)); self.name.pack(fill="x",ipady=7); self.name.bind("<FocusOut>",lambda _:self._save_meta()); self.desc=tk.Entry(center,bg=PANEL,fg=MUTED,insertbackground=TEXT,relief="flat"); self.desc.pack(fill="x",ipady=6,pady=(0,10)); self.desc.bind("<FocusOut>",lambda _:self._save_meta()); self.steps=ttk.Treeview(center,columns=("type","detail"),show="headings"); self.steps.heading("type",text="Type"); self.steps.heading("detail",text="Step"); self.steps.column("type",width=110); self.steps.column("detail",width=600); self.steps.pack(fill="both",expand=True); self.steps.bind("<Double-1>",lambda _:self._edit()); c=ttk.Frame(center); c.pack(fill="x",pady=8)
        for label,cmd in (("+ Add",self._add),("Edit",self._edit),("Duplicate",self._dup),("Remove",self._remove),("↑",lambda:self._move(-1)),("↓",lambda:self._move(1))):ttk.Button(c,text=label,command=cmd).pack(side="left",padx=(0,6))
        ttk.Label(center,text="RUN LOG",style="Muted.TLabel").pack(anchor="w"); self.log=tk.Text(center,height=12,bg="#0d1116",fg="#bac5cf",relief="flat",font=("Cascadia Mono",9),padx=10,pady=8); self.log.pack(fill="both",pady=(5,0))
    def _idx(self):
        s=self.workflow_list.curselection(); return int(s[0]) if s else None
    def _flow(self):
        i=self._idx(); return self.workflows[i] if i is not None and i<len(self.workflows) else None
    def _refresh_workflows(self,select=None):
        self.workflow_list.delete(0,"end"); [self.workflow_list.insert("end",w.name) for w in self.workflows]
        if self.workflows:
            i=min(select if select is not None else (self._idx() or 0),len(self.workflows)-1); self.workflow_list.selection_set(i); self._workflow_changed()
        self.store.save(self.workflows)
    def _workflow_changed(self):
        f=self._flow()
        if not f:return
        self.workflow_name.set(f.name); self.desc.delete(0,"end"); self.desc.insert(0,f.description); self._refresh_steps()
    def _refresh_steps(self):
        self.steps.delete(*self.steps.get_children()); f=self._flow()
        if f:
            for i,s in enumerate(f.steps):self.steps.insert("","end",iid=str(i),values=(s.type.upper(),s.label()))
    def _save_meta(self):
        f=self._flow()
        if f:f.name=self.workflow_name.get().strip() or "Untitled workflow"; f.description=self.desc.get().strip(); self.store.save(self.workflows)
    def _new(self):
        n=simpledialog.askstring("New workflow","Workflow name",parent=self)
        if n:self.workflows.append(Workflow(n.strip())); self._refresh_workflows(len(self.workflows)-1)
    def _delete(self):
        i=self._idx()
        if i is not None and messagebox.askyesno("Forge",f"Delete workflow '{self.workflows[i].name}'?",parent=self):self.workflows.pop(i); self._refresh_workflows(max(0,i-1))
    def _sidx(self):
        s=self.steps.selection(); return int(s[0]) if s else None
    def _add(self):
        f=self._flow(); d=StepDialog(self)
        if f and d.result:f.steps.append(d.result); self.store.save(self.workflows); self._refresh_steps()
    def _edit(self):
        f=self._flow(); i=self._sidx()
        if f is None or i is None:return
        d=StepDialog(self,f.steps[i])
        if d.result:f.steps[i]=d.result; self.store.save(self.workflows); self._refresh_steps(); self.steps.selection_set(str(i))
    def _dup(self):
        f=self._flow(); i=self._sidx()
        if f is None or i is None:return
        s=Step.from_dict(f.steps[i].to_dict()); import uuid; s.id=uuid.uuid4().hex[:10]; f.steps.insert(i+1,s); self.store.save(self.workflows); self._refresh_steps(); self.steps.selection_set(str(i+1))
    def _remove(self):
        f=self._flow(); i=self._sidx()
        if f is not None and i is not None:f.steps.pop(i); self.store.save(self.workflows); self._refresh_steps()
    def _move(self,d):
        f=self._flow(); i=self._sidx(); t=(i+d) if i is not None else -1
        if f is not None and i is not None and 0<=t<len(f.steps):f.steps[i],f.steps[t]=f.steps[t],f.steps[i]; self.store.save(self.workflows); self._refresh_steps(); self.steps.selection_set(str(t))
    def _run(self):
        if self.running:return
        f=self._flow()
        if not f:return
        if any(s.type=="delete" for s in f.steps) and not messagebox.askyesno("Forge","This workflow contains a delete step. Review it carefully before continuing.\n\nRun anyway?",parent=self):return
        self.running=True; self.log.delete("1.0","end")
        def work():self.runner.run(f); self.after(0,lambda:setattr(self,"running",False))
        threading.Thread(target=work,daemon=True).start()
    def _log_threadsafe(self,line):self.after(0,lambda:self._append(line))
    def _append(self,line):self.log.insert("end",line+"\n"); self.log.see("end")
    def _import(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[("Forge workflow","*.json"),("JSON","*.json")])
        if p:
            try:self.workflows.append(self.store.import_workflow(Path(p))); self._refresh_workflows(len(self.workflows)-1)
            except Exception as e:messagebox.showerror("Forge",f"Could not import workflow:\n{e}",parent=self)
    def _export(self):
        f=self._flow()
        if not f:return
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".forge.json",initialfile="workflow.forge.json",filetypes=[("Forge workflow","*.forge.json")])
        if p:self.store.export_workflow(f,Path(p))

def main():ForgeApp().mainloop()
