from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any
import uuid

STEP_TYPES=("command","copy","move","mkdir","write","delete","http","wait","open")

@dataclass
class Step:
    type:str
    config:dict[str,Any]=field(default_factory=dict)
    name:str=""
    timeout:float=0.0
    continue_on_error:bool=False
    id:str=field(default_factory=lambda:uuid.uuid4().hex[:10])
    def __post_init__(self):
        if self.type not in STEP_TYPES: raise ValueError(f"Unknown step type: {self.type}")
    def label(self):
        if self.name.strip(): return self.name.strip()
        detail={"command":self.config.get("command","Run command"),"copy":f"Copy {self.config.get('source','')}","move":f"Move {self.config.get('source','')}","mkdir":f"Create {self.config.get('path','')}","write":f"Write {self.config.get('path','')}","delete":f"Delete {self.config.get('path','')}","http":f"{self.config.get('method','GET')} {self.config.get('url','')}","wait":f"Wait {self.config.get('seconds',1)}s","open":f"Open {self.config.get('path','')}"}.get(self.type,self.type)
        return str(detail)[:80]
    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls,data): return cls(type=str(data.get("type","command")),config=dict(data.get("config",{})),name=str(data.get("name","")),timeout=float(data.get("timeout",0) or 0),continue_on_error=bool(data.get("continue_on_error",False)),id=str(data.get("id") or uuid.uuid4().hex[:10]))

@dataclass
class Workflow:
    name:str
    steps:list[Step]=field(default_factory=list)
    description:str=""
    def to_dict(self): return {"name":self.name,"description":self.description,"steps":[s.to_dict() for s in self.steps]}
    @classmethod
    def from_dict(cls,data): return cls(name=str(data.get("name","Untitled workflow")),description=str(data.get("description","")),steps=[Step.from_dict(x) for x in list(data.get("steps",[])) if isinstance(x,dict)])
