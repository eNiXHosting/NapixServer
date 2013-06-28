#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ResourceFields is the property class of managers' resource_field.

It makes the documentation and the poperty homogenous.
"""

import collections
from napixd.exceptions import ImproperlyConfigured, ValidationError

__all__ = [
        'ResourceFields',
        'ResourceField',
        'ResourceFieldsDict',
        'ResourceFieldsDescriptor',
        ]

class ResourceFields( object):
    """
    The property object.

    When accessing it as a class property, it returns a dict-like object of the resource_fields.

    When it is accessed through a manager instance, it returns a :class:`ResourceFieldsDescriptor`.
    """
    def __init__(self, resource_fields):
        self.values = [ ResourceField( name, meta) for name, meta in resource_fields.items() ]

    def __get__(self, instance, owner):
        if instance is None:
            return ResourceFieldsDict( owner, self.values )
        return ResourceFieldsDescriptor( instance, self.values )

class ResourceFieldsDict( collections.Mapping):
    """
    The class view of the resource_fields

    It behaves as a dict.

    The fields returned are a combination of the properties of the
    :class:`ResourceField` and the :attr:`ResourceField.extra`
    and the extra **validate** member extracted from
    the corresponding :meth:`~napixd.managers.base.Manager.validate_resource_FIELDNAME`
    if it exists.
    """
    def __init__(self, manager_class, values):
        self.resource_fields = values
        self.values = {}
        for resource_field in values:
            field = resource_field.name
            field_meta = resource_field.resource_field()
            validation_method = getattr( manager_class, 'validate_resource_' + field, None)

            if hasattr( validation_method, '__doc__') and validation_method.__doc__ is not None:
                field_meta['validation'] = validation_method.__doc__.strip()
            else:
                field_meta['validation'] = ''

            self.values[ field] = field_meta

    def __getitem__(self, item):
        return self.values[item]
    def __len__(self):
        return len( self.values)
    def __iter__(self):
        return iter( self.values)

    def get_example_resource(self):
        """
        Returns the example resource found with the :attr:`~ResourceField.example` field of the resource fields.

        The :attr:`~ResourceField.computed` field are ignored.
        """
        example = {}
        for field in self.resource_fields:
            if field.computed:
                continue
            example[field.name]= field.example
        return example


class ResourceFieldsDescriptor( collections.Sequence):
    """
    The instance view of resource_fields

    This object manages the relations between a manager and its resource_fields.
    """
    def __init__(self, manager, values):
        self.manager = manager
        self.values = values

    def __getitem__(self, item):
        return self.values[item]

    def __len__(self):
        return len(self.values)

    def serialize(self, raw):
        """
        Prepare the data from **raw** to be serialized to JSON.
        """
        dest = {}
        for k in self.values:
            try:
                 value = raw[k.name]
            except KeyError:
                pass
            else:
                dest[k.name] = k.serialize(value)
        return dest

    def unserialize(self, raw):
        """
        Extract the data from **raw**.
        """
        dest = {}
        for k in self:
            try:
                 value = raw[k.name]
            except KeyError:
                pass
            else:
                dest[k.name] = k.unserialize(value)
        return dest

    def validate(self, input, for_edit=False):
        """
        Validate the **input**.
        If **for_edit** is set to True, the *input* is validated as the modification of an existing resource.

        Field are ignored and remove from *input* if

        * The property :attr:`ResourceField.computed` is set.
        * The property :attr:`ResourceField.editable` is not set and **for_edit** is True.

        A :exc:`napixd.exceptions.ValidationError` is raised when

        * A field is missing and is :attr:`ResourceField.required`.
        * A field does not satisfies :meth:`ResourceField.validate`.

        """
        output = {}
        for resource_field in self:
            key = resource_field.name
            if resource_field.computed or for_edit and not resource_field.editable :
                continue
            elif key not in input:
                if resource_field.default_on_null:
                    value = None
                elif not resource_field.required:
                    continue
                else:
                    raise ValidationError({
                        key : u'Required'
                        })
            else:
                value = input[key]

            output[key] = resource_field.validate( self.manager, value)
        return output

identity = lambda x:x
class ResourceField( object):
    """
    The object for each resource_fields member.

    It takes as arguments the name on the field and the :class:`dict`
    of values defined in the creation of the :class:`napixd.managers.base.Manager` class.

    Some members have conditions, if those conditions are not met,
    :exc:`napixd.exceptions.ImproperlyConfigured` is raised.

    .. attribute:: example

        **Mandatory** unless :attr:`computed` and :attr:`type` are set.

        If :attr:`type` is not defined, it is guessed from the example.
        If :attr:`type` is defined, :type:`example` must be an instance of it.

    .. attribute:: editable

        Set to False if the field is not writeable once the object is created.
        The field will be stripped from *resource_dict* before :meth:`napixd.managers.base.Manager.modify_resource` is called.

        :attr:`editable` is False if :attr:`computed` is True.

        Defaults to True

    .. attribute:: optional

        Set to True if the field is not required at all times.

        Defaults to False

    .. attribute:: default_on_null

        Set to True if the validation method can take ``None`` as an input an generate a default value,
        when the field is not present.

        Defaults to False

    .. attribute:: typing

        One of **static** or **dynamic**.
        When typing is static, the validation checks the :attr:`type` of the input
        and raises a :exc:`~napixd.exceptions.ValidationError` if it does not match.

        When it is dynamic, the type is not enforced.

        Defaults to *static*

    .. attribute:: type

        The type of the field.

        Defaults to ``type(example)``

    .. attribute:: unserializer

        The extractor from the serialized data.

    .. attribute:: serialize

        The serializer to the JSON representation.

    .. attribute:: extra

        All the fields from the resource_field which are not a property.
        Those fields are not used by the Napix Server but may be usefull to the clients.

        :description:
            The goal of the field.

        :display_order:
            The priority of the field.
            The fields with a lower *display_order* are shown first.

    """
    def __init__(self, name, values):
        self.name = name

        meta = {
            'editable' : True,
            'optional' : False,
            'computed' : False,
            'default_on_null' : False,
            'typing' : 'static',
            'unserializer' : identity,
            'serializer' : identity,
            }
        extra_keys = set( values).difference( meta)
        meta.update( values)

        self.optional = meta['optional']
        self.computed = meta['computed']
        self.default_on_null = meta['default_on_null']

        self.editable = not self.computed and meta.get( 'editable', True)

        explicit_type = meta.get('type')
        if explicit_type and not isinstance( explicit_type, type):
            raise ImproperlyConfigured( '{0}: type field must be a class'.format( self.name))

        try:
            self.example = meta['example']
        except KeyError:
            if not self.computed or not explicit_type:
                raise ImproperlyConfigured( '{0}: Missing example'.format( self.name))
            else:
                self.example = u''

        implicit_type = type(self.example)
        if implicit_type is str:
            implicit_type = unicode

        self.type = explicit_type or implicit_type
        self.typing = meta['typing']

        if self.typing == 'dynamic':
            self._dynamic_typing = True
        elif self.typing == 'static':
            self._dynamic_typing = False
            if type( self.example) != self.type and not self.computed:
                if self.type is unicode and isinstance( self.example, str):
                    self.example = unicode(self.example)
                else:
                    raise ImproperlyConfigured('{0}: Example is not of type {1}'.format( self.name, self.type.__name__))
        else:
            raise ImproperlyConfigured('{0}: typing must be one of "static", "dynamic"'.format( self.name))

        self.choices = meta.get( 'choices')
        self.unserialize = meta['unserializer']
        self.serialize = meta['serializer']

        self.extra = dict( (k, values[k]) for k in extra_keys )

    def __repr__(self):
        return 'Field <{0}>'.format( self.name)

    def check_type(self, value):
        """
        Check the :attr:`type` of **value**.

        It is always returns True if :attr:`typing` is **dynamic**.
        """
        if value is None and self.default_on_null:
            return True
        elif self._dynamic_typing:
            return True
        else:
            return isinstance( value, self.type)

    @property
    def required(self):
        """
        The field is :attr:`optional` or :attr:`computed`
        """
        return not ( self.optional or self.computed)

    def resource_field(self):
        values = dict( self.extra)
        values.update({
            'editable' : self.editable,
            'optional' : self.optional,
            'computed' : self.computed,
            'default_on_null' : self.default_on_null,
            'example' : self.example,
            'typing' : 'dynamic' if self._dynamic_typing else 'static',
            'choices' : self.choices
            })
        if self.unserialize in ( str, basestring, unicode):
            values['unserializer'] = 'string'
        elif self.unserialize is not identity:
            values['unserializer'] = self.unserialize.__name__

        if self.type in ( str, basestring, unicode):
            values['type'] = 'string'
        elif self.type is not identity:
            values['type'] = self.type.__name__

        if self.serialize in ( str, basestring, unicode):
            values['serializer'] = 'string'
        elif self.serialize is not identity:
            values['serializer'] = self.serialize.__name__

        return values


    def validate( self, manager, value):
        """
        Validate the input **value**.
        """
        if not self.check_type( value):
            raise ValidationError({
                    self.name : u'Bad type: {0} has type {2} but should be {1}'.format(
                        self.name, self.type.__name__, type(value).__name__)
                    })
        validator = getattr( manager, 'validate_resource_%s' % self.name, None)
        if validator:
            try:
                value = validator( value)
            except ValidationError, e:
                raise ValidationError({
                    self.name : unicode(e)
                    })
        return value