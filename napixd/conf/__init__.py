#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
The napix Configuration class.

The Napix Configuration is a :class:`collections.MutableMapping`.
Keys are accessible by their name, or their path.
Their path are composed of each descendant joined by a ``.``.

The defautl configuration is loaded from a JSON file
:file:`HOME/conf/settings.json`

"""


import __builtin__
import logging
import json
import os.path
import collections
import napixd
from contextlib import contextmanager

logger = logging.getLogger('Napix.conf')

# So that it's overridable in the tests
open = open
DEFAULT_CONF = os.path.join(os.path.dirname(__file__), 'settings.json')

_sentinel = object()


class Conf(collections.Mapping):

    """
    Configuration Object

    The configuration object are dict like values.

    An access can span multiple keys

    .. code-block:: python

        c = Conf({ 'a': { 'b' : 1 }})
        c.get('a.b) == 1
    """
    _default = None

    def __init__(self, data=None):
        self.data = dict(data) if data else {}

    def __repr__(self):
        return repr(self.data)

    def __iter__(self):
        return (key for key in self.data if not key.startswith('#'))

    def iteritems(self):
        return ((key, value)
                for key, value in self.data.items()
                if not key.startswith('#'))

    def __len__(self):
        return len(self.data)

    paths = [
        napixd.get_file('conf/settings.json'),
        '/etc/napixd/settings.json',
    ]

    @classmethod
    def get_default(cls, value=None):
        """
        Get a value on the default conf instance.
        """
        if cls._default is None:
            cls.make_default()
        if value is None:
            return cls._default
        else:
            return cls._default.get(value)

    @classmethod
    def make_default(cls):
        """
        Load the configuration from the default file.

        If the configuration file does not exists,
        a new configuration file is created.
        """
        conf = None
        paths = iter(cls.paths)
        for path in paths:
            try:
                handle = open(path, 'r')
                logger.info('Using %s configuration file', path)
            except IOError:
                pass
            else:
                try:
                    conf = json.load(handle)
                    break
                except ValueError, e:
                    raise ValueError(
                        'Configuration file {0} contains a bad JSON object ({0})'.format(path, e))
                finally:
                    handle.close()
        else:
            try:
                logger.warning('Did not find any configuration, trying default conf from %s',
                               DEFAULT_CONF)
                with open(DEFAULT_CONF, 'r') as handle:
                    conf = json.load(handle)
                for path in cls.paths:
                    try:
                        logger.info('Try to write default conf to %s', path)
                        with open(path, 'w') as destination:
                            with open(DEFAULT_CONF, 'r') as source:
                                destination.write(source.read())
                    except IOError:
                        logger.warning('Failed to write conf in %s', path)
                    else:
                        logger.info('Conf written to %s', path)
                        break
                else:
                    logger.error('Cannot write defaulf conf')
            except IOError:
                logger.error('Did not find any configuration at all')
                conf = {}

        cls._default = cls(conf)
        return cls._default

    def __getitem__(self, item):
        if item in self.data:
            return self.data[item]
        if '.' in item:
            prefix, x, suffix = item.partition('.')
            base = self[prefix]
            if isinstance(base, dict):
                return Conf(base)[suffix]
        raise KeyError(item)

    def __contains__(self, item):
        if not self:
            return False
        if item in self.data:
            return True
        if '.' in item:
            prefix, x, suffix = item.partition('.')
            return suffix in self.get(prefix)
        return False

    def __nonzero__(self):
        return bool(self.data)

    def __eq__(self, other):
        return (isinstance(other, collections.Mapping) and
                other.keys() == self.keys() and
                other.values() == self.values())

    def get(self, section_id, default_value=_sentinel, type=None):
        """
        Return the value pointed at **section_id**.

        If the key does not exist, **default_value** is returned.
        If *default_value* is left by default, an empty :class:`Conf`
        instance is returned.
        """
        try:
            value = self[section_id]
        except (KeyError, ValueError):
            if default_value is not _sentinel:
                return default_value
            if type is not None:
                raise
            return Conf()

        if type and not isinstance(value, type):
            raise TypeError('{key} has not the required type "{required}" but is a "{actual}"'.format(
                key=section_id, required=type, actual=__builtin__.type(value).__name__))

        if isinstance(value, dict):
            return Conf(value)
        return value
