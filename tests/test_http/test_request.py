#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import mock

from cStringIO import StringIO

from napixd.http.request import Request, InputStream
from napixd.http.response import HTTPError


class TestRequest(unittest.TestCase):
    def _r(self, **values):
        environ = {
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '',
        }
        environ.update(values)
        return Request(environ)
    def test_path(self):
        r = self._r()
        self.assertEqual(r.path, '/')
        self.assertEqual(r.method, 'GET')

    def test_content_type(self):
        r = self._r(CONTENT_TYPE='text/plain')
        self.assertEqual(r.content_type, 'text/plain')

    def test_content_length_negative(self):
        r = self._r(CONTENT_LENGTH='-1234')
        self.assertEqual(r.content_length, 0)

    def test_content_length(self):
        r = self._r(CONTENT_LENGTH='1234')
        self.assertEqual(r.content_length, 1234)

    def test_no_content_length(self):
        r = self._r()
        self.assertEqual(r.content_length, 0)

    def test_bad_content_length(self):
        r = self._r(CONTENT_LENGTH='pim')
        self.assertEqual(r.content_length, 0)

    def test_query_string(self):
        r = self._r(QUERY_STRING='abc&def=ghi')
        self.assertEqual(r.query_string, 'abc&def=ghi')

    def test_query(self):
        r = self._r(QUERY_STRING='abc&def=ghi')
        self.assertEqual(r.query, {'abc': None, 'def': 'ghi'})

    def test_headers(self):
        r = self._r(HTTP_AUTHORIZATION='login:pass', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.headers, {
            'authorization': 'login:pass',
            'x-requested-with': 'XMLHttpRequest'
        })

    def test_body(self):
        input = mock.Mock()
        r = self._r(CONTENT_LENGTH=14, **{
            'wsgi.input': input
        })
        with mock.patch('napixd.http.request.InputStream') as IS:
            body = r._body()

        self.assertEqual(body, IS.return_value)
        IS.assert_called_once_with(input, 14)

    def test_body_cl_0(self):
        r = self._r(**{
            'wsgi.input': input
        })

        self.assertEqual(r._body().read(), '')

    def test_body_too_big(self):
        r = self._r(CONTENT_LENGTH=1e9, **{
            'wsgi.input': input
        })

        self.assertRaises(HTTPError, r._body)

    def test_request_json(self):
        data = '{ "mpm": "prefork", "x": 1 }'
        r = self._r(
            CONTENT_TYPE='application/json',
            CONTENT_LENGTH=len(data),
            **{
                'wsgi.input': StringIO(data)
            })

        self.assertEqual(r.json, {'mpm': 'prefork', 'x': 1})

    def test_request_bad_json(self):
        data = '{ "mpm": prefork", "x": 1 }'
        r = self._r(
            CONTENT_TYPE='application/json',
            CONTENT_LENGTH=len(data),
            **{
                'wsgi.input': StringIO(data)
            })

        self.assertRaises(HTTPError, lambda: r.json)

    def test_request_no_json(self):
        r = self._r(**{
                'wsgi.input': StringIO('')
            })

        self.assertEqual(r.json, None)


class TestInputStream(unittest.TestCase):
    def setUp(self):
        self.input = StringIO('01234567890')

    def test_read_all(self):
        ist = InputStream(self.input, 11)
        self.assertEqual(ist.read(), '01234567890')

    def test_read_eof(self):
        ist = InputStream(self.input, 11)
        self.assertEqual(ist.read(), '01234567890')
        self.assertEqual(ist.read(), '')

    def test_read_size_eof(self):
        ist = InputStream(self.input, 11)
        self.assertEqual(ist.read(11), '01234567890')
        self.assertEqual(ist.read(11), '')

    def test_read_all_after_eof(self):
        ist = InputStream(self.input, 10)
        self.assertEqual(ist.read(), '0123456789')
        self.assertEqual(ist.read(), '')

    def test_read_size_after_eof(self):
        ist = InputStream(self.input, 10)
        self.assertEqual(ist.read(11), '0123456789')
        self.assertEqual(ist.read(11), '')

    def test_read_all_before(self):
        ist = InputStream(self.input, 10)
        self.assertEqual(ist.read(), '0123456789')

    def test_read_size_after(self):
        ist = InputStream(self.input, 10)
        self.assertEqual(ist.read(5), '01234')
        self.assertEqual(ist.read(4), '5678')
        self.assertEqual(ist.read(3), '9')

    def test_read_size_all(self):
        ist = InputStream(self.input, 11)
        self.assertEqual(ist.read(5), '01234')
        self.assertEqual(ist.read(4), '5678')
        self.assertEqual(ist.read(3), '90')
