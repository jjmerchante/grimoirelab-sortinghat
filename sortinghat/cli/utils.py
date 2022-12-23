# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2020 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#

import contextlib
import functools
import hashlib

import os.path
import unicodedata

import click
import jinja2


from .client import (SortingHatClient,
                     SortingHatClientError)


def _set_ssl_cb(ctx, param, value):
    ctx.params['ssl'] = None
    if value is not None:
        ctx.params['ssl'] = not value


def _set_path_cb(ctx, param, value):
    ctx.params['path'] = value


_conn_options = [
    click.option('-u', '--user', envvar='SORTINGHAT_CLIENT_USER',
                 help="Name of the user to authenticate on the server."),
    click.option('-p', '--password', envvar='SORTINGHAT_CLIENT_PASSWORD',
                 help="Password to authenticate on the server."),
    click.option('--host', envvar='SORTINGHAT_CLIENT_HOST',
                 help="Address to use for connection."),
    click.option('--port', envvar='SORTINGHAT_CLIENT_PORT',
                 help="Port number to use for connection."),
    click.option('--server-path', envvar='SORTINGHAT_CLIENT_PATH',
                 callback=_set_path_cb,
                 help="Path to the server API."),
    click.option('--disable-ssl',
                 is_flag=True,
                 default=None,
                 callback=_set_ssl_cb,
                 help="Disable SSL/TSL connection.")
]


def sh_client_cmd_options(func):
    """Decorator to add options to a command to initialize a client."""

    for option in reversed(_conn_options):
        func = option(func)
    return func


def sh_client(func):
    """Decorator to initialize a SortingHat client.

    This decorator initializes a client that will be
    available in the context object.
    """
    def _choose_param(name, cfg, param):
        """Choose between param or configuration value."""

        if param is not None:
            return param
        elif not cfg:
            return None
        else:
            if name == 'ssl':
                value = cfg.get(name, 'true')
                return value.lower() in ['true', '1']
            else:
                return cfg.get(name, None)

    @click.pass_context
    def initialize_client(ctx, *args, **kwargs):
        client_params = [
            'host', 'port', 'path', 'user', 'password', 'ssl'
        ]

        params = {
            name: _choose_param(name, ctx.obj, kwargs.pop(name))
            for name in client_params
        }

        # Create a client object and remember it as as the context object.
        client = SortingHatClient(**params)
        ctx.obj = client
        return ctx.invoke(func, ctx, *args, **kwargs)

    return functools.update_wrapper(initialize_client, func)


@contextlib.contextmanager
def connect(client):
    """Context for commands to handle connections.

    Creates a context that will initialize and dispose
    a client connection. Client errors will be handled
    and raised as `ClickException` instances.

    :param client: an initialized client
    """
    try:
        client.connect()
        yield client
    except SortingHatClientError as exc:
        if exc.errors:
            error = exc.errors[0]
            new_exc = click.ClickException(error['message'])
            new_exc.exit_code = error['extensions']['code']
        else:
            new_exc = click.ClickException(exc.msg)
        raise new_exc
    finally:
        client.disconnect()


def display(template, nl=True, **kwargs):
    """Render and display a template.

    Giving the name of a template with the parameter `template`,
    this function will locate and render it using the arguments
    passed as keywords.

    :param template: name of the template
    :param nl: if set to `True`, it renders a newline afterwards
    :param kwargs: list of attributes required to render the template
    """
    templates_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                 "templates")
    loader = jinja2.FileSystemLoader(templates_dir)
    env = jinja2.Environment(loader=loader,
                             lstrip_blocks=True, trim_blocks=True)

    t = env.get_template(template)
    s = t.render(**kwargs)
    click.echo(s, nl=nl)


def unaccent_string(unistr):
    """Convert a Unicode string to its canonical form without accents.

    This allows to convert Unicode strings which include accent
    characters to their unaccent canonical form. For instance,
    characters 'Ê, ê, é, ë' are considered the same character as 'e';
    characters 'Ĉ, ć' are the same as 'c'.

    :param unistr: Unicode string to unaccent

    :returns: Unicode string on its canonical form
    """
    if not isinstance(unistr, str):
        msg = "argument must be a string; {} given".format(unistr.__class__.__name__)
        raise TypeError(msg)

    cs = [c for c in unicodedata.normalize('NFD', unistr)
          if unicodedata.category(c) != 'Mn']
    string = ''.join(cs)

    return string


def generate_uuid(source, email=None, name=None, username=None):
    """Generate a UUID related to identity data.

    Based on the input data, the function will return the UUID
    associated to an identity. On this version, the UUID will
    be the SHA1 of `source:email:name:username` string.

    This string is case insensitive, which means same values
    for the input parameters in upper or lower case will produce
    the same UUID.

    The value of `name` will converted to its unaccent form which
    means same values with accent or unaccent chars (i.e 'ö and o')
    will generate the same UUID.

    For instance, these combinations will produce the same UUID:
        ('scm', 'jsmith@example.com', 'John Smith', 'jsmith'),
        ('scm', 'jsmith@example,com', 'Jöhn Smith', 'jsmith'),
        ('scm', 'jsmith@example.com', 'John Smith', 'JSMITH'),
        ('scm', 'jsmith@example.com', 'john Smith', 'jsmith')

    :param source: data source
    :param email: email of the identity
    :param name: full name of the identity
    :param username: user name used by the identity

    :returns: a universal unique identifier for Sorting Hat

    :raises ValueError: when source is `None` or empty; each one
        of the parameters is `None`; or the parameters are empty.
    """
    def to_str(value, unaccent=False):
        s = str(value)
        if unaccent:
            return unaccent_string(s)
        else:
            return s

    if source is None:
        raise ValueError("'source' cannot be None")
    if source == '':
        raise ValueError("'source' cannot be an empty string")
    if not (email or name or username):
        raise ValueError("identity data cannot be empty")

    s = ':'.join((to_str(source),
                  to_str(email),
                  to_str(name, unaccent=True),
                  to_str(username))).lower()
    s = s.encode('UTF-8', errors="surrogateescape")

    sha1 = hashlib.sha1(s)
    uuid = sha1.hexdigest()

    return uuid
