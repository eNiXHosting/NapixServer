#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Various WSGI compatible middlewares.
"""

import urlparse
import logging
import datetime
from napixd.chrono import Chrono


class PathInfoMiddleware(object):
    """
    Use the `REQUEST_URI` to generate `PATH_INFO` to avoid problems with
    URL encoding.
    """

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        environ['PATH_INFO'] = urlparse.urlparse(environ['REQUEST_URI']).path
        return self.application(environ, start_response)


class CORSMiddleware(object):
    """
    Reply to OPTIONS requests emitted by browsers
    to check for Cross Origin Requests
    """

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        if environ['REQUEST_METHOD'] == 'OPTIONS':
            start_response('200 OK', [
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods',
                 'GET, POST, PUT, CREATE, DELETE, OPTIONS'),
                ('Access-Control-Allow-Headers',
                 'Authorization, Content-Type'),
            ])
            return []
        return self.application(environ, start_response)


class LoggedRequest(object):
    """
    Objects returned by :class:`LoggerMiddleware`.

    Keeps the info to log.
    """
    logger = logging.getLogger('Napix.requests')

    def __init__(self, start_response, application, environ):
        self._start_response = start_response
        self.application = application
        self.environ = environ

    def start_response(self, status, headers):
        self.status = status
        self._start_response(status, headers)
        del self._start_response

    @property
    def request_line(self):
        request_line = self.environ['PATH_INFO']
        if self.environ.get('QUERY_STRING'):
            request_line += '?' + self.environ['QUERY_STRING']
        return request_line

    def __iter__(self):
        size = 0
        with Chrono() as chrono:
            for x in self.application(self.environ, self.start_response):
                size += len(x)
                yield x

        self.logger.info('%s - - [%s] "%s %s" %s %s %s',
                         self.environ.get('REMOTE_ADDR', '-'),
                         datetime.datetime.now().replace(microsecond=0),
                         self.environ['REQUEST_METHOD'],
                         self.request_line,
                         self.status.split(' ')[0],
                         size,
                         chrono.total
                         )


def LoggerMiddleware(application):
    """
    Middleware that logs requests, in the combined log format
    with the body's size and the time.
    """
    def inner_logger(environ, start_response):
        return LoggedRequest(start_response, application, environ)
    return inner_logger
