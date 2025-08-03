
import asyncio
import time
import random
from dataclasses import dataclass
from typing import Optional, Callable, Any

# NOTE: This is a standalone robust implementation scaffold for jsplan/tools usage.
# It mirrors Agent Zero Tool API shape minimally to integrate as a drop-in tool module.

# ---------------------- Robustness helpers (Injected) ----------------------
class _Backoff:
    def __init__(self, base: float = 0.2, factor: float = 2.0, max_delay: float = 5.0, max_retries: int = 6):
        self.base = base
        self.factor = factor
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.attempt = 0
    def sleep(self):
        if self.attempt >= self.max_retries:
            raise TimeoutError('backoff_exceeded')
        delay = min(self.base * (self.factor ** self.attempt), self.max_delay)
        jitter = delay * 0.15
        time.sleep(max(0.0, delay + random.uniform(-jitter, jitter)))
        self.attempt += 1
    def reset(self):
        self.attempt = 0

class _AsyncReader:
    def __init__(self, read_fn: Callable[[], bytes], on_chunk: Callable[[bytes], None], log: Callable[[str, dict], None], stall_sec: float = 15.0):
        self._read_fn = read_fn
        self._on_chunk = on_chunk
        self._log = log
        self._stall_sec = stall_sec
        self._last_activity = time.time()
        self._stop = False
        self._loop = asyncio.get_event_loop()
        self._task: Optional[asyncio.Task] = None
    async def _run(self):
        try:
            while not self._stop:
                try:
                    data = self._read_fn()
                    if not data:
                        self._log('reader_eof', {})
                        break
                    self._on_chunk(data)
                    self._last_activity = time.time()
                except Exception as e:  # read error
                    self._log('reader_error', {'error': str(e)})
                    break
                if (time.time() - self._last_activity) > self._stall_sec:
                    self._log('reader_stall_heartbeat', {'silence_sec': time.time() - self._last_activity})
                    self._last_activity = time.time()
                await asyncio.sleep(0.01)
        finally:
            self._log('reader_stopped', {})
    def start(self):
        if not self._task or self._task.done():
            self._task = self._loop.create_task(self._run())
    async def stop(self):
        self._stop = True
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except Exception:
                pass
            self._task = None

class _SocketClosedError(Exception):
    pass

class _SocketWrapper:
    def __init__(self, connect_fn: Callable[[], Any], recv_fn_name: str = 'recv', send_fn_name: str = 'sendall', log: Optional[Callable[[str, dict], None]] = None):
        self._connect_fn = connect_fn
        self._recv_name = recv_fn_name
        self._send_name = send_fn_name
        self._log = log or (lambda e, f: None)
        self._sock = self._connect()
    def _connect(self):
        s = self._connect_fn()
        self._log('socket_connected', {})
        return s
    def close(self):
        try:
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
        finally:
            self._sock = None
    def _reconnect_with_backoff(self):
        backoff = _Backoff()
        while True:
            try:
                self.close()
                self._sock = self._connect()
                backoff.reset()
                self._log('socket_reconnected', {'attempts': backoff.attempt})
                return
            except Exception as e:
                self._log('socket_reconnect_failed', {'attempt': backoff.attempt + 1, 'error': str(e)})
                backoff.sleep()
    def send(self, data: bytes):
        backoff = _Backoff()
        while True:
            try:
                getattr(self._sock, self._send_name)(data)
                return
            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                self._log('socket_send_error', {'error': str(e)})
                try:
                    self._reconnect_with_backoff()
                except Exception as e2:
                    self._log('socket_send_giveup', {'error': str(e2)})
                    raise
                backoff.sleep()
    def recv(self, n: int) -> bytes:
        backoff = _Backoff()
        while True:
            try:
                data = getattr(self._sock, self._recv_name)(n)
                if data == b'':
                    raise _SocketClosedError('socket_eof')
                return data
            except (_SocketClosedError, ConnectionResetError, OSError) as e:
                self._log('socket_recv_error', {'error': str(e)})
                try:
                    self._reconnect_with_backoff()
                except Exception as e2:
                    self._log('socket_recv_giveup', {'error': str(e2)})
                    raise
                backoff.sleep()

# ---------------------- Minimal Tool integration scaffold ----------------------
@dataclass
class Response:
    message: str

class CodeExecution:
    name = 'code_execution_tool'
    def __init__(self, agent=None, args=None):
        self.agent = agent
        self.args = args or {}
        self._last_terminal_command: Optional[str] = None
    def _log(self, event: str, fields: Optional[dict] = None):
        ts = time.strftime('%Y-%m-%dT%H:%M:%S')
        print(f"[CET_LOG ts={ts} event={event} fields={fields or {}}]")
    async def execute(self, **kwargs):
        runtime = (self.args.get('runtime') or '').lower().strip()
        session = int(self.args.get('session', 0))
        if runtime == 'reset':
            return await self.reset_terminal(session=session)
        elif runtime == 'output':
            return Response(message='output_wait_not_implemented_in_jsplan_scaffold')
        elif runtime == 'terminal':
            cmd = self.args.get('code', '')
            self._last_terminal_command = cmd
            try:
                out = await self.execute_terminal_command(command=cmd, session=session)
                return Response(message=out)
            except Exception as e:
                self._log('terminal_error', {'error': str(e)})
                await self.reset_terminal(session=session)
                if session == 0 and self._last_terminal_command:
                    self._log('auto_continue_after_reset', {'session': session})
                    out = await self.execute_terminal_command(command=self._last_terminal_command, session=session)
                    return Response(message=out)
                raise
        elif runtime == 'python':
            code = self.args.get('code', '')
            loc = {}
            exec(code, {}, loc)
            return Response(message=str(loc.get('_', '')))
        elif runtime == 'nodejs':
            return Response(message='nodejs_not_implemented_in_jsplan_scaffold')
        else:
            return Response(message=f'unknown_runtime:{runtime}')
    async def reset_terminal(self, session: int = 0):
        self._log('terminal_reset', {'session': session})
        return Response(message='[SYSTEM: Terminal session has been reset.] ')
    async def execute_terminal_command(self, command: str, session: int = 0) -> str:
        self._log('terminal_exec_start', {'session': session})
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            executable='/bin/bash',
        )
        output_chunks = []
        first_ts = time.time()
        last_ts = time.time()
        between_timeout = 30.0
        first_timeout = 60.0
        while True:
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
            except asyncio.TimeoutError:
                now = time.time()
                if not output_chunks and now - first_ts > first_timeout:
                    self._log('terminal_first_output_timeout', {'timeout': first_timeout})
                    break
                if output_chunks and now - last_ts > between_timeout:
                    self._log('terminal_between_output_timeout', {'timeout': between_timeout})
                    break
                continue
            if not line:
                break
            output_chunks.append(line.decode(errors='replace'))
            last_ts = time.time()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
        out = ''.join(output_chunks)
        self._log('terminal_exec_end', {'bytes': len(out)})
        return out

# Factory for the framework to pick up
Tool = CodeExecution
