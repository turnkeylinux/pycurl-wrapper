# Copyright (c) 2013 Liraz Siri <liraz@turnkeylinux.org> - all rights reserved
# Copyright (c) 2010 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
import pycurl

from io import BytesIO, StringIO
from urllib.parse import urlencode

import simplejson as json
import re

def _useragent():
    vi = pycurl.version_info()
    ua = "pycurl_wrapper: libcurl/%s %s %s" % (vi[1], vi[5], vi[3])
    try:
        with open("/etc/apt/apt.conf.d/01turnkey", 'r') as fob:
            apt_ua = fob.read()
            m = re.search(r' \((.*?)\)', apt_ua)
            if m:
                ua += " (%s)" % m.groups(1)
    except:
        pass

    return ua

USERAGENT = _useragent()
    
class Client:
    class Response(str):
        def __new__(cls, code, type, data):
            return str.__new__(cls, data)

        def __init__(self, code, type, data):
            self.code = code
            self.type = type
            self.data = data

            str.__init__(self)

    def __init__(self, cainfo=None, verbose=False, timeout=None):
        self.handle = pycurl.Curl()
        self.handle.setopt(pycurl.VERBOSE, verbose)
        self.handle.setopt(pycurl.USERAGENT, USERAGENT)

        if timeout:
            self.handle.setopt(pycurl.NOSIGNAL, True)
            self.handle.setopt(pycurl.TIMEOUT, timeout)

        if cainfo:
            self.handle.setopt(pycurl.CAINFO, cainfo)

    def _perform(self):
        response_buffer = BytesIO()

        self.handle.setopt(pycurl.WRITEFUNCTION, response_buffer.write)
        self.handle.perform()

        code = self.handle.getinfo(pycurl.RESPONSE_CODE)
        type = self.handle.getinfo(pycurl.CONTENT_TYPE)
        data = response_buffer.getvalue()

        response_buffer.close()

        return self.Response(code, type, data)

    def _setup(self, url, headers={}, attrs={}):
        if attrs:
            url = "%s?%s" % (url, urlencode(attrs))

        self.handle.setopt(pycurl.URL, str(url))

        headers = ["%s: %s" % (val, headers[val]) for val in headers]
        self.handle.setopt(pycurl.HTTPHEADER, headers)

    def get(self, url, attrs={}, headers={}):
        self._setup(url, headers, attrs)

        self.handle.setopt(pycurl.HTTPGET, True)
        return self._perform()

    def post(self, url, attrs, headers={}):
        self._setup(url, headers)

        self.handle.setopt(pycurl.POST, True)
        self.handle.setopt(pycurl.POSTFIELDS, urlencode(attrs))

        return self._perform()

    def put(self, url, attrs, headers={}):
        self._setup(url, headers)

        encoded_attrs = urlencode(attrs)
        request_buffer = StringIO(encoded_attrs)

        self.handle.setopt(pycurl.PUT, True)
        self.handle.setopt(pycurl.READFUNCTION, request_buffer.read)
        self.handle.setopt(pycurl.INFILESIZE, len(encoded_attrs))

        return self._perform()

    def delete(self, url, attrs={}, headers={}):
        self._setup(url, headers, attrs)
        self.handle.setopt(pycurl.CUSTOMREQUEST, 'DELETE')

        return self._perform()

# here for backwards compatibility 
class Curl:
    def __init__(self, url, headers={}, cainfo=None, verbose=False, timeout=None):
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
            
    def _perform(self, methodname, attrs={}):
        method = getattr(self.client, methodname)
        response = method(self.url, attrs, self.headers)

        self.client.handle.close()

        self.response_code = response.code
        self.response_type = response.type
        self.response_data = response.data

        return response.data

    def get(self, attrs={}):
        return self._perform('get', attrs)

    def post(self, attrs):
        return self._perform('post', attrs)

    def put(self, attrs):
        return self._perform('put', attrs)

    def delete(self, attrs={}):
        return self._perform('delete', attrs)

class API:
    class Error(Exception):
        def __init__(self, code, name, description):
            Exception.__init__(self, code, name, description)
            self.code = code
            self.name = name
            self.description = description

        def __str__(self):
            return "%s - %s (%s)" % (self.code, self.name, self.description)

    ALL_OK = 200
    CREATED = 201
    DELETED = 204
    ERROR = 500

    API_HEADERS = {'Accept': 'application/json'}

    def __init__(self, cainfo=None, verbose=False, timeout=None):
        self.client = Client(cainfo, verbose, timeout)

    def request(self, method, url, attrs={}, headers={}):
        _headers = self.API_HEADERS.copy()
        _headers.update(headers)

        # workaround: http://redmine.lighttpd.net/issues/1017
        if method == "PUT":
            _headers['Expect'] = ''

        func = getattr(self.client, method.lower())
        try:
            response = func(url, attrs, _headers)
        except Exception as e:
            raise self.Error(self.ERROR, "exception", e.__class__.__name__ + repr(e.args))

        if not response.code in (self.ALL_OK, self.CREATED, self.DELETED):
            name, description = response.data.decode().split(":", 1)
            raise self.Error(response.code, name, description)

        return json.loads(response.data)
