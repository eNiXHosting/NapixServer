#!/usr/bin/env python
# -*- coding: utf-8 -*-

import itertools
import functools

import bottle
from bottle import HTTPError
from napixd.exceptions import NotFound,ValidationError,Duplicate

"""
The service class ack like a proxy between bottle and napix resource Manager Component.

It handle bottle registering, url routing and Manager configuration when needed.
"""

class Service(object):
    """
    The service objects make the interface between the end user's HTTP calls and the active modules.
    """
    def __init__(self,collection,configuration):
        """
        Create a base service for the given collection and its managed classes.
        collection MUST be a Manager subclass and configuration an instance of Conf
        for this collection
        """
        self.configuration = configuration
        self.collection_services = []
        first_service = self._create_collection_service(None,collection)
        self.url = first_service.url

    def _create_collection_service(self,previous_service,collection, append_url=True):
        service = CollectionService(previous_service, collection, self.configuration, append_url)
        self.collection_services.append(service)

        if collection.managed_class != None:
            try:
                for managed_class in collection.managed_class:
                    self._create_collection_service(service, managed_class, True)
            except TypeError:
                self._create_collection_service(service,
                        collection.managed_class, False)
        return service


    def setup_bottle(self,app):
        """
        Route the managers inside the given bottle app.
        """
        for service in self.collection_services:
            service.setup_bottle(app)

class CollectionService(object):
    def __init__(self, previous_service, collection, config, append_url):
        """
        Serve the collection given as a managed class of the previous_service, with the config given.
        collection is a subclass of Manager
        previous_service is an instance of CollectionService that serve the Manager class below.
        previous_service is None when it's the base collection being served.
        config is the instance of Conf for this Service.
        append_url is a boolean that add the URL token between the previous and this service.
        """
        self.previous_service = previous_service
        self.collection = collection

        #Recursive list of services.
        self.services = list(self._services_stack())
        self.services.reverse()

        self.config= dict(config.for_manager(self.services))

        #url is added if append_url is True
        self.url = append_url and self.config.get('url',self.get_name()) or ''

        base_url = '/'
        last = len(self.services) -1
        #build the prefix url with the list of previous services
        for i,service in enumerate(self.services):
            base_url += service.get_prefix()
            if i != last:
                base_url += ':f%i/'%i
        #collection and resource urls of this service
        self.collection_url = base_url
        self.resource_url = base_url + ':f%i' % last

    def get_name(self):
        return self.collection.get_name()


    def get_prefix(self):
        """
        Get the prefix of this service
        if append_url was True, this service hasn't a prefix
        else, it's the url from the configuration
        ex:
        >>>cs = CollectionService(ps,ManagerClass,conf,append_url=True)
        >>>cs.get_prefix()
            'managerclass/'

        >>>cs = CollectionService(ps,ManagerClass,conf,append_url)
        >>>cs.get_prefix()
            ''
        """
        return self.url and self.url + '/' or ''
    def get_token(self,path):
        """
        get the url bit for a resource identified by path for this collection
        """
        return self.get_prefix()+str(path)

    def get_manager(self,path):
        """
        Get a manager of this collection with the given path.
        """
        return self._generate_manager(
                self._get_resource(path))

    def _generate_manager(self,resource):
        """
        instanciate a manager for the given resource
        """
        manager = self.collection(resource)
        manager.configure(self.config)
        return manager

    def _get_resource(self,path):
        """
        Get a resource with the given path.
        if this is the first CollectionService return {}
        """
        if path:
            return self.previous_service.get_manager(path[:-1]).get_resource(path[-1])
        else:
            return {}

    def _services_stack(self):
        """
        return the list of services before this one
        """
        serv = self
        yield serv
        while serv.previous_service:
            yield serv.previous_service
            serv = serv.previous_service

    def setup_bottle(self,app):
        """
        Register the routes of this collection inside the app
        """
        app.route(self.collection_url+'_napix_resource_fields',callback=self.as_resource_fields,
                method='GET',apply=ArgumentsPlugin())
        app.route(self.collection_url+'_napix_help',callback=self.as_help,
                method='GET',apply=ArgumentsPlugin())
        app.route(self.collection_url+'_napix_new',callback=self.as_example_resource,
                method='GET',apply=ArgumentsPlugin())
        app.route(self.collection_url,callback=self.as_collection,
                method='ANY',apply=ArgumentsPlugin())
        app.route(self.resource_url,callback=self.as_resource,
                method='ANY',apply=ArgumentsPlugin())
        try:
            iter(self.collection.managed_class)
            app.route(self.resource_url+'/',
                    callback = self.as_managed_classes , apply = ArgumentsPlugin())
        except TypeError:
            pass

    def _respond(self,cls,path):
        """
        shortcut method to respond a ServiceRequest subclass with the path given
        """
        return cls(bottle.request,path,self).handle()

    def as_resource(self,path):
        return self._respond(ServiceResourceRequest,path)

    def as_collection(self,path):
        return self._respond(ServiceCollectionRequest,path)

    def as_managed_classes(self,path):
        manager = self.collection({})
        url = ''
        for service,id_ in zip(self.services,path):
            url += '/'+service.get_token(id_)
        return ['%s/%s'%(url,x.get_name()) for x in manager.managed_class ]

    def as_help(self,path):
        manager = self.collection({})
        return {
                'doc' : manager.__doc__,
                'managed_class' : [ mc.get_name() for mc in self.collection.get_managed_classes() ],
                'collection_methods' : ServiceCollectionRequest.available_methods(manager),
                'resource_methods' : ServiceResourceRequest.available_methods(manager),
                'resource_fields' : manager.resource_fields
                }

    def as_resource_fields(self,path):
        manager = self.collection
        return manager.resource_fields

    def as_example_resource(self,path):
        manager = self.collection({})
        return manager.get_example_resource()


class ServiceRequest(object):
    """
    ServiceRequest is an abstract class that is created to serve a single request.
    """
    def __init__(self,request,path,service):
        """
        Create the object that will handle the request for the path given on the collection
        """
        self.request = request
        self.method = request.method
        self.service = service
        self.path = path

    @classmethod
    def available_methods(cls,manager):
        """
        Return the HTTP methods defined in the given manager
        that are usable with this ServiceRequest
        """
        available_methods = ['HEAD']
        for meth,callback in cls.METHOD_MAP.items():
            if hasattr(manager,callback):
                available_methods.append(meth)
        return available_methods


    def check_datas(self,collection):
        """
        Filter and check the collection fields.

        Remove any field that is not in the collection's field
        Call the validator of the collection
        """
        if self.request.method not in ('POST','PUT') :
            return {}
        data = {}
        for x in self.request.data:
            if x in collection.resource_fields:
                data[x] = self.request.data[x]
        data = collection.validate_resource(data)
        return data

    def get_manager(self):
        """
        Récupere la collection correspondante à la requete
        """
        return self.service.get_manager(self.path)

    def get_callback(self,manager):
        """
        recupere la callback de manager
        Si elle n'est pas disponible renvoie une erreur 405 avec les methodes possibles
        """
        try:
            return getattr(manager,self.METHOD_MAP[self.method])
        except (AttributeError,KeyError):
            raise HTTPError(405,
                    header=[ ('allow',','.join(self.available_methods(manager)))])

    def handle(self):
        """
        Actually handle the request.
        Call a set of methods that may be overrident by subclasses
        """
        try:
            #obtient l'object designé
            manager = self.get_manager()
            manager.start_request(self.request)
            #recupère la vue qui va effectuer la requete
            callback = self.get_callback(manager)
            #recupère les données valides pour cet objet
            datas =  self.check_datas(manager)
            #recupere les arguments a passer a cette vue
            args = self.get_args(datas)
            result =  callback(*args)
            manager.end_request(self.request)
            return result
        except ValidationError,e:
            raise HTTPError(400,str(e))
        except KeyError,e:
            raise HTTPError(400,'`%s` parameter is required'%str(e))
        except NotFound,e:
            raise HTTPError(404,'`%s` not found'%str(e))
        except Duplicate,e:
            raise HTTPError(409,'`%s` already exists'%str(e))

class ServiceCollectionRequest(ServiceRequest):
    """
    ServiceCollectionRequest is an implementation of ServiceRequest specified for Collection requests (urls ending with /)
    """
    #association de verbes HTTP aux methodes python
    METHOD_MAP = {
        'POST':'create_resource',
        'GET':'list_resource'
        }
    def get_args(self,datas):
        if self.method == 'POST':
            return (datas,)
        return tuple()
    def handle(self):
        result = super(ServiceCollectionRequest,self).handle()
        if self.method == 'POST':
            url = self.make_url(result)
            bottle.redirect(url)
        if self.method == 'GET':
            return map(self.make_url,result)
        return result
    def make_url(self,result):
        url = ''
        path = list(self.path)
        path.append(result)
        for service,id_ in zip(self.service.services,path):
            url += '/'+service.get_token(id_)
        return url

class ServiceResourceRequest(ServiceRequest):
    """
    ServiceResourceRequest is an implementation of ServiceRequest specified for Ressource requests (urls not ending with /)
    """
    METHOD_MAP = {
            'PUT':'modify_resource',
            'GET':'get_resource',
            'DELETE':'delete_resource',
        }

    def get_args(self,datas):
        if self.method == 'PUT':
            return (self.resource_id,datas)
        return (self.resource_id,)
    def get_manager(self):
        #get the last path token because we may not just want to GET the resource
        resource_id = self.path.pop()
        manager = super(ServiceResourceRequest,self).get_manager()
        #verifie l'identifiant de la resource aussi
        self.resource_id = manager.validate_id(resource_id)
        return manager


class ArgumentsPlugin(object):
    """
    Bottle only passes the arguments from the url by keyword.

    This bottle plugin get the dict provided by bottle and get it in a tuple form

    url: /plugin/:f1/:f2/:f3
    bottle args : { f1:path1, f2:path2, f3:path3 }
    after plugin: (path1,path2,path3)
    """
    name='argument'
    api = 2
    def apply(self,callback,route):
        @functools.wraps(callback)
        def inner(*args,**kw):
            path = self._get_path(args,kw)
            return callback(path)
        return inner

    def _get_path(self,args,kw):
        if args :
            return args
        return map(lambda x:kw[x],
                #limit to keywords given in the kwargs
                itertools.takewhile(lambda x:x in kw,
                    #infinite generator of f0,f1,f2,...
                    itertools.imap(lambda x:'f%i'%x,
                        #infinite generator of 0,1,2,3...
                        itertools.count())))
"""

GET     /a/     a.list()
POST    /a/     a.create()

GET     /a/1    a.get(1)
DELETE  /a/1    a.delete(1)
PUT     /a/1    a.modify(1)

GET     /a/1/   a.get(1).list()
POST    /a/1/   a.get(1).create()
PUT     /a/1/b  a.get(1).mofify(b)
GET     /a/1/b  a.get(1).get(b).get()

"""