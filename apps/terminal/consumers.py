import asyncio
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
    from channels.db import database_sync_to_async
except ImportError:
    class AsyncWebsocketConsumer:
        pass
    def database_sync_to_async(func):
        return func


class TerminalConsumer(AsyncWebsocketConsumer):
    """
    Bidirectional WebSocket consumer bridging xterm.js in the browser
    to the target Docker container's pseudo-terminal (PTY).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = None
        self.sock = None
        self.read_task = None
        self.is_connected = False
        self._sim_buffer = []

    @database_sync_to_async
    def get_lab_instance(self, instance_id, user):
        from apps.labs.models import LabInstance
        from apps.users.models import UserRole
        try:
            instance = LabInstance.objects.select_related('lab').get(id=instance_id)
            if user.role in [UserRole.ADMIN, UserRole.TEACHER] or instance.user_id == user.id:
                return instance
        except Exception as e:
            logger.debug(f"Terminal instance lookup error: {e}")
        return None

    async def connect(self):
        self.instance_id = self.scope['url_route']['kwargs']['instance_id']
        self.user = self.scope.get('user')

        # 1. Require authenticated session
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        # 2. Verify access to instance
        self.instance = await self.get_lab_instance(self.instance_id, self.user)
        if not self.instance:
            await self.close(code=4404)
            return

        await self.accept()
        self.is_connected = True

        # Send welcome header
        welcome_banner = (
            "\r\n\x1b[1;36m========================================================\x1b[0m\r\n"
            f"\x1b[1;32m  MYANMAR E-LEARNING - ISOLATED LAB TERMINAL\x1b[0m\r\n"
            f"\x1b[0;37m  Target Environment: {self.instance.lab.title}\x1b[0m\r\n"
            f"\x1b[0;37m  Logged in as: {self.user.username} (Restricted Sandboxed Access)\x1b[0m\r\n"
            "\x1b[1;36m========================================================\x1b[0m\r\n\r\n"
        )
        await self.send(text_data=welcome_banner)

        # 3. Attach to real container PTY if Docker engine is available
        container_id = self.instance.container_id
        docker_attached = False

        if container_id and not str(container_id).startswith("sim-"):
            docker_attached = await self._attach_docker_pty(container_id)

        if not docker_attached:
            # Fallback to simulated shell
            await self.send(
                text_data="\x1b[33m[Connected to environment sandbox shell]\x1b[0m\r\nstudent@ftcr-lab:~$ "
            )

    async def _attach_docker_pty(self, container_id) -> bool:
        """Attach to container exec stream with interactive PTY."""
        from apps.labs.orchestrator import orchestrator
        client = orchestrator.client
        if not client:
            return False

        try:
            loop = asyncio.get_running_loop()

            def _start_exec():
                try:
                    container = client.containers.get(container_id)
                    # Try bash first, then sh
                    exec_instance = client.api.exec_create(
                        container.id,
                        cmd=['/bin/bash'],
                        stdin=True,
                        stdout=True,
                        stderr=True,
                        tty=True,
                        environment={'TERM': 'xterm-256color', 'HOME': '/home/student'},
                    )
                except Exception:
                    container = client.containers.get(container_id)
                    exec_instance = client.api.exec_create(
                        container.id,
                        cmd=['/bin/sh'],
                        stdin=True,
                        stdout=True,
                        stderr=True,
                        tty=True,
                        environment={'TERM': 'xterm-256color', 'HOME': '/root'},
                    )
                exec_id = exec_instance['Id']
                sock = client.api.exec_start(exec_id, socket=True, tty=True)
                return sock

            self.sock = await loop.run_in_executor(None, _start_exec)
            self.read_task = asyncio.create_task(self._docker_read_loop())
            return True
        except Exception as e:
            logger.warning(f"Could not attach Docker PTY for container {container_id}: {e}")
            self.sock = None
            return False

    async def _docker_read_loop(self):
        """Continuously stream stdout/stderr from container PTY socket to xterm.js."""
        loop = asyncio.get_running_loop()
        raw_sock = getattr(self.sock, '_sock', self.sock)
        try:
            raw_sock.setblocking(False)
        except Exception:
            pass

        while self.is_connected and self.sock:
            try:
                data = await loop.sock_recv(raw_sock, 4096)
                if not data:
                    break
                await self.send(text_data=data.decode('utf-8', errors='replace'))
            except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
                break
            except Exception as e:
                logger.debug(f"Docker PTY read error: {e}")
                break

        if self.is_connected:
            await self.send(text_data="\r\n\x1b[31m[Container session closed]\x1b[0m\r\n")

    async def disconnect(self, close_code):
        self.is_connected = False
        if self.read_task and not self.read_task.done():
            self.read_task.cancel()
        if self.sock:
            try:
                raw_sock = getattr(self.sock, '_sock', self.sock)
                raw_sock.close()
            except Exception:
                pass
            self.sock = None
        logger.info(f"Terminal WebSocket disconnected for instance {getattr(self, 'instance_id', 'unknown')}")

    async def receive(self, text_data=None, bytes_data=None):
        """Receives keystrokes from xterm.js and forwards to container PTY or simulation shell."""
        if not self.is_connected:
            return

        payload = (text_data or '').encode('utf-8') if text_data is not None else bytes_data
        if not payload:
            return

        # 1. Real Docker PTY Mode
        if self.sock:
            try:
                loop = asyncio.get_running_loop()
                raw_sock = getattr(self.sock, '_sock', self.sock)
                await loop.sock_sendall(raw_sock, payload)
                return
            except Exception as e:
                logger.warning(f"Failed to send to Docker PTY: {e}")

        # 2. Fallback Simulation Shell Mode
        await self._handle_simulation_input(text_data or payload.decode('utf-8', errors='replace'))

    async def _handle_simulation_input(self, text: str):
        """Interactive simulated terminal shell for dev/testing when Docker daemon is not bound."""
        flag = getattr(self.instance, 'dynamic_flag', None) or "FTCR{demo_flag_student_sandbox}"

        for char in text:
            if char in ('\r', '\n'):
                cmd = ''.join(self._sim_buffer).strip()
                self._sim_buffer = []
                await self.send(text_data="\r\n")

                if cmd:
                    parts = cmd.split()
                    c = parts[0].lower()
                    if c in ('whoami', 'id'):
                        await self.send(text_data="student (uid=1000 gid=1000)\r\n")
                    elif c == 'pwd':
                        await self.send(text_data="/home/student\r\n")
                    elif c == 'ls':
                        await self.send(text_data="app.py  flag.txt  notes.txt  README.md\r\n")
                    elif c == 'cat':
                        target = parts[1] if len(parts) > 1 else ''
                        if 'flag' in target.lower():
                            await self.send(text_data=f"{flag}\r\n")
                        elif 'notes' in target.lower() or 'readme' in target.lower():
                            await self.send(text_data="Objective: Find the vulnerability and submit the flag.\r\n")
                        elif 'app' in target.lower():
                            await self.send(text_data="# Application Target source code\r\nprint('Running challenge')\r\n")
                        else:
                            await self.send(text_data=f"cat: {target}: No such file or directory\r\n")
                    elif c in ('uname', 'uname -a'):
                        await self.send(text_data="Linux ftcr-sandbox 6.1.0-ftcr #1 SMP PREEMPT x86_64 GNU/Linux\r\n")
                    elif c == 'help':
                        await self.send(text_data="Built-in commands: whoami, id, pwd, ls, cat, uname, clear, exit, help\r\n")
                    elif c == 'clear':
                        await self.send(text_data="\x1b[2J\x1b[H")
                    elif c == 'exit':
                        await self.send(text_data="[Process completed]\r\n")
                        await self.close()
                        return
                    else:
                        await self.send(text_data=f"bash: {c}: command not found\r\n")

                await self.send(text_data="student@ftcr-lab:~$ ")
            elif char == '\x7f' or char == '\b':  # Backspace
                if self._sim_buffer:
                    self._sim_buffer.pop()
                    await self.send(text_data="\b \b")
            elif char == '\x03':  # Ctrl+C
                self._sim_buffer = []
                await self.send(text_data="^C\r\nstudent@ftcr-lab:~$ ")
            else:
                self._sim_buffer.append(char)
                await self.send(text_data=char)
