# getter < https://t.me/kastaid >
# Copyright (C) 2022-present kastaid
#
# This file is a part of < https://github.com/kastaid/getter/ >
# Please read the GNU Affero General Public License in
# < https://github.com/kastaid/getter/blob/main/LICENSE/ >.

import importlib.util
import os
import sys
import typing
from asyncio import sleep, Future
from inspect import getmembers
from platform import version, machine
from random import choice
from time import time
from telethon.client.telegramclient import TelegramClient
from telethon.errors import (
    ApiIdInvalidError,
    AuthKeyDuplicatedError,
    PhoneNumberInvalidError,
    AccessTokenExpiredError,
    AccessTokenInvalidError,
    InvalidBufferError,
)
from telethon.sessions.abstract import Session
from telethon.sessions.string import CURRENT_VERSION, StringSession
from telethon.tl import functions as fun, types as typ
from .. import (
    Root,
    StartTime,
    __version__,
    LOOP,
)
from ..config import Var, DEVS
from ..logger import LOG, TelethonLogger
from .db import sgvar
from .functions import display_name
from .property import do_not_remove_credit, get_blacklisted
from .utils import time_formatter


class ReverseList(list):
    def __iter__(self):
        return reversed(self)


class KastaClient(TelegramClient):
    def __init__(
        self,
        session: typing.Union[str, Session],
        api_id: typing.Optional[int] = None,
        api_hash: typing.Optional[str] = None,
        bot_token: typing.Optional[str] = None,
        *args,
        **kwargs,
    ):
        self._dialogs = []
        self._plugins = {}
        kwargs["api_id"] = api_id
        kwargs["api_hash"] = api_hash
        kwargs["request_retries"] = 3
        kwargs["connection_retries"] = 3
        kwargs["auto_reconnect"] = True
        kwargs["device_model"] = "Getter"
        kwargs["system_version"] = " ".join((version(), machine()))
        kwargs["app_version"] = __version__
        kwargs["loop"] = LOOP
        kwargs["base_logger"] = TelethonLogger
        kwargs["entity_cache_limit"] = 1000
        super().__init__(session, **kwargs)
        self._event_builders = ReverseList()
        self.run_in_loop(self.start_client(bot_token=bot_token))
        self.dc_id = self.session.dc_id

    def __repr__(self):
        return "<Kasta.Client:\n self: {}\n id: {}\n bot: {}\n>".format(
            self.full_name,
            self.uid,
            self._bot,
        )

    @property
    def __dict__(self) -> typing.Optional[dict]:
        if self.me:
            return self.me.to_dict()

    async def start_client(self, **kwargs) -> None:
        self.log.info("Trying to login...")
        do_not_remove_credit()
        await sleep(choice((4, 6, 8)))
        try:
            await self.start(**kwargs)
            self._bot = await self.is_bot()
            if not self._bot:
                cfg = await self(fun.help.GetConfigRequest())
                for opt in cfg.dc_options:
                    if opt.ip_address == self.session.server_address:
                        if self.session.dc_id != opt.id:
                            self.log.warning(f"Fixed DC ID in session from {self.session.dc_id} to {opt.id}")
                        self.session.set_dc(opt.id, opt.ip_address, opt.port)
                        self.session.save()
                        break
            await sleep(5)
            self.me = await self.get_me()
            if self.me.bot:
                me = f"@{self.me.username}"
            else:
                self.me.phone = None
                me = self.full_name
            await sleep(5)
            if self.uid not in DEVS:
                KASTA_BLACKLIST = await get_blacklisted(
                    url="https://raw.githubusercontent.com/kastaid/resources/main/kastablacklist.py",
                    attempts=6,
                    fallbacks=None,
                )
                if self.uid in KASTA_BLACKLIST:
                    self.log.error(
                        "({} - {}) YOU ARE BLACKLISTED !!".format(
                            me,
                            self.uid,
                        )
                    )
                    sys.exit(1)
            self.log.success(
                "Logged in as {} [{}]".format(
                    me,
                    self.uid,
                )
            )
        except (ValueError, ApiIdInvalidError):
            self.log.critical("API_ID and API_HASH combination does not match, please re-check! Quitting...")
            sys.exit(1)
        except (AuthKeyDuplicatedError, PhoneNumberInvalidError, EOFError):
            self.log.critical("STRING_SESSION expired, please create new! Quitting...")
            sys.exit(1)
        except (AccessTokenExpiredError, AccessTokenInvalidError):
            self.log.critical(
                "Bot Token expired or invalid. Create new from @Botfather and update BOT_TOKEN in Config Vars!"
            )
            sys.exit(1)
        except Exception as err:
            self.log.exception(f"[KastaClient] - {err}")
            sys.exit(1)

    def run_in_loop(self, func: typing.Coroutine[typing.Any, typing.Any, None]) -> typing.Any:
        return self.loop.run_until_complete(func)

    def run(self) -> typing.NoReturn:
        try:
            self.run_until_disconnected()
        except InvalidBufferError as err:
            self.log.exception(err)
            self.log.error("Client was stopped, restarting...")
            try:
                import psutil

                proc = psutil.Process(os.getpid())
                for _ in proc.open_files() + proc.connections():
                    os.close(_.fd)
            except BaseException:
                pass
            os.execl(sys.executable, sys.executable, "-m", "getter")

    def add_handler(
        self,
        func: Future,
        *args,
        **kwargs,
    ) -> None:
        if func in [_[0] for _ in self.list_event_handlers()]:
            return
        self.add_event_handler(func, *args, **kwargs)

    def reboot(self, message: typ.Message) -> typing.NoReturn:
        try:
            chat_id = message.chat_id or message.from_id
            sgvar("_reboot", f"{chat_id}|{message.id}")
        except BaseException:
            pass
        try:
            import psutil

            proc = psutil.Process(os.getpid())
            for _ in proc.open_files() + proc.connections():
                os.close(_.fd)
        except BaseException:
            pass
        os.execl(sys.executable, sys.executable, "-m", "getter")

    def load_plugin(
        self,
        plugin: str,
    ) -> bool:
        try:
            path = Root / ("getter/plugins/custom/" + plugin)
            plug = path.stem
            name = f"getter.plugins.custom.{plug}"
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self._plugins[plug] = mod
            self.log.success(f"Successfully loaded custom plugin {plug}!")
            return True
        except Exception as err:
            self.log.warning(f"Failed to load custom plugin {plug}!")
            self.log.exception(err)
            return False

    def unload_plugin(
        self,
        plugin: str,
    ) -> None:
        name = self._plugins[plugin].__name__
        for x in reversed(range(len(self._event_builders))):
            ev, cb = self._event_builders[x]
            if cb.__module__ == name:
                del self._event_builders[x]
        del self._plugins[plugin]
        self.log.success(f"Removed custom plugin {plugin}!")

    @property
    def all_plugins(self) -> typing.List[typing.Dict[str, str]]:
        return [
            {
                "path": ".".join(str(_.resolve()).replace(".py", "").split("/")[-2:]),
                "name": _.stem,
            }
            for _ in (Root / "getter/plugins/").rglob("*.py")
            if not str(_).endswith(("__.py", "_draft.py"))
        ]

    @property
    def full_name(self) -> str:
        return display_name(self.me)

    @property
    def uid(self) -> int:
        return self.me.id

    @property
    def uptime(self) -> str:
        return time_formatter((time() - StartTime) * 1000)

    def to_dict(self) -> dict:
        return dict(getmembers(self))


_ssn = Var.STRING_SESSION
if _ssn:
    if _ssn.startswith(CURRENT_VERSION) and len(_ssn) != 353:
        LOG.critical("STRING_SESSION wrong. Copy paste correctly! Quitting...")
        sys.exit(1)
    session = StringSession(_ssn)
else:
    LOG.critical("STRING_SESSION empty. Please filling! Quitting...")
    sys.exit(1)

getter_app = KastaClient(
    session=session,
    api_id=Var.API_ID,
    api_hash=Var.API_HASH,
)
