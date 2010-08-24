# Copyright (c) 2010 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
import pycurl

from cStringIO import StringIO
from urllib import urlencode

class Curl:
    def __init__(self, url, headers={}, cainfo=None, verbose=False):
        """simplified wrapper to pycurl (get, post, put)
        
        Usage:
            print Curl(URL).get()

            c = Curl(URL)
            c.post({'foo': 'bar'})
            print c.response_data
            print c.response_code

        """
        self.url = url

        self.response_code = None
        self.response_type = None
        self.response_data = None

        self.c = pycurl.Curl()
        self.c.setopt(pycurl.URL, self.url)
        self.c.setopt(pycurl.VERBOSE, verbose)

        headers = map(lambda val: "%s: %s" % (val, headers[val]), headers)
        self.c.setopt(pycurl.HTTPHEADER, headers)

        if cainfo:
            self.c.setopt(pycurl.CAINFO, cainfo)

    def _perform(self):
        response_buffer = StringIO()

        self.c.setopt(pycurl.WRITEFUNCTION, response_buffer.write)
        self.c.perform()

        self.response_code = self.c.getinfo(pycurl.RESPONSE_CODE)
        self.response_type = self.c.getinfo(pycurl.CONTENT_TYPE)
        self.c.close()

        self.response_data = response_buffer.getvalue()
        response_buffer.close()

        return self.response_data

    def get(self, attrs={}):
        if attrs:
            self.c.setopt(pycurl.URL, "%s?%s" % (self.url, urlencode(attrs)))

        return self._perform()

    def post(self, attrs):
        self.c.setopt(pycurl.POST, True)
        self.c.setopt(pycurl.POSTFIELDS, urlencode(attrs))

        return self._perform()

    def put(self, attrs):
        encoded_attrs = urlencode(attrs)
        request_buffer = StringIO(encoded_attrs)

        self.c.setopt(pycurl.PUT, True)
        self.c.setopt(pycurl.READFUNCTION, request_buffer.read)
        self.c.setopt(pycurl.INFILESIZE, len(encoded_attrs))

        return self._perform()

    #def delete(self, attrs={}):
    #    if attrs:
    #        encoded_attrs = urlencode(attrs)
    #        self.c.setopt(pycurl.DELETEFIELDS, encoded_attrs)
    #    self.c.setopt(pycurl.CUSTOMREQUEST, 'DELETE')
    #    return self._perform()


