import json, os, sys, tempfile, threading, time, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from forge.engine import WorkflowRunner
from forge.models import Step, Workflow
from forge.storage import ForgeStore

PY = f'"{sys.executable}"'


def run(*steps):
    log = []; ok = WorkflowRunner(log.append).run(Workflow('t', list(steps))); return ok, log


class FileStepTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(); self.d = Path(self._tmp.name)
    def tearDown(self):
        self._tmp.cleanup()

    def test_copy_file_and_directory(self):
        (self.d / 'src').mkdir(); (self.d / 'src' / 'a.txt').write_text('a')
        ok, _ = run(Step('copy', {'source': str(self.d / 'src' / 'a.txt'), 'target': str(self.d / 'out' / 'b.txt')}),
                    Step('copy', {'source': str(self.d / 'src'), 'target': str(self.d / 'mirror')}))
        self.assertTrue(ok); self.assertEqual((self.d / 'out' / 'b.txt').read_text(), 'a'); self.assertTrue((self.d / 'mirror' / 'a.txt').exists())

    def test_move_append_and_delete(self):
        f = self.d / 'log.txt'
        ok, _ = run(Step('write', {'path': str(f), 'content': 'one\n'}), Step('write', {'path': str(f), 'content': 'two\n', 'append': True}),
                    Step('move', {'source': str(f), 'target': str(self.d / 'archive' / 'log.txt')}),
                    Step('delete', {'path': str(self.d / 'archive')}), Step('delete', {'path': str(self.d / 'never-existed')}))
        self.assertTrue(ok); self.assertFalse((self.d / 'archive').exists())

    def test_failure_halts_the_workflow(self):
        marker = self.d / 'after.txt'
        ok, log = run(Step('copy', {'source': str(self.d / 'missing'), 'target': str(self.d / 'x')}), Step('write', {'path': str(marker), 'content': 'x'}))
        self.assertFalse(ok); self.assertFalse(marker.exists()); self.assertIn('Workflow halted', log)


class CommandStepTests(unittest.TestCase):
    def test_output_is_logged_and_cwd_is_honoured(self):
        with tempfile.TemporaryDirectory() as d:
            ok, log = run(Step('command', {'command': f'{PY} -c "import os; print(os.getcwd())"', 'cwd': d}))
        self.assertTrue(ok); self.assertTrue(any(Path(line.strip()).resolve() == Path(d).resolve() for line in log if line.startswith('    ')))

    def test_nonzero_exit_fails(self):
        ok, log = run(Step('command', {'command': f'{PY} -c "raise SystemExit(3)"'}))
        self.assertFalse(ok); self.assertTrue(any('code 3' in line for line in log))

    def test_empty_command_fails(self):
        self.assertFalse(run(Step('command', {'command': '  '}))[0])

    def test_timeout_stops_a_slow_command(self):
        started = time.monotonic()
        ok, log = run(Step('command', {'command': f'{PY} -c "import time; time.sleep(30)"'}, timeout=0.5))
        self.assertFalse(ok); self.assertLess(time.monotonic() - started, 10); self.assertTrue(any('timeout' in line for line in log))

    def _pid_alive(self, pid):
        # A killed orphan can linger as a zombie until init reaps it; that is dead.
        status = Path(f'/proc/{pid}/status')
        if status.exists():
            return '\tZ' not in next((l for l in status.read_text().splitlines() if l.startswith('State:')), '')
        try:
            os.kill(pid, 0); return True
        except OSError:
            return False

    @unittest.skipIf(os.name == 'nt', 'uses POSIX signals to probe the child')
    def test_timeout_kills_the_command_not_just_its_shell(self):
        with tempfile.TemporaryDirectory() as d:
            pidfile = Path(d) / 'pid'
            cmd = f'{PY} -c "import os, time, pathlib; pathlib.Path(r\'{pidfile}\').write_text(str(os.getpid())); time.sleep(30)"'
            ok, _ = run(Step('command', {'command': cmd}, timeout=1))
            self.assertFalse(ok); time.sleep(0.3)
            self.assertFalse(self._pid_alive(int(pidfile.read_text())), 'the command survived its timeout')

    @unittest.skipIf(os.name == 'nt', 'uses POSIX signals to probe the child')
    def test_stop_kills_a_running_command(self):
        with tempfile.TemporaryDirectory() as d:
            pidfile = Path(d) / 'pid'
            cmd = f'{PY} -c "import os, time, pathlib; pathlib.Path(r\'{pidfile}\').write_text(str(os.getpid())); time.sleep(30)"'
            runner = WorkflowRunner(); threading.Timer(1.0, runner.stop).start(); started = time.monotonic()
            self.assertFalse(runner.run(Workflow('t', [Step('command', {'command': cmd})])))
            self.assertLess(time.monotonic() - started, 10); time.sleep(0.3)
            self.assertFalse(self._pid_alive(int(pidfile.read_text())), 'the command survived Stop')

    def test_stop_interrupts_a_wait(self):
        runner = WorkflowRunner(); threading.Timer(0.2, runner.stop).start(); started = time.monotonic()
        self.assertFalse(runner.run(Workflow('t', [Step('wait', {'seconds': 30})])))
        self.assertLess(time.monotonic() - started, 5)


class HttpStepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                code = 500 if self.path == '/fail' else 200
                self.send_response(code); self.end_headers(); self.wfile.write(b'{"status":"ok"}')
            def log_message(self, *a): pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.server.server_address[1]}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()

    def test_success_logs_status_and_body(self):
        ok, log = run(Step('http', {'url': self.base + '/health'}))
        self.assertTrue(ok); self.assertIn('    HTTP 200 OK', log)

    def test_http_error_fails_the_step(self):
        self.assertFalse(run(Step('http', {'url': self.base + '/fail'}))[0])

    def test_headers_must_be_an_object(self):
        self.assertFalse(run(Step('http', {'url': self.base, 'headers': ['x']}))[0])


class ModelAndStorageTests(unittest.TestCase):
    def test_unknown_step_type_is_rejected(self):
        with self.assertRaises(ValueError):
            Step('teleport')

    def test_labels_fall_back_to_a_description(self):
        self.assertEqual(Step('http', {'method': 'POST', 'url': 'http://x'}).label(), 'POST http://x')
        self.assertEqual(Step('wait', {'seconds': 2}, name='  Pause  ').label(), 'Pause')

    def test_corrupt_store_loads_as_empty_and_import_rejects_lists(self):
        with tempfile.TemporaryDirectory() as d:
            store = ForgeStore(Path(d)); store.path.write_text('{not json'); self.assertEqual(store.load(), [])
            bad = Path(d) / 'bad.forge.json'; bad.write_text('[]')
            with self.assertRaises(ValueError):
                ForgeStore.import_workflow(bad)

    def test_export_import_round_trip(self):
        wf = Workflow('Deploy', [Step('command', {'command': 'echo hi'}, timeout=5, continue_on_error=True)], 'desc')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'deploy.forge.json'; ForgeStore.export_workflow(wf, p); back = ForgeStore.import_workflow(p)
        self.assertEqual(back.to_dict(), wf.to_dict())


if __name__ == '__main__':
    unittest.main()
