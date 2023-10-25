# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

import json
from typing import Optional, Any

from requests import Response
from requests_cache import CachedSession

from aiohttp import ClientSession
from aiohttp_client_cache.session import CachedSession as AsyncCachedSession
from aiohttp_client_cache.backends import FileBackend
from aiohttp_client_cache.cache_control import CacheActions

from otterdog.providers.github.exception import BadCredentialsException, GitHubException
from otterdog.utils import print_debug, print_trace, is_debug_enabled, is_trace_enabled

from .auth import AuthStrategy

_AIOHTTP_CACHE_DIR = ".cache/async_http"
_REQUESTS_CACHE_DIR = ".cache/http"


class Requester:
    def __init__(self, auth_strategy: AuthStrategy, base_url: str, api_version: str):
        self._base_url = base_url
        self._auth = auth_strategy.get_auth()

        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": api_version,
            "X-Github-Next-Global-ID": "1",
        }

        # enable logging for requests_cache
        # import logging
        #
        #
        # logging.basicConfig(level='DEBUG')

        self._session: CachedSession = CachedSession(
            _REQUESTS_CACHE_DIR,
            backend="filesystem",
            use_cache_dir=False,
            cache_control=True,
            allowable_methods=["GET"],
        )
        self._session.auth = self._auth

    def close(self) -> None:
        self._session.close()

    def _build_url(self, url_path: str) -> str:
        return f"{self._base_url}{url_path}"

    def request_paged_json(
        self,
        method: str,
        url_path: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, str]] = None,
    ) -> list[dict[str, Any]]:
        result = []
        current_page = 1
        while current_page > 0:
            query_params = {"per_page": "100", "page": current_page}
            if params is not None:
                query_params.update(params)

            response: list[dict[str, Any]] = self.request_json(method, url_path, data, query_params)

            if len(response) == 0:
                current_page = -1
            else:
                for item in response:
                    result.append(item)

                current_page += 1

        return result

    async def async_request_paged_json(
        self,
        method: str,
        url_path: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, str]] = None,
    ) -> list[dict[str, Any]]:
        result = []
        current_page = 1
        while current_page > 0:
            query_params = {"per_page": "100", "page": current_page}
            if params is not None:
                query_params.update(params)

            response: list[dict[str, Any]] = await self.async_request_json(method, url_path, data, query_params)

            if len(response) == 0:
                current_page = -1
            else:
                for item in response:
                    result.append(item)

                current_page += 1

        return result

    def request_json(
        self,
        method: str,
        url_path: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        input_data = None
        if data is not None:
            input_data = json.dumps(data)

        response = self.request_raw(method, url_path, input_data, params)
        self._check_response(response.url, response.status_code, response.text)
        return response.json()

    async def async_request_json(
        self,
        method: str,
        url_path: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        input_data = None
        if data is not None:
            input_data = json.dumps(data)

        status, body = await self.async_request_raw(method, url_path, input_data, params)
        self._check_response(url_path, status, body)
        return json.loads(body)

    def request_raw(
        self,
        method: str,
        url_path: str,
        data: Optional[str] = None,
        params: Optional[dict[str, str]] = None,
        stream: bool = False,
        force_refresh: bool = False,
    ) -> Response:
        print_trace(f"'{method}' url = {url_path}, data = {data}, headers = {self._headers}")

        response = self._session.request(
            method,
            url=self._build_url(url_path),
            headers=self._headers,
            refresh=True,
            force_refresh=force_refresh,
            params=params,
            data=data,
            stream=stream,
        )

        if is_debug_enabled():
            print_debug(f"'{method}' {url_path}: rate-limit-used = {response.headers.get('x-ratelimit-used', None)}")

        if is_trace_enabled():
            print_trace(f"'{method}' result = ({response.status_code}, {response.text})")

        return response

    async def async_request_raw(
        self,
        method: str,
        url_path: str,
        data: Optional[str] = None,
        params: Optional[dict[str, str]] = None,
    ) -> tuple[int, str]:
        print_trace(f"async '{method}' url = {url_path}, data = {data}, headers = {self._headers}")

        headers = self._headers.copy()
        self._auth.update_headers_with_authorization(headers)

        async with AsyncCachedSession(cache=FileBackend(cache_name=_AIOHTTP_CACHE_DIR, use_temp=False)) as session:
            url = self._build_url(url_path)
            key = session.cache.create_key(method, url, params=params)
            cached_response = await session.cache.get_response(key)

            if cached_response is not None and method == "GET":
                # if the url is present in the cache, try to refresh it from the server
                refresh_headers = headers.copy()

                if "ETag" in cached_response.headers:
                    refresh_headers["If-None-Match"] = cached_response.headers["ETag"]

                if "Last-Modified" in cached_response.headers:
                    refresh_headers["If-Modified-Since"] = cached_response.headers["Last-Modified"]

                # the actual refresh must happen without a cache
                # we initialize a new client session as the current version of the cache has a bug
                # where responses are modify the cache even if it is disabled.
                async with ClientSession() as nocache_session:
                    response = await nocache_session.request(
                        method,
                        url=url,
                        headers=refresh_headers,
                        params=params,
                        data=data,
                    )

                    if response.status == 304:
                        # we received a not-modified response, re-request the item from the cache
                        print_trace(
                            f"async '{method}' result = ({response.status}, {await response.text()}), "
                            f"not-modified, requesting from cache"
                        )
                        pass
                    elif response.status == 200:
                        # update the cache with the received response and return it
                        actions = CacheActions.from_headers(key, response.headers)
                        await session.cache.save_response(response, key, actions.expires)

                        if is_trace_enabled():
                            print_trace(
                                f"async '{method}' result = ({response.status}, {await response.text()}), "
                                f"refreshing cache"
                            )

                        return response.status, await response.text()
                    else:
                        # in all other cases, remove the item from the cache
                        await session.cache.delete(key)

                        if is_trace_enabled():
                            print_trace(
                                f"async '{method}' result = ({response.status}, {await response.text()}), "
                                f"deleting from cache"
                            )

                        return response.status, await response.text()

            response = await session.request(method, url=url, headers=headers, params=params, data=data)
            if is_debug_enabled():
                if not response.from_cache:  # type: ignore
                    print_debug(
                        f"'{method}' {url_path}: rate-limit-used = {response.headers.get('x-ratelimit-used', None)}"
                    )

            if is_trace_enabled():
                print_trace(f"async '{method}' result = ({response.status}, {await response.text()})")

            text = await response.text()
            response.close()
            return response.status, text

    def _check_response(self, url_path: str, status_code: int, body: str) -> None:
        if status_code >= 400:
            self._create_exception(self._build_url(url_path), status_code, body)

    @staticmethod
    def _create_exception(url: str, status_code: int, body: str):
        if status_code == 401:
            raise BadCredentialsException(url, status_code, body)
        else:
            raise GitHubException(url, status_code, body)
