import json
import logging
import asyncio
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
except ImportError:
    class AsyncWebsocketConsumer:
        pass

class TerminalConsumer(AsyncWebsocketConsumer):
    """
    Bidirectional WebSocket consumer bridging xterm.js in the browser
    to the target Docker container's pseudo-terminal (PTY).
    """

    async def connect(self):
        self.instance_id = self.scope['url_route']['kwargs']['instance_id']
        self.user = self.scope.get('user')

        # 1. Require authenticated session
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        await self.accept()

        # Send welcome header
        welcome_banner = (
            "\r\n\x1b[1;36m========================================================\x1b[0m\r\n"
            f"\x1b[1;32m  FUTURE TECH CYBER RANGE - ISOLATED LAB TERMINAL\x1b[0m\r\n"
            f"\x1b[0;37m  Target Environment Instance: {self.instance_id}\x1b[0m\r\n"
            f"\x1b[0;37m  Logged in as: {self.user.username} (Restricted Access)\x1b[0m\r\n"
            "\x1b[1;36m========================================================\x1b[0m\r\n\r\n"
            "student@ftcr-lab:~$ "
        )
        await self.send(text_data=welcome_banner)

    async def disconnect(self, close_code):
        logger.info(f"Terminal WebSocket disconnected for instance {getattr(self, 'instance_id', 'unknown')}")

    async def receive(self, text_data=None, bytes_data=None):
        """
        Receives keystrokes from xterm.js and forwards to container PTY.
        """
        if text_data:
            # Echo input locally or pass to container PTY
            # In Phase 6, this binds to the raw Docker PTY socket
            if text_data == '\r':
                await self.send(text_data="\r\nstudent@ftcr-lab:~$ ")
            elif text_data == '\x7f':  # Backspace
                await self.send(text_data="\b \b")
            else:
                await self.send(text_data=text_data)

