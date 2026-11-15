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

    @unittest.skipIf(os.name == 'nt', 'POSIX signals; Windows stops trees with taskkill /T /F')
    def test_stop_kills_a_child_that_ignores_sigterm_after_its_shell_exits(self):
        with tempfile.TemporaryDirectory() as d:
            pidfile = Path(d) / 'pid'
            child = Path(d) / 'stubborn.py'
            child.write_text(
                'import os, signal, time, pathlib\n'
                'signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
                f'pathlib.Path(r"{pidfile}").write_text(str(os.getpid()))\n'
                'time.sleep(60)\n', encoding='utf-8')
            # The shell dies on SIGTERM; the child it started does not.
            cmd = f'{PY} "{child}" & wait'
            runner = WorkflowRunner()
            def stop_when_started():
                while not pidfile.exists(): time.sleep(0.05)
                runner.stop()
            threading.Thread(target=stop_when_started, daemon=True).start()
            self.assertFalse(runner.run(Workflow('t', [Step('command', {'command': cmd})])))
            self.assertFalse(self._pid_alive(int(pidfile.read_text())), 'Forge said stopped while the command ran on')

    def test_a_stop_before_the_run_starts_is_not_forgotten(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'x'
            runner = WorkflowRunner(); runner.stop()
            self.assertFalse(runner.run(Workflow('t', [Step('write', {'path': str(out), 'content': 'x'})])))
            self.assertFalse(out.exists())
            runner.reset()
            self.assertTrue(runner.run(Workflow('t', [Step('write', {'path': str(out), 'content': 'x'})])))

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


class StructuredEventTests(unittest.TestCase):
    """on_event gives programs that drive Forge (Depot) progress without parsing log text."""

    def run_with_events(self, *steps):
        events = []
        ok = WorkflowRunner(lambda _: None, on_event=lambda kind, data: events.append((kind, data))).run(Workflow('t', list(steps)))
        return ok, events

    def test_success_reports_each_step_and_completion(self):
        with tempfile.TemporaryDirectory() as d:
            ok, events = self.run_with_events(Step('mkdir', {'path': str(Path(d) / 'a')}))
        self.assertTrue(ok)
        self.assertEqual([k for k, _ in events], ['step_started', 'step_succeeded', 'run_finished'])
        self.assertEqual(events[0][1]['type'], 'mkdir')
        self.assertEqual(events[-1][1], {'outcome': 'completed', 'failed_steps': 0})

    def test_failed_command_reports_its_pid_and_exit_code(self):
        ok, events = self.run_with_events(Step('command', {'command': f'{PY} -c "import sys; sys.exit(3)"'}))
        self.assertFalse(ok)
        failed = dict(events)['step_failed']
        self.assertIsInstance(failed['pid'], int)
        self.assertEqual(failed['exit_code'], 3)
        self.assertEqual(events[-1], ('run_finished', {'outcome': 'failed', 'failed_steps': 1}))

    def test_non_command_failure_has_no_pid(self):
        with tempfile.TemporaryDirectory() as d:
            ok, events = self.run_with_events(Step('copy', {'source': str(Path(d) / 'missing'), 'target': str(Path(d) / 'x')}))
        failed = dict(events)['step_failed']
        self.assertIsNone(failed['pid']); self.assertIsNone(failed['exit_code'])

    def test_continue_on_error_completes_and_counts_failures(self):
        with tempfile.TemporaryDirectory() as d:
            ok, events = self.run_with_events(
                Step('copy', {'source': str(Path(d) / 'missing'), 'target': str(Path(d) / 'x')}, continue_on_error=True),
                Step('mkdir', {'path': str(Path(d) / 'b')}))
        self.assertTrue(ok)
        self.assertEqual(events[-1], ('run_finished', {'outcome': 'completed', 'failed_steps': 1}))

    def test_a_broken_handler_does_not_break_the_run(self):
        log = []
        def boom(kind, data): raise RuntimeError('handler bug')
        with tempfile.TemporaryDirectory() as d:
            ok = WorkflowRunner(log.append, on_event=boom).run(Workflow('t', [Step('mkdir', {'path': str(Path(d) / 'a')})]))
        self.assertTrue(ok)
        self.assertTrue(any('event handler failed' in line for line in log))


class PathSafetyTests(unittest.TestCase):
    """A blank path means the current folder to pathlib; Forge must refuse it, not act on it."""

    def test_blank_paths_are_refused_and_nothing_is_touched(self):
        with tempfile.TemporaryDirectory() as d:
            keep = Path(d) / "keep.txt"
            keep.write_text("x")
            old = os.getcwd()
            os.chdir(d)
            try:
                for step in (
                    Step('delete', {'path': ''}),
                    Step('delete', {'path': '   '}),
                    Step('delete', {}),
                    Step('mkdir', {'path': ''}),
                    Step('write', {'path': '', 'content': 'x'}),
                    Step('copy', {'source': '', 'target': str(Path(d) / 'out')}),
                    Step('move', {'source': str(keep), 'target': ''}),
                ):
                    ok, log = run(step)
                    self.assertFalse(ok, step.config)
                    self.assertTrue(any('is empty' in line for line in log), log)
            finally:
                os.chdir(old)
            self.assertTrue(keep.exists())

    def test_delete_refuses_home_root_and_the_running_folder(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.getcwd()
            os.chdir(d)
            try:
                for target in ('.', d, str(Path(d).parent), str(Path.home()), Path(d).anchor):
                    ok, log = run(Step('delete', {'path': target}))
                    self.assertFalse(ok, target)
                    self.assertTrue(any('Refusing to delete' in line for line in log), log)
                self.assertTrue(Path(d).exists())
            finally:
                os.chdir(old)

    def test_ordinary_deletes_still_work(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'build'
            (target / 'sub').mkdir(parents=True)
            ok, _ = run(Step('delete', {'path': str(target)}))
            self.assertTrue(ok)
            self.assertFalse(target.exists())
