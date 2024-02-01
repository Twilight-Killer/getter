# getter < https://t.me/kastaid >
# Copyright (C) 2022-present kastaid
#
# This file is a part of < https://github.com/kastaid/getter/ >
# Please read the GNU Affero General Public License in
# < https://github.com/kastaid/getter/blob/main/LICENSE/ >.

import re
import sys
import typing
from asyncio import sleep
from base64 import b64decode
from asyncache import cached
from cachetools import TTLCache
from getter import __license__, __copyright__
from getter.logger import LOG
from getter.tools import Fetch

_c, _u, _g = (
    b64decode("a2FzdGFpZA==").decode("utf-8"),
    b64decode("a2FzdGF1cA==").decode("utf-8"),
    b64decode("a2FzdGFvdA==").decode("utf-8"),
)


def do_not_remove_credit() -> None:
    if _c not in __copyright__:
        LOG.warning(__copyright__)
        LOG.warning("PLEASE RESPECT US, DO NOT REMOVE THE ORIGINAL CREDITS AND LICENSE !!")
        LOG.warning(__license__)
        sys.exit(1)


@cached(TTLCache(maxsize=1024, ttl=(120 * 30)))  # 1 hours
async def get_blacklisted(
    url: str,
    is_json: bool = False,
    attempts: int = 3,
    fallbacks: typing.Optional[typing.Tuple[typing.Union[int, str]]] = None,
) -> typing.Set[typing.Union[int, str]]:
    count = 0
    is_content = not is_json
    while count < attempts:
        res = await Fetch(
            url,
            re_json=is_json,
            re_content=is_content,
        )
        count += 1
        if not res:
            if count != attempts:
                await sleep(1)
                continue
            ids = fallbacks or []
            break
        if is_content:
            reg = r"[^\s#,\[\]\{\}]+"
            data = re.findall(reg, res.decode("utf-8"))
            ids = [int(x) for x in data if x.isdecimal() or (x.startswith("-") and x[1:].isdecimal())]
        else:
            ids = list(res)
        break
    return set(ids)
