from __future__ import annotations
import json
from pathlib import Path
from .models import Workflow

class ForgeStore:
    def __init__(self,root:Path|None=None):
        self.root=root or Path.home()/".forge"; self.root.mkdir(parents=True,exist_ok=True); self.path=self.root/"workflows.json"
    def load(self):
        try:
            raw=json.loads(self.path.read_text(encoding="utf-8")); return [Workflow.from_dict(x) for x in raw if isinstance(x,dict)] if isinstance(raw,list) else []
        except (FileNotFoundError,json.JSONDecodeError,OSError,ValueError): return []
    def save(self,workflows):
        tmp=self.path.with_suffix(".tmp"); tmp.write_text(json.dumps([w.to_dict() for w in workflows],indent=2,ensure_ascii=False),encoding="utf-8"); tmp.replace(self.path)
    @staticmethod
    def export_workflow(workflow,path:Path): path.write_text(json.dumps(workflow.to_dict(),indent=2,ensure_ascii=False),encoding="utf-8")
    @staticmethod
    def import_workflow(path:Path):
        raw=json.loads(path.read_text(encoding="utf-8"));
        if not isinstance(raw,dict): raise ValueError("Workflow file must contain one JSON object.")
        return Workflow.from_dict(raw)
