#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import cPickle as pickle

from napixd import get_path
from napixd.store.backends import Store, BaseStore, BaseBackend


class FileBackend(BaseBackend):
    ROOT = 'stores'

    def __init__(self, options):
        root = options.get('root')
        self.root = (get_path(root) if root else get_path(
            os.path.join(self.ROOT, self.__class__.__name__)))

    def get_args(self, collection):
        return (os.path.join(self.root, collection),), {}

    def get_class(self):
        return FileStore

    def _root_content(self):
        return (path
                for path in os.listdir(self.root)
                if not path.startswith('.'))

    def keys(self):
        return [path for path in self._root_content()
                if os.path.isfile(os.path.join(self.root, path))]


class FileStore(Store):

    """
    Store based on files.
    The collection is a file containing pickled datas.

    It takes an optional `path` argument that indicates the directory
    which contains the collections.
    If it is not given,
    the configuration key ``Napix.storage.file.path`` is used.
    """

    def __init__(self, collection):
        try:
            data = pickle.load(open(collection, 'r'))
        except IOError:
            data = {}
        super(FileStore, self).__init__(collection, data)

    def drop(self):
        super(FileStore, self).drop()
        if os.path.isfile(self.collection):
            os.unlink(self.collection)

    def save(self):
        pickle.dump(self.data, open(self.collection, 'w'))


class DirectoryBackend(FileBackend):

    def get_class(self):
        return DirectoryStore

    def keys(self):
        return [path for path in self._root_content()
                if os.path.isdir(os.path.join(self.root, path))]


class DirectoryStore(BaseStore):

    def __init__(self, collection):
        super(DirectoryStore, self).__init__(collection)
        self.dir_path = os.path.join(collection, '')

    def keys(self):
        try:
            return [x for x in os.listdir(self.dir_path) if x[0] != '.']
        except OSError:
            return []

    def _fname(self, key):
        if '/' in key:
            raise ValueError('No / in key names')
        return os.path.join(self.dir_path, key)

    def __setitem__(self, key, value, _retry=True):
        try:
            pickle.dump(value, open(self._fname(key), 'w'))
        except IOError:
            if _retry and not os.path.isdir(self.dir_path):
                os.makedirs(self.dir_path, 0700)
                self.__setitem__(key, value, _retry=False)
            else:
                raise

    def __getitem__(self, key):
        try:
            return pickle.load(open(self._fname(key), 'r'))
        except IOError:
            raise KeyError(key)

    def __delitem__(self, key):
        try:
            os.unlink(self._fname(key))
        except IOError:
            raise KeyError(key)

    def drop(self):
        for key in self.keys():
            del self[key]
        try:
            os.rmdir(self.dir_path)
        except OSError:
            pass

    def incr(self, key, by=0):
        raise NotImplementedError('DirectoryStore does not implement incr')
