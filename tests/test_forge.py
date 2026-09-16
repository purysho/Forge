import tempfile,unittest
from pathlib import Path
from forge.engine import WorkflowRunner
from forge.models import Step,Workflow
from forge.storage import ForgeStore

class ForgeTests(unittest.TestCase):
    def test_roundtrip(self):
        f=Workflow("Demo",steps=[Step("wait",{"seconds":.01},name="Pause")]); r=Workflow.from_dict(f.to_dict()); self.assertEqual(r.name,"Demo"); self.assertEqual(r.steps[0].type,"wait")
    def test_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=ForgeStore(Path(tmp)); s.save([Workflow("One")]); self.assertEqual(s.load()[0].name,"One")
    def test_write_and_mkdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"nested"/"hello.txt"; f=Workflow("Files",steps=[Step("mkdir",{"path":str(out.parent)}),Step("write",{"path":str(out),"content":"hello"})]); self.assertTrue(WorkflowRunner().run(f)); self.assertEqual(out.read_text(),"hello")
    def test_continue_on_error(self):
        f=Workflow("Continue",steps=[Step("command",{"command":"python -c \"import sys; sys.exit(4)\""},continue_on_error=True),Step("wait",{"seconds":.01})]); self.assertTrue(WorkflowRunner().run(f))
if __name__=="__main__":unittest.main()
