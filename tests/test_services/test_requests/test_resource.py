#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import mock

from napixd.exceptions import ValidationError, NotFound
from napixd.http.response import HTTPError
from napixd.utils.lock import Lock

from napixd.services.urls import URL
from napixd.services.wrapper import ResourceWrapper
from napixd.services.collection import CollectionService, ActionService
from napixd.services.contexts import CollectionContext

from napixd.services.requests import (
    ServiceActionRequest,
    ServiceResourceRequest
)


def validate_id(value):
    if value.isdigit():
        return int(value)
    raise ValidationError()


def serialize(value):
    value['_s'] = True
    return value


class TestServiceResourceRequest(unittest.TestCase):
    def setUp(self):
        self.manager = manager = mock.Mock()
        self.manager.validate_id.side_effect = validate_id
        self.manager.serialize.side_effect = serialize
        self.url = url = URL(['abc', None])
        self.cs = mock.Mock(
            spec=CollectionService,
            lock=None,
            collection=manager,
            resource_url=url)
        self.context = mock.Mock(
            spec=CollectionContext,
            service=self.cs,
            method='GET',
            parameters={},
            data=mock.Mock(name='data'),
        )
        self.context.get_manager_instance.return_value = manager

    def srr(self):
        return ServiceResourceRequest(self.context, ['123'])

    def test_handle_get(self):
        self.manager.get_resource.return_value = {'mpm': 'prefork'}
        r = self.srr().handle()
        self.assertEqual(r, {'mpm': 'prefork', '_s': True})

    def test_handle_get_None(self):
        self.manager.get_resource.return_value = None
        self.assertRaises(ValueError, self.srr().handle)

    def test_handle_get_404(self):
        self.manager.get_resource.side_effect = NotFound()
        try:
            self.srr().handle()
        except HTTPError as err:
            self.assertEqual(err.status, 404)
        else:
            self.fail()

    def test_handle_get_not_dict(self):
        self.manager.get_resource.return_value = mock.MagicMock()
        self.assertRaises(ValueError, self.srr().handle)

    def test_handle_put(self):
        self.context.method = 'PUT'
        self.manager.modify_resource.return_value = None

        r = self.srr().handle()
        self.assertEqual(r.status, 204)

        o = self.manager.get_resource.return_value
        v = self.manager.validate
        v.assert_called_once_with(self.context.data, o)
        self.manager.modify_resource.assert_called_once_with(
            ResourceWrapper(self.manager, 123, o),
            v.return_value
        )

    def test_handle_put_validation_error(self):
        self.context.method = 'PUT'
        self.manager.validate.side_effect = ValidationError({
            'mpm': 'This is prefork or worker'
        })

        try:
            self.srr().handle()
        except HTTPError as err:
            self.assertEqual(err.status, 400)
            self.assertEqual(err.body, {
                'mpm': 'This is prefork or worker'
            })
        else:
            self.fail()

    def test_handle_put_new_id(self):
        self.context.method = 'PUT'
        self.manager.modify_resource.return_value = 312

        r = self.srr().handle()
        self.assertEqual(r.status, 205)
        self.assertEqual(r.headers['Location'], '/abc/312')

    def test_handle_head(self):
        self.context.method = 'HEAD'
        self.manager.get_resource.return_value = {'mpm': 'prefork'}
        r = self.srr().handle()
        self.assertEqual(r, None)

    def test_handle_get_format_none(self):
        self.context.parameters['format'] = 'pouet'
        o = self.manager.get_resource.return_value = {'mpm': 'prefork'}
        formatter = self.manager.get_formatter.return_value
        formatter.return_value = None

        r = self.srr().handle()

        formatter.assert_called_once_with(ResourceWrapper(self.manager, 123, o), r)

    def test_handle_get_format_not_exist(self):
        self.context.parameters['format'] = 'pouet'
        self.manager.get_all_formats.return_value = {'this': '', 'that': ''}
        self.manager.get_formatter.side_effect = KeyError()

        r = self.srr().handle()
        self.assertEqual(r.status, 406)

    def test_handle_get_format_other_headers(self):
        self.context.parameters['format'] = 'pouet'
        o = self.manager.get_resource.return_value = {'mpm': 'prefork'}

        def formatter(res, resp):
            resp.set_header('content-type', 'text/plain')
            self.assertEqual(res, ResourceWrapper(self.manager, 123, o))
            return 'pouetpouetpouet'
        self.manager.get_formatter.return_value.side_effect = formatter

        r = self.srr().handle()

        self.assertEqual(r.body, 'pouetpouetpouet')
        self.assertEqual(r.headers['Content-Type'], 'text/plain')

    def test_handle_delete(self):
        self.context.method = 'DELETE'
        self.srr().handle()
        self.manager.delete_resource.assert_called_once_with(
            ResourceWrapper(self.manager, 123))


class TestServiceActionRequest(unittest.TestCase):
    def setUp(self):
        self.manager = manager = mock.Mock()
        self.url = url = URL(['abc', None])
        self.acs = mock.Mock(
            spec=ActionService,
            collection=manager,
            lock=mock.Mock(spec=Lock),
            resource_url=url
        )
        self.action = self.manager.do_the_stuff
        self.validate = self.action.resource_fields.validate
        self.validate.return_value = {}
        self.data = mock.Mock(name='data')
        self.context = mock.Mock(
            spec=CollectionContext,
            service=self.acs,
            method='POST',
            data=self.data,
            parameters={},
        )
        self.context.get_manager_instance.return_value = manager

    def sar(self):
        return ServiceActionRequest(self.context, [123], 'do_the_stuff')

    def test_handle(self):
        r = self.sar().handle()
        self.validate.assert_called_once_with(self.data)
        self.assertEqual(r, self.action.return_value)
