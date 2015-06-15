# Copyright 2014 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


"""
STARTING ASSUMPTIONS

On URIs:

The Redfish RESTful API is a "hypermedia API" by design.  This is to avoid
building in restrictive assumptions to the data model that will make it
difficult to adapt to future hardware implementations.  A hypermedia API avoids
these assumptions by making the data model discoverable via links between
resources.

A URI should be treated by the client as opaque, and thus should not be
attempted to be understood or deconstructed by the client.  Only specific top
level URIs (any URI in this sample code) may be assumed, and even these may be
absent based upon the implementation (e.g. there might be no /redfish/v1/Systems
collection on something that doesn't have compute nodes.)

The other URIs must be discovered dynamically by following href links.  This is
because the API will eventually be implemented on a system that breaks any
existing data model "shape" assumptions we may make now.  In particular,
clients should not make assumptions about the URIs for the resource members of
a collection.  For instance, the URI of a collection member will NOT always be
/redfish/v1/.../collection/1, or 2.  On systems with multiple compute nodes per
manager, a System collection member might be /redfish/v1/Systems/C1N1.

This sounds very complicated, but in reality (as these examples demonstrate),
if you are looking for specific items, the traversal logic isn't too
complicated.

On Resource Model Traversal:

Although the resources in the data model are linked together, because of cross
link references between resources, a client may not assume the resource model
is a tree.  It is a graph instead, so any crawl of the data model should keep
track of visited resources to avoid an infinite traversal loop.

A reference to another resource is any property called "href" no matter where
it occurs in a resource.

An external reference to a resource outside the data model is referred to by a
property called "extref".  Any resource referred to by extref should not be
assumed to follow the conventions of the API.

On Resource Versions:

Each resource has a "Type" property with a value of the format Tyepname.x.y.z
where
* x = major version - incrementing this is a breaking change to the schema y =
* minor version - incrementing this is a non-breaking additive change to the
* schema z = errata - non-breaking change

Because all resources are versioned and schema also have a version, it is
possible to design rules for "nearest" match (e.g. if you are interacting with
multiple services using a common batch of schema files).  The mechanism is not
prescribed, but a client should be prepared to encounter both older and newer
versions of resource types.

On HTTP POST to create:

WHen POSTing to create a resource (e.g. create an account or session) the
guarantee is that a successful response includes a "Location" HTTP header
indicating the resource URI of the newly created resource.  The POST may also
include a representation of the newly created object in a JSON response body
but may not.  Do not assume the response body, but test it.  It may also be an
ExtendedError object.

HTTP REDIRECT:

All clients must correctly handle HTTP redirect.  We (or Redfish) may
eventually need to use redirection as a way to alias portions of the data
model.

FUTURE:  Asynchronous tasks

In the future some operations may start asynchonous tasks.  In this case, the
client should recognized and handle HTTP 202 if needed and the 'Location'
header will point to a resource with task information and status.

JSON-SCHEMA:

The json-schema available at /redfish/v1/Schemas governs the content of the
resources, but keep in mind:
* not every property in the schema is implemented in every implementation.
* some properties are schemed to allow both null and anotehr type like string
* or integer.

Robust client code should check both the existence and type of interesting
properties and fail gracefully if expectations are not met.

GENERAL ADVICE:

Clients should always be prepared for:
* unimplemented properties (e.g. a property doesn't apply in a particular case)
* null values in some cases if the value of a property is not currently known
* due to system conditions HTTP status codes other than 200 OK.  Can your code
* handle an HTTP 500 Internal Server Error with no other info?  URIs are case
* insensitive HTTP header names are case insensitive JSON Properties and Enum
* values are case sensitive A client should be tolerant of any set of HTTP
* headers the service returns

"""

import base64
import gzip
import hashlib
import httplib
import json
import ssl
import StringIO
import sys
import urllib2
from urlparse import urlparse

from oslo_log import log as logging

from redfish import exception
from redfish import types


LOG = logging.getLogger('redfish')


def connect(host, user, password):
    return RedfishConnection(host, user, password)


class RedfishConnection(object):
    """Implements basic connection handling for Redfish APIs."""

    def __init__(self, host, user_name, password,
                 auth_token=None, enforce_SSL=True):
        """Initialize a connection to a Redfish service."""
        super(RedfishConnection, self).__init__()

        self.user_name = user_name
        self.password = password
        self.auth_token = auth_token
        self.enforce_SSL = enforce_SSL

        # context for the last status and header returned from a call
        self.status = None
        self.headers = None

        # If the http schema wasn't specified, default to HTTPS
        if host[0:4] != 'http':
            host = 'https://' + host
        self.host = host

        self._connect()

        if not self.auth_token:
            # TODO: if a token is returned by this call, cache it. However,
            # the sample HTML does not include any token data, so it's unclear
            # what we should do here.
            LOG.debug('Initiating session with host %s', self.host)
            auth_dict = {'Password': self.password, 'UserName': self.user_name}
            response = self.rest_post(
                    '/redfish/v1/Sessions', None, json.dumps(auth_dict))

        # TODO: do some schema discovery here and cache the result
        # self.schema = ...
        LOG.info('Connection established to host %s', self.host)

    def _connect(self):
        LOG.debug("Establishing connection to host %s", self.host)
        url = urlparse(self.host)
        if url.scheme == 'https':
            # New in Python 2.7.9, SSL enforcement is defaulted on.
            # It can be opted-out of, which might be useful for debugging
            # some things. The below case is the Opt-Out condition and
            # should be used with GREAT caution.
            if (sys.version_info.major == 2
                    and sys.version_info.minor == 7
                    and sys.version_info.micro >= 9
                    and self.enforce_SSL == False):
                cont = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
                cont.verify_mode = ssl.CERT_NONE
                self.connection = httplib.HTTPSConnection(
                        host=url.netloc, strict=True, context=cont)
            else:
                self.connection = httplib.HTTPSConnection(
                        host=url.netloc, strict=True)
        elif url.scheme == 'http':
            self.connection = httplib.HTTPConnection(
                    host=url.netloc, strict=True)
        else:
            raise exception.RedfishException(
                    message='Unknown connection schema')

    def _op(self, operation, suburi, request_headers=None, request_body=None):
        """
        REST operation generic handler

        :param operation: GET, POST, etc
        :param suburi: the URI path to the resource
        :param request_headers: optional dict of headers
        :param request_body: optional JSON body
        """
        # ensure trailing slash
        if suburi[-1:] != '/':
            suburi = suburi + '/'
        url = urlparse(self.host + suburi)

        if not isinstance(request_headers, dict):
            request_headers = dict()
        request_headers['Content-Type'] = 'application/json'

        # if X-Auth-Token specified, supply it instead of basic auth
        if self.auth_token is not None:
            request_headers['X-Auth-Token'] = self.auth_token
        # else use user_name/password and Basic Auth
        elif self.user_name is not None and self.password is not None:
            request_headers['Authorization'] = ("BASIC " + base64.b64encode(
                    self.user_name + ":" + self.password))
        # TODO: add support for other types of auth

        redir_count = 4
        while redir_count:
            # NOTE: Do not assume every HTTP operation will return a JSON body.
            # For example, ExtendedError structures are only required for
            # HTTP 400 errors and are optional elsewhere as they are mostly
            # redundant for many of the other HTTP status code.  In particular,
            # 200 OK responses should not have to return any body.
            self.connection.request(operation, url.path,
                    headers=request_headers, body=json.dumps(request_body))
            resp = self.connection.getresponse()
            body = resp.read()
            # NOTE:  this makes sure the headers names are all lower case
            # because HTTP says they are case insensitive
            headers = dict((x.lower(), y) for x, y in resp.getheaders())

            # Follow HTTP redirect
            if resp.status == 301 and 'location' in headers:
                url = urlparse(headers['location'])
                # TODO: cache these redirects
                LOG.debug("Following redirect to %s", headers['location'])
                redir_count -= 1
            else:
                break

        response = dict()
        try:
            response = json.loads(body.decode('utf-8'))
        except ValueError: # if it doesn't decode as json
            # NOTE:  resources may return gzipped content, so try to decode
            # as gzip (we should check the headers for Content-Encoding=gzip)
            try:
                gzipper = gzip.GzipFile(fileobj=StringIO.StringIO(body))
                uncompressed_string = gzipper.read().decode('UTF-8')
                response = json.loads(uncompressed_string)
            except:
                raise exception.RedfishException(message=
                        'Failed to parse response as a JSON document, '
                        'received "%s".' % body)

        self.status = resp.status
        self.headers = headers
        return response

    def rest_get(self, suburi, request_headers):
        """REST GET

        :param: suburi
        :param: request_headers
        """
        # NOTE:  be prepared for various HTTP responses including 500, 404, etc
        return self._op('GET', suburi, request_headers, None)

    def rest_patch(self, suburi, request_headers, request_body):
        """REST PATCH

        :param: suburi
        :param: request_headers
        :param: request_body
        NOTE: this body is a dict, not a JSONPATCH document.
              redfish does not follow IETF JSONPATCH standard
              https://tools.ietf.org/html/rfc6902
        """
        # NOTE:  be prepared for various HTTP responses including 500, 404, 202
        return self._op('PATCH', suburi, request_headers, request_body)

    def rest_put(self, suburi, request_headers, request_body):
        """REST PUT

        :param: suburi
        :param: request_headers
        :param: request_body
        """
        # NOTE:  be prepared for various HTTP responses including 500, 404, 202
        return self._op('PUT', suburi, request_headers, request_body)

    def rest_post(self, suburi, request_headers, request_body):
        """REST POST

        :param: suburi
        :param: request_headers
        :param: request_body
        """
        # NOTE:  don't assume any newly created resource is included in the
        # response.  Only the Location header matters.
        # the response body may be the new resource, it may be an
        # ExtendedError, or it may be empty.
        return self._op('POST', suburi, request_headers, request_body)

    def rest_delete(self, suburi, request_headers):
        """REST DELETE

        :param: suburi
        :param: request_headers
        """
        # NOTE:  be prepared for various HTTP responses including 500, 404
        # NOTE:  response may be an ExtendedError or may be empty
        return self._op('DELETE', suburi, request_headers, None)

    def get_root(self):
        return types.Root(self.rest_get('/redfish/v1', {}), connection=self)


class Version(object):
    def __init__(self, string):
        try:
            buf = string.split('.')
            if len(buf) < 2:
                raise AttributeError
        except AttributeError:
            raise RedfishException(message="Failed to parse version string")
        self.major = int(buf[0])
        self.minor = int(buf[1])

    def __repr__(self):
        return str(self.major) + '.' + str(self.minor)


# return the type of an object (down to the major version, skipping minor, and errata)
def get_type(obj):
    typever = obj['Type']
    typesplit = typever.split('.')
    return typesplit[0] + '.' + typesplit[1]


# checks HTTP response headers for specified operation (e.g. 'GET' or 'PATCH')
def operation_allowed(headers_dict, operation):
    if 'allow' in headers_dict:
        if headers_dict['allow'].find(operation) != -1:
            return True
    return False


# Message registry support
# XXX not supported yet
message_registries = {}


# Build a list of decoded messages from the extended_error using the message
# registries An ExtendedError JSON object is a response from the with its own
# schema.  This function knows how to parse the ExtendedError object and, using
# any loaded message registries, render an array of plain language strings that
# represent the response.
def render_extended_error_message_list(extended_error):
    messages = []
    if isinstance(extended_error, dict):
        if 'Type' in extended_error and extended_error['Type'].startswith('ExtendedError.'):
            for msg in extended_error['Messages']:
                MessageID = msg['MessageID']
                x = MessageID.split('.')
                registry = x[0]
                msgkey = x[len(x) - 1]

                # if the correct message registry is loaded, do string resolution
                if registry in message_registries:
                    if registry in message_registries and msgkey in message_registries[registry]['Messages']:
                        msg_dict = message_registries[registry]['Messages'][msgkey]
                        msg_str = MessageID + ':  ' + msg_dict['Message']

                        for argn in range(0, msg_dict['NumberOfArgs']):
                            subst = '%' + str(argn+1)
                            msg_str = msg_str.replace(subst, str(msg['MessageArgs'][argn]))

                        if 'Resolution' in msg_dict and msg_dict['Resolution'] != 'None':
                            msg_str += '  ' + msg_dict['Resolution']

                        messages.append(msg_str)
                else: # no message registry, simply return the msg object in string form
                    messages.append('No Message Registry Info:  '+ str(msg))

    return messages


# Print a list of decoded messages from the extended_error using the message registries
def print_extended_error(extended_error):
    messages = render_extended_error_message_list(extended_error)
    msgcnt = 0
    for msg in messages:
        print('\t' + msg)
        msgcnt += 1
    if msgcnt == 0: # add a spacer
        print
