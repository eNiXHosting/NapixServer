#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
The launcher defines the infrastructure to prepare and run the Napix Server.

:class:`Setup` is intended to be overidden to customize running
as an integrated component or in a specialized server.
"""

import sys
import optparse
import logging

from napixd.launcher.setup import Setup, CannotLaunch


console = logging.getLogger('Napix.console')


def get_setup_class(class_name):
    if class_name == 'napixd.launcher.Setup':
        return Setup

    module, dot, name = class_name.rpartition('.')
    if not dot:
        raise CannotLaunch('setup class value is not a valid python dotted class path, eg: napixd.launcher.Setup')
    try:
        __import__(module)
    except Exception as e:
        raise CannotLaunch('Cannot import {0} because {1}'.format(module, e))

    try:
        setup_class = getattr(sys.modules[module], name)
    except AttributeError:
        raise CannotLaunch('Module {0} has no attribute {1}'.format(module, name))

    if not callable(setup_class):
        raise CannotLaunch('Setup class {0} is not callable'.format(setup_class))

    return setup_class


def launch(options, setup_class=None):
    """
    Helper function to run Napix.

    It creates a **setup_class** (by default :class:`Setup` instance with the given **options**.

    **options** is an iterable.

    The exceptions are caught and logged.
    The function will block until the server is killed.
    """

    parser = optparse.OptionParser(usage=Setup.HELP_TEXT)
    parser.add_option('-p', '--port',
                      help='The TCP port to listen to',
                      type='int',
                      )
    parser.add_option('-s', '--setup-class',
                      help='The setup class used to start the Napix server',
                      )
    parser.add_option('-G', '--no-auto-wsgi',
                      help='Do not guess which WSGI server napixd is running on',
                      action='store_false',
                      dest='auto_guess_wsgi',
                      default=True,
                      )
    keys, options = parser.parse_args(options)

    sys.stdin.close()

    try:
        setup_class = setup_class or keys.setup_class and get_setup_class(keys.setup_class) or Setup
    except CannotLaunch as e:
        sys.stderr.write('{0}\n'.format(e))
        sys.exit(2)
        return

    try:
        setup = setup_class(options, auto_guess_wsgi=keys.auto_guess_wsgi, port=keys.port)
    except CannotLaunch as e:
        console.critical(e)
        sys.exit(1)
        return
    except Exception as e:
        if not logging.getLogger('Napix').handlers:
            sys.stderr.write('Napix failed before the loggers went up\n')
            import traceback
            traceback.print_exc()
        else:
            console.exception(e)
            console.critical(e)
        sys.exit(-1)
        return

    try:
        setup.run()
    except (KeyboardInterrupt, SystemExit) as e:
        console.warning('Got %s, exiting', e.__class__.__name__)
        return
    except Exception, e:
        if 'print_exc' in setup.options:
            console.exception(e)
        console.critical(e)
        sys.exit(3)
