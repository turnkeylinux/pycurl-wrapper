# Copyright (c) 2010 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
# Copyright (c) 2013 Liraz Siri <liraz@turnkeylinux.org> - all rights reserved
# Copyright (c) 2025 TurnKey GNU/Linux <admin@turnkeylinux.org>

import pycurl

from io import BytesIO
from urllib.parse import urlencode

import json
import re

from typing import ClassVar


def gen_useragent() -> str:
    vi = pycurl.version_info()
    ua = f"pycurl_wrapper: libcurl/{vi[1]} {vi[5]} {vi[3]}"
    try:
        with open("/etc/apt/apt.conf.d/01turnkey") as fob:
            apt_ua = fob.read()
        m = re.search(r' \((.*?)\)', apt_ua)
        if m:
            ua += f" ({m.groups(1)})"
    except FileNotFoundError:
        pass
    return ua


class Client:
    class Response(str):
        def __new__(cls, code: int, type: str, data: bytes) -> str:
            # stop typing checker whinging
            _ = code
            _ = type
            return str.__new__(cls, data)

        def __init__(self, code: int, type: str, data: bytes) -> None:
            self.code = code
            self.type = type
            self.data = data
            str.__init__(self)

    def __init__(
            self,
            cainfo: str | None = None,
            verbose: bool = False,
            timeout: int | None = None,
    ) -> None:
        self.handle = pycurl.Curl()
        self.handle.setopt(pycurl.VERBOSE, verbose)
        self.handle.setopt(pycurl.USERAGENT, gen_useragent())

        if timeout:
            self.handle.setopt(pycurl.NOSIGNAL, True)
            self.handle.setopt(pycurl.TIMEOUT, timeout)

        if cainfo:
            self.handle.setopt(pycurl.CAINFO, cainfo)

    def _perform(self) -> str:
        response_buffer = BytesIO()

        self.handle.setopt(pycurl.WRITEFUNCTION, response_buffer.write)
        self.handle.perform()

        code = self.handle.getinfo(pycurl.RESPONSE_CODE)
        type = self.handle.getinfo(pycurl.CONTENT_TYPE)
        data = response_buffer.getvalue()

        response_buffer.close()
        return self.Response(code, type, data)

    def _setup(
            self,
            url: str,
            headers: dict[str, str] | None = None,
            attrs: dict[str, str] | None = None,
    ) -> None:
        if not headers:
            headers = {}
        if attrs:
            url = f"{url}?{urlencode(attrs)}"

        self.handle.setopt(pycurl.URL, str(url))

        headers_list = [f"{k}: {v}" for k, v in headers.items()]
        self.handle.setopt(pycurl.HTTPHEADER, headers_list)

    def get(
            self,
            url: str,
            attrs: dict[str, str] | None = None,
            headers: dict[str, str] | None = None,
    ) -> str:
        self._setup(url, headers, attrs)

        self.handle.setopt(pycurl.HTTPGET, True)
        return self._perform()

    def post(
            self,
            url: str,
            attrs: dict[str, str] | None = None,
            headers: dict[str, str] | None = None,
    ) -> str:
        if attrs is None:
            attrs = {}
        self._setup(url, headers)

        self.handle.setopt(pycurl.POST, True)
        self.handle.setopt(pycurl.POSTFIELDS, urlencode(attrs))

        return self._perform()

    def put(
            self,
            url: str,
            attrs: dict[str, str] | None = None,
            headers: dict[str, str] | None = None,
    ) -> str:
        if attrs is None:
            attrs = {}
        self._setup(url, headers)

        encoded_attrs = urlencode(attrs).encode()
        request_buffer = BytesIO(encoded_attrs)

        self.handle.setopt(pycurl.PUT, True)
        self.handle.setopt(pycurl.READFUNCTION, request_buffer.read)
        self.handle.setopt(pycurl.INFILESIZE, len(encoded_attrs))

        return self._perform()

    def delete(
            self,
            url: str,
            attrs: dict[str, str] | None = None,
            headers: dict[str, str] | None = None,
    ) -> str:
        self._setup(url, headers, attrs)
        self.handle.setopt(pycurl.CUSTOMREQUEST, 'DELETE')

        return self._perform()

# here for backwards compatibility
class Curl:
    def __init__(
            self,
            url: str,
            headers: dict[str, str] | None = None,
            cainfo: str | None = None,
            verbose: bool = False,
            timeout: int | None = None
    ) -> None:
        """simplified wrapper to pycurl (get, post, put, delete)

        Usage:
            print Curl(URL).get()

            c = Curl(URL)
            c.post({'foo': 'bar'})
            print c.response_data
            print c.response_code

        """

        self.response_code = None
        self.response_type = None
        self.response_data = None

        self.client = Client(cainfo, verbose, timeout)

        self.url = url
        self.headers = headers

    def _perform(
            self,
            methodname: str,
            attrs: dict[str, str] | None = None,
    ) -> str:
        method = getattr(self.client, methodname)
        response = method(self.url, attrs, self.headers)

        self.client.handle.close()

        self.response_code = response.code
        self.response_type = response.type
        self.response_data = response.data

        return response.data

    def get(self, attrs: dict[str, str] | None = None) -> str:
        return self._perform('get', attrs)

    def post(self, attrs: dict[str, str]) -> str:
        return self._perform('post', attrs)

    def put(self, attrs: dict[str, str]) -> str:
        return self._perform('put', attrs)

    def delete(self, attrs: dict[str, str] | None = None) -> str:
        return self._perform('delete', attrs)

class API:
    class APIError(Exception):
        def __init__(self, code: int, name: str, description: str) -> None:
            super().__init__(code, name, description)
            self.code = code
            self.name = name
            self.description = description

        def __str__(self) -> str:
            return f"{self.code} - {self.name} ({self.description})"

    ALL_OK = 200
    CREATED = 201
    DELETED = 204
    ERROR = 500

    API_HEADERS: ClassVar = {"Accept": "application/json"}

    def __init__(
            self,
            cainfo: str | None = None,
            verbose: bool = False,
            timeout: int | None = None,
    ) -> None:
        self.client = Client(cainfo, verbose, timeout)

    def request(
            self,
            method: str,
            url: str,
            attrs: dict[str, str] | None = None,
            headers: dict[str, str] | None = None,
    ) -> str:
        if headers is None:
            headers = {}
        _headers = self.API_HEADERS.copy()
        _headers.update(headers)

        # workaround: http://redmine.lighttpd.net/issues/1017
        if method == "PUT":
            _headers['Expect'] = ''

        func = getattr(self.client, method.lower())
        try:
            response = func(url, attrs, _headers)
        except Exception as e:
            raise self.APIError(
                    self.ERROR,
                    "exception",
                    e.__class__.__name__ + repr(e.args)
            ) from e

        if response.code not in (self.ALL_OK, self.CREATED, self.DELETED):
            name, description = str(response.data).split(":", 1)
            raise self.APIError(response.code, name, description)

        return json.loads(response.data)
