"""API 层对核心服务/状态模块的转发封装。

所有对外工具都通过这些薄封装调用 services，而不是在 import 时绑定具体函数，
这样运行时 monkeypatch ``services.client._post`` 等仍能生效，同时 API 层保持简洁。
"""

from ..services import client as _client
from ..services import metadata as _metadata
from ..services import system as _system


def _url(*args, **kwargs):
    return _client._url(*args, **kwargs)


async def _login(*args, **kwargs):
    return await _client._login(*args, **kwargs)


async def _post(*args, **kwargs):
    return await _client._post(*args, **kwargs)


async def _post_raw(*args, **kwargs):
    return await _client._post_raw(*args, **kwargs)


async def _post_query(*args, **kwargs):
    return await _client._post_query(*args, **kwargs)


def _query_payload(*args, **kwargs):
    return _client._query_payload(*args, **kwargs)


async def _post_system(*args, **kwargs):
    return await _system._post_system(*args, **kwargs)


async def _get_metadata_validator(*args, **kwargs):
    return await _metadata._get_metadata_validator(*args, **kwargs)


async def _query_metadata(*args, **kwargs):
    return await _metadata._query_metadata(*args, **kwargs)


