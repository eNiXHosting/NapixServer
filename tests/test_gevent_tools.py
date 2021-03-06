#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import mock
import unittest

import time
import functools

try:
    import gevent
    from napixd.gevent_tools import Greenlet, Tracer, AddGeventTimeHeader
except ImportError:
    __test__ = False


class TestTimedGreenlet(unittest.TestCase):

    def setUp(self):
        self.greenlet = Greenlet()

    def test_no_times(self):
        self.assertEquals(self.greenlet.get_running_time(), 0)

    def test_running(self):
        self.greenlet.add_time()
        time.sleep(.1)
        self.greenlet.add_time()
        self.assertAlmostEquals(self.greenlet.get_running_time(), .1, places=2)

    def test_running_and_yielding(self):
        self.greenlet.add_time()
        time.sleep(.1)  # running
        self.greenlet.add_time()
        time.sleep(.1)  # not running
        self.greenlet.add_time()
        time.sleep(.1)  # running
        self.greenlet.add_time()
        self.assertAlmostEquals(self.greenlet.get_running_time(), .2, places=2)


class TestTracer(unittest.TestCase):

    def setUp(self):
        self.tracer = Tracer()
        self.tracer.set_trace()

    def tearDown(self):
        self.tracer.unset_trace()

    def test_yield(self):
        def x1():
            # first step
            gevent.sleep(.1)
            # second step
            g2.join()
            # third step

        def x2():
            # first step
            gevent.sleep(.1)
            # second step

        g1 = Greenlet.spawn(x1)
        g2 = Greenlet.spawn(x2)

        g1.join()

        self.assertEquals(len(list(g1.get_running_intervals())), 3)
        self.assertEquals(len(list(g2.get_running_intervals())), 2)


class TestGeventHeaders(unittest.TestCase):

    def _do_something(self, request):
        """This function should run in .1s with a total run of .2s"""
        gevent.sleep(0.1)  # Yield
        time.sleep(0.1)  # No Yield

    def setUp(self):
        self.plugin = AddGeventTimeHeader()
        self.callback = functools.partial(self.plugin, self._do_something, mock.Mock())

    def test_run_solo(self):
        resp = self.callback()
        self.assertAlmostEquals(float(resp.headers['x-total-time']), .2, places=1)
        self.assertAlmostEquals(float(resp.headers['x-running-time']), .1, places=1)

    def test_run(self):
        resps = [self.callback() for x in xrange(4)]
        for resp in resps:
            self.assertAlmostEquals(float(resp.headers['x-total-time']), .2, places=1)
            self.assertAlmostEquals(float(resp.headers['x-running-time']), .1, places=1)
