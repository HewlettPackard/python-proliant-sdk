from __future__ import print_function
 # Copyright 2014,2015 Hewlett Packard Enterprise Development, LP.
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

Provides examples of using the HP RESTful API on iLO for common use cases.  This is for tutorial/example purposes only.

---------------------------------------------------------------------------------------------------------------------
IMPORTANT!!!
---------------------------------------------------------------------------------------------------------------------
When developing a client for the HP RESTful API, be sure to not code based upon assumptions that are not guaranteed.
Search for, and note any 'NOTE' comments in this code to read about ways to avoid incorrect assumptions.

The reason avoiding these assumptions is so important is that implementations may vary across systems and firmware
versions, and we want your code to work consistently.

---------------------------------------------------------------------------------------------------------------------
STARTING ASSUMPTIONS
---------------------------------------------------------------------------------------------------------------------

On URIs:

The HP RESTful API is a "hypermedia API" by design.  This is to avoid building in restrictive assumptions to the
data model that will make it difficult to adapt to future hardware implementations.  A hypermedia API avoids these
assumptions by making the data model discoverable via links between resources.

A URI should be treated by the client as opaque, and thus should not be attempted to be understood or deconstructed
by the client.  Only specific top level URIs (any URI in this sample code) may be assumed, and even these may be
absent based upon the implementation (e.g. there might be no /rest/v1/Systems collection on something that doesn't
have compute nodes.)

The other URIs must be discovered dynamically by following href links.  This is because the API will eventually be
implemented on a system that breaks any existing data model "shape" assumptions we may make now.  In particular,
clients should not make assumptions about the URIs for the resource members of a collection.  For instance, the URI of
a collection member will NOT always be /rest/v1/.../collection/1, or 2.  On Moonshot a System collection member might be
/rest/v1/Systems/C1N1.

This sounds very complicated, but in reality (as these examples demonstrate), if you are looking for specific items,
the traversal logic isn't too complicated.

On Resource Model Traversal:

Although the resources in the data model are linked together, because of cross link references between resources,
a client may not assume the resource model is a tree.  It is a graph instead, so any crawl of the data model should
keep track of visited resources to avoid an infinite traversal loop.

A reference to another resource is any property called "href" no matter where it occurs in a resource.

An external reference to a resource outside the data model is referred to by a property called "extref".  Any
resource referred to by extref should not be assumed to follow the conventions of the API.

On Resource Versions:

Each resource has a "Type" property with a value of the format Tyepname.x.y.z where
* x = major version - incrementing this is a breaking change to the schema
* y = minor version - incrementing this is a non-breaking additive change to the schema
* z = errata - non-breaking change

Because all resources are versioned and schema also have a version, it is possible to design rules for "nearest"
match (e.g. if you are interacting with multiple services using a common batch of schema files).  The mechanism
is not prescribed, but a client should be prepared to encounter both older and newer versions of resource types.

On HTTP POST to create:

WHen POSTing to create a resource (e.g. create an account or session) the guarantee is that a successful response
includes a "Location" HTTP header indicating the resource URI of the newly created resource.  The POST may also
include a representation of the newly created object in a JSON response body but may not.  Do not assume the response
body, but test it.  It may also be an ExtendedError object.

HTTP REDIRECT:

All clients must correctly handle HTTP redirect.  We (or Redfish) may eventually need to use redirection as a way
to alias portions of the data model.

FUTURE:  Asynchronous tasks

In the future some operations may start asynchonous tasks.  In this case, the client should recognized and handle
HTTP 202 if needed and the 'Location' header will point to a resource with task information and status.

JSON-SCHEMA:

The json-schema available at /rest/v1/Schemas governs the content of the resources, but keep in mind:
* not every property in the schema is implemented in every implementation.
* some properties are schemed to allow both null and anotehr type like string or integer.

Robust client code should check both the existence and type of interesting properties and fail gracefully if
expectations are not met.

GENERAL ADVICE:

Clients should always be prepared for:
* unimplemented properties (e.g. a property doesn't apply in a particular case)
* null values in some cases if the value of a property is not currently known due to system conditions
* HTTP status codes other than 200 OK.  Can your code handle an HTTP 500 Internal Server Error with no other info?
* URIs are case insensitive
* HTTP header names are case insensitive
* JSON Properties and Enum values are case sensitive
* A client should be tolerant of any set of HTTP headers the service returns

"""


__author__ = 'HP'

import sys
import ssl
if (sys.version_info >= (3, 0)):
   # Python 3 imports
   from urllib.parse import urlparse
   from http.client import HTTPSConnection, HTTPConnection
   from io import StringIO
else:
   # Python 2 imports
   from urlparse import urlparse
   from httplib import HTTPSConnection, HTTPConnection
   from StringIO import StringIO

import base64
import json
import hashlib
import gzip
import re

# REST operation generic handler
def rest_op(operation, host, suburi, request_headers, request_body, iLO_loginname, iLO_password, x_auth_token=None, enforce_SSL=True):

    url = urlparse('https://' + host + suburi)
    #url = urlparse('http://' + host + suburi)

    if request_headers is None:
        request_headers = dict()

    # if X-Auth-Token specified, supply it instead of basic auth
    if x_auth_token is not None:
        request_headers['X-Auth-Token'] = x_auth_token
    # else use iLO_loginname/iLO_password and Basic Auth
    elif iLO_loginname is not None and iLO_password is not None:
        request_headers['Authorization'] = "BASIC " + base64.b64encode(iLO_loginname + ":" + iLO_password)

    redir_count = 4
    while redir_count:
        conn = None
        if url.scheme == 'https':
            # New in Python 2.7.9, SSL enforcement is defaulted on, but can be opted-out of.
            # The below case is the Opt-Out condition and should be used with GREAT caution.
            if( sys.version_info.major == 2 and
                sys.version_info.minor == 7 and
                sys.version_info.micro >= 9 and
                enforce_SSL            == False):
                cont=ssl.SSLContext(ssl.PROTOCOL_TLSv1)
                cont.verify_mode = ssl.CERT_NONE
                conn = HTTPSConnection(host=url.netloc, strict=True, context=cont)
            else:
                conn = HTTPSConnection(host=url.netloc, strict=True)
        elif url.scheme == 'http':
            conn = HTTPConnection(host=url.netloc, strict=True)
        else:
            assert(False)
        conn.request(operation, url.path, headers=request_headers, body=json.dumps(request_body))
        resp = conn.getresponse()
        body = resp.read()

        # NOTE:  Do not assume every HTTP operation will return a JSON body.  For example, ExtendedError structures
        # are only required for HTTP 400 errors and are optional elsewhere as they are mostly redundant for many of the
        # other HTTP status code.  In particular, 200 OK responses should not have to return any body.

        # NOTE:  this makes sure the headers names are all lower cases because HTTP says they are case insensitive
        headers = dict((x.lower(), y) for x, y in resp.getheaders())

        # Follow HTTP redirect
        if resp.status >= 300 and resp.status < 400 and 'location' in  headers:
            url = urlparse(headers['location'])
            redir_count -= 1
        else:
            break

    response = dict()
    try:
        response = json.loads(body.decode('utf-8'))
    except ValueError: # if it doesn't decode as json
        # NOTE:  resources may return gzipped content
        # try to decode as gzip (we should check the headers for Content-Encoding=gzip)
        try:
            gzipper = gzip.GzipFile(fileobj=StringIO(body))
            uncompressed_string = gzipper.read().decode('UTF-8')
            response = json.loads(uncompressed_string)
        except:
            pass

        # return empty
        pass

    return resp.status, headers, response

# REST GET
def rest_get(host, suburi, request_headers, iLO_loginname, iLO_password):
    return rest_op('GET', host, suburi, request_headers, None, iLO_loginname, iLO_password)
    # NOTE:  be prepared for various HTTP responses including 500, 404, etc.

# REST PATCH
def rest_patch(server, suburi, request_headers, request_body, iLO_loginname, iLO_password):
    if not isinstance(request_headers, dict):  request_headers = dict()
    request_headers['Content-Type'] = 'application/json'
    return rest_op('PATCH', server, suburi, request_headers, request_body, iLO_loginname, iLO_password)
    # NOTE:  be prepared for various HTTP responses including 500, 404, 202 etc.

# REST PUT
def rest_put(host, suburi, request_headers, request_body, iLO_loginname, iLO_password):
    if not isinstance(request_headers, dict):  request_headers = dict()
    request_headers['Content-Type'] = 'application/json'
    return rest_op('PUT', host, suburi, request_headers, request_body, iLO_loginname, iLO_password)
    # NOTE:  be prepared for various HTTP responses including 500, 404, 202 etc.

# REST POST
def rest_post(host, suburi, request_headers, request_body, iLO_loginname, iLO_password):
    if not isinstance(request_headers, dict):  request_headers = dict()
    request_headers['Content-Type'] = 'application/json'
    return rest_op('POST', host, suburi, request_headers, request_body, iLO_loginname, iLO_password)
    # NOTE:  don't assume any newly created resource is included in the response.  Only the Location header matters.
    # the response body may be the new resource, it may be an ExtendedError, or it may be empty.

# REST DELETE
def rest_delete(host, suburi, request_headers, iLO_loginname, iLO_password):
    return rest_op('DELETE', host, suburi, request_headers, None, iLO_loginname, iLO_password)
    # NOTE:  be prepared for various HTTP responses including 500, 404, etc.
    # NOTE:  response may be an ExtendedError or may be empty

# this is a generator that returns collection members
def collection(host, collection_uri, request_headers, iLO_loginname, iLO_password):

    # get the collection
    status, headers, thecollection = rest_get(host, collection_uri, request_headers, iLO_loginname, iLO_password)

    while status < 300:

        # verify expected type

        # NOTE:  Because of the Redfish standards effort, we have versioned many things at 0 in anticipation of
        # them being ratified for version 1 at some point.  So this code makes the (unguarranteed) assumption
        # throughout that version 0 and 1 are both legitimate at this point.  Don't write code requiring version 0 as
        # we will bump to version 1 at some point.

        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(thecollection) == 'Collection.0' or get_type(thecollection) == 'Collection.1')

        # if this collection has inline items, return those

        # NOTE:  Collections are very flexible in how the represent members.  They can be inline in the collection
        # as members of the 'Items' array, or they may be href links in the links/Members array.  The could actually
        # be both.  Typically, iLO implements the inline (Items) for only when the collection is read only.  We have
        # to render it with the href links when an array contains PATCHable items because its complex to PATCH
        # inline collection members.
        # A client may wish to pass in a boolean flag favoring the href links vs. the Items in case a collection
        # contains both.

        if 'Items' in thecollection:

            # iterate items
            for item in thecollection['Items']:
                # if the item has a self uri pointer, supply that for convenience
                memberuri = None
                if 'links' in item and 'self' in item['links']:
                    memberuri = item['links']['self']['href']

                # Read up on Python generator functions to understand what this does.
                yield 200, None, item, memberuri

        # else walk the member links
        elif 'links' in thecollection and 'Member' in thecollection['links']:

            # iterate members
            for memberuri in thecollection['links']['Member']:
                # for each member return the resource indicated by the member link
                status, headers, member = rest_get(host, memberuri['href'], request_headers, iLO_loginname, iLO_password)

                # Read up on Python generator functions to understand what this does.
                yield status, headers, member, memberuri['href']

        # page forward if there are more pages in the collection
        if 'links' in thecollection and 'NextPage' in thecollection['links']:
            next_link_uri = collection_uri + '?page=' + str(thecollection['links']['NextPage']['page'])
            status, headers, thecollection = rest_get(host, next_link_uri, request_headers, iLO_loginname, iLO_password)

        # else we are finished iterating the collection
        else:
            break

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
message_registries = {}

# Build a list of decoded messages from the extended_error using the message registries
# An ExtendedError JSON object is a response from the with its own schema.  This function knows
# how to parse the ExtendedError object and, using any loaded message registries, render an array of
# plain language strings that represent the response.
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
        print()

# Validate BIOS Enumeration setting
def validate_bios_enum(attribute, value):
    assert(attribute["Type"] == "Enumeration")
    if type(value) is not str:
        return None

    for enum_value in attribute['Value']:
        if value == enum_value['ValueName']:
            return value

    print('\tValue did not match a possible enumeration')
    return None

# Validate BIOS String setting
def validate_bios_string(attribute, value):
    assert(attribute["Type"] == "String")
    if type(value) is not str:
        return None

    if len(value) < attribute.get("MinLength", -1):
        print('\tString too short')
        return None

    if len(value) > attribute.get("MaxLength", len(value)):
        print('\tString too long')
        return None

    if 'ValueExpression' in attribute and not re.match(attribute['ValueExpression'], value):
        print('\tString did not match required format')
        return None

    return value

# Validate BIOS Integer setting
def validate_bios_int(attribute, value):
    assert(attribute["Type"] == "Integer")
    try:
        value = int(value)
    except ValueError:
        print('\tValue was not an integer')
        return None

    if value < attribute.get('LowerBound', value):
        print('\tInteger value too low')
        return None

    if value > attribute.get('UpperBound', value):
        print('\tInteger value too high')
        return None

    return value

# Validate BIOS Boolean setting
def validate_bios_bool(attribute, value):
    assert(attribute["Type"] == "Boolean")
    if not isinstance(value,bool):
        if value == 'true':
            value = True
        elif value == 'false':
            value = False
        else:
            print('\tValue was not boolean')
            return None

    return value

# Validate BIOS Password setting
def validate_bios_password(attribute, value):
    assert(attribute["Type"] == "Password")
    # (anything that looks like a string is fine)
    return str(value)

# Determine whether the requested BIOS setting is allowed by the restrictions
# listed in the BIOS Attribute Registry. One of the Type-specific validation
# functions is used, which will convert the input value to the appropriate Type
# if possible, or return None if it isn't valid.
def validate_bios_value(registry, bios_property, value):

    # First find the corresponding entry in the Registry
    for attribute in registry['RegistryEntries']['Attributes']:
        if attribute['Name'] == bios_property:
            break

    if attribute['Name'] != bios_property:
        print('\tCould not find property in attribute registry')
        return None

    if attribute['ReadOnly']:
        print('\tProperty is read-only')
        return None

    attr_type = attribute['Type']
    if attr_type == 'Enumeration':
        return validate_bios_enum(attribute, value)
    elif attr_type == 'String':
        return validate_bios_string(attribute, value)
    elif attr_type == 'Integer':
        return validate_bios_int(attribute, value)
    elif attr_type == 'Boolean':
        return validate_bios_bool(attribute, value)
    elif attr_type == 'Password':
        return validate_bios_password(attribute, value)
    else:
        print('\tUnknown type {}'.format(attr_type))
        return None

# Determine whether the requested BIOS setting is allowed by the setting
# dependencies listed in the BIOS Attribute Registry.
def validate_bios_deps(registry, bios_settings, bios_property, value):
    deps = registry['RegistryEntries']['Dependencies']
    for dep in deps:
        if dep['DependencyFor'] != bios_property:
            continue

        if dep['Dependency']['MapToAttribute'] != bios_property:
            print('\tNot enforcing triggered dependency for different attribute')
            continue

        map_froms = dep['Dependency']['MapFrom']
        eval_str = ''
        for map_from in map_froms:
            from_attr = map_from['MapFromAttribute']
            from_prop = map_from['MapFromProperty']
            from_cond = map_from['MapFromCondition']
            from_val = map_from['MapFromValue']
            if from_prop != 'CurrentValue':
                print('\tUnsupported MapFromProperty in dependency')
                return False

            if 'MapTerms' in map_from:
                term = map_from['MapTerms']
                if term == '&&':
                    eval_str += ' and'
                elif term == '||':
                    eval_str += ' or'
                else:
                    print('\tInvalid MapTerms')
                    return False

            eval_str += ' bios_settings["{}"] {} {}'.format(from_attr, from_cond, json.dumps(from_val))

        # Eval is always risky, but it saves some interpretation logic here.
        # Don't use if you don't trust the data returned by the API!
        if not eval(eval_str):
            continue

        print('\tActive dependency: {}'.format(eval_str))

        to_prop = dep['Dependency']['MapToProperty']
        to_val = dep['Dependency']['MapToValue']

        if to_prop == 'ReadOnly' and to_val == True:
            print('\t\t{} setting not accepted (ReadOnly)'.format(bios_property))
            return False

        if to_prop == 'CurrentValue' and to_val != value:
            print('\t\t{} setting not accepted (must be {})'.format(bios_property, to_val))
            return False

        if to_prop == 'GrayOut' and to_val == True:
            print('\t\t{} setting accepted but has no effect (GrayOut)'.format(bios_property))
            continue

    return True

# Determine whether a requested BIOS setting is allowed by the rules listed in
# the BIOS Attribute Registry. This will also convert the input value from a
# string to the required type, if such a conversion is possible. The
# validated/converted value is returned, or None if validation fails.
def validate_bios_setting(registry, bios_settings, bios_property, value):
    print("\tValidating {} = {}".format(bios_property, value))

    # First, validate it's value is within bounds
    value = validate_bios_value(registry, bios_property, value)
    if value is None:
        print('\tValue validation failed')
        return None

    # Then, check dependencies
    if validate_bios_deps(registry, bios_settings, bios_property, value):
        return value
    else:
        print('\tDependency checking failed')
        return None

def ex0_get_bios_resource(host, iLO_loginname, iLO_password):
        
    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, system, memberuri in collection(host, '/rest/v1/Systems', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(system) == 'ComputerSystem.0' or get_type(system) == 'ComputerSystem.1')

        # find the BIOS URI
        try:
            bios_uri = system['Oem']['Hp']['links']['BIOS']['href']
        except KeyError:
            print('\tComputerSystem/Oem/Hp does not contain link to BIOS')
            continue

        # get the BIOS object
        status, headers, bios_settings = rest_get(host, bios_uri, None, iLO_loginname, iLO_password)

        if status < 300:
            return bios_settings, status, headers

    print('\tCould not find BIOS resource')
    return None

def bios_patch_template(host, iLO_loginname, iLO_password, bios_properties, values, bios_password=None, doValidation=False):
    # Get the BIOS resource
    bios_settings, status, headers = ex0_get_bios_resource(host, iLO_loginname, iLO_password)

    # check to make sure the bios_properties are supported
    # if not, its OK to PATCH it but it will generate an error if not implemented and waste everyone's time
    for i in range(len(bios_properties)):
        if bios_properties[i] not in bios_settings:
            # not supported on this platform
            print('\tBIOS Property "' + bios_properties[i] + '" is not supported on this system')
            return

    registry_name = bios_settings['AttributeRegistry']

    # if this BIOS resource doesn't support PATCH, go get the Settings, which should
    if not operation_allowed(headers, 'PATCH'):   # this is GET-only
        bios_uri = bios_settings['links']['Settings']['href']
        status, headers, bios_settings = rest_get(host, bios_uri, None, iLO_loginname, iLO_password)
        print('Not support PATCH')
        assert(operation_allowed(headers, 'PATCH'))   # this allows PATCH

    # Validate setting (and possibly convert value to correct Type)
    if doValidation:
        registry = ex26_get_registry(host, iLO_loginname, iLO_password, registry_name)[1]
        for i in range(len(bios_properties)):
            values[i] = validate_bios_settings(registry, bios_settings, bios_properties[i], values[i])
            if values[i] is None:
                return

    # we don't need to PATCH back everything, just the one bios_properties we want to change
    new_bios_settings = dict()
    for i in range(len(bios_properties)):
        new_bios_settings[bios_properties[i]] = values[i]
    request_headers = dict()
    if bios_password:
        bios_password_hash = hashlib.sha256(bios_password.encode()).hexdigest().upper()
        request_headers['X-HPRESTFULAPI-AuthToken'] = bios_password_hash

    # perform the patch
    print('PATCH ' + json.dumps(new_bios_settings) + ' to ' + bios_uri)
    status, headers, response = rest_patch(host, bios_uri, request_headers, new_bios_settings, iLO_loginname, iLO_password)
    print('PATCH response = ' + str(status))
    print_extended_error(response)
    assert(status < 300)
    return status

# noinspection PyPep8Naming
def ex1_change_bios_setting(host, bios_property, value, iLO_loginname, iLO_password, bios_password):

    print('EXAMPLE 1:  Change a BIOS setting')

    bios_patch_template(host, iLO_loginname, iLO_password, bios_property, value, bios_password, doValidation=True);

# noinspection PyPep8Naming
def ex2_reset_server(host, iLO_loginname, iLO_password):

    print('EXAMPLE 2:  Reset a server')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, system, memberuri in collection(host, '/rest/v1/Systems', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(system) == 'ComputerSystem.0' or get_type(system) == 'ComputerSystem.1')

        # verify it supports POST
        assert(operation_allowed(headers, 'POST'))

        action = dict()
        action['Action'] = 'Reset'
        action['ResetType'] = 'ForceRestart'

        # perform the POST action
        print('POST ' + json.dumps(action) + ' to ' + memberuri)
        status, headers, response = rest_post(host, memberuri, None, action, iLO_loginname, iLO_password)
        print('POST response = ' + str(status))
        print_extended_error(response)

        # point made...quit
        break

# noinspection PyPep8Naming
def ex3_enable_secure_boot(host, secure_boot_enable, iLO_loginname, iLO_password):

    print('EXAMPLE 3:  Enable UEFI Secure Boot')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, system, memberuri in collection(host, '/rest/v1/Systems', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(system) == 'ComputerSystem.0' or get_type(system) == 'ComputerSystem.1')

        # find the BIOS URI
        if 'links' not in system['Oem']['Hp'] or 'SecureBoot' not in system['Oem']['Hp']['links']:
            print('\t"SecureBoot" resource or feature is not supported on this system')
            return
        secure_boot_uri = system['Oem']['Hp']['links']['SecureBoot']['href']

        # get the Secure Boot object
        status, headers, secure_boot_settings = rest_get(host, secure_boot_uri, None, iLO_loginname, iLO_password)

        # if the BIOS doesn't support PATCH, go get the Settings, which should
        if not operation_allowed(headers, 'PATCH'):   # this is GET-only
            secure_boot_uri = secure_boot_settings['links']['Settings']['href']
            status, headers, boot_settings = rest_get(host, secure_boot_uri, None, iLO_loginname, iLO_password)
            assert(operation_allowed(headers, 'PATCH'))   # this allows PATCH

        # we don't need to PATCH back everything, just the one property we want to change
        new_secure_boot_settings = dict()
        new_secure_boot_settings['SecureBootEnable'] = secure_boot_enable

        # perform the patch
        print('PATCH ' + json.dumps(new_secure_boot_settings) + ' to ' + secure_boot_uri)
        status, headers, response = rest_patch(host, secure_boot_uri, None, new_secure_boot_settings, iLO_loginname, iLO_password)
        print('PATCH response = ' + str(status))
        print_extended_error(response)
        assert(status < 300)

        # point made...quit
        break

# noinspection PyPep8Naming
def ex4_bios_revert_default(host, iLO_loginname, iLO_password, default_overrides=None):

    if not default_overrides: default_overrides = {}
    print('EXAMPLE 4:  Revert BIOS Settings to default')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, system, memberuri in collection(host, '/rest/v1/Systems', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(system) == 'ComputerSystem.0' or get_type(system) == 'ComputerSystem.1')

        # find the BIOS URI
        if 'links' not in system['Oem']['Hp'] or 'BIOS' not in system['Oem']['Hp']['links']:
            print('\tBIOS Settings resource or feature is not supported on this system')
            return
        bios_uri = system['Oem']['Hp']['links']['BIOS']['href']

        # get the BIOS object
        status, headers, bios_settings = rest_get(host, bios_uri, None, iLO_loginname, iLO_password)

        # get the BaseConfigs object and check if the BaseConfig capability is supported before attempting to use it. 
        if 'BaseConfigs' not in bios_settings['links']:
            print('\t"links" section in Bios settings does not have a BaseConfigs resource')
            return
        
        bios_baseconfigs_uri = bios_settings['links']['BaseConfigs']['href']
        status, baseconfigs_headers, bios_baseconfigs = rest_get(host, bios_baseconfigs_uri, None, iLO_loginname, iLO_password)
        assert(status < 300)
        if not bios_baseconfigs['Capabilities']['BaseConfig']:
            print('BIOS BaseConfig capability is not supported.')
            return

        # if the BIOS doesn't support PUT, go get the Settings, which should
        if not operation_allowed(headers, 'PUT'):   # this is GET-only
            if 'Settings' not in bios_settings['links']:
                print('No BIOS settings resources allow PUT')
                return
            bios_uri = bios_settings['links']['Settings']['href']
            status, headers, bios_settings = rest_get(host, bios_uri, None, iLO_loginname, iLO_password)
            assert(operation_allowed(headers, 'PUT'))   # this allows PUT

        # we don't need to PUT back everything, just the one property we want to change
        new_bios_settings = dict()
        new_bios_settings['BaseConfig'] = 'default'
        # preserve the Type property from the existing BIOS settings to avoid an error
        new_bios_settings['Type'] = bios_settings['Type']
        # add in any caller-supplied override properties
        for override in default_overrides:
            new_bios_settings[override] = default_overrides[override]

        # perform the PUT
        print('PUT ' + json.dumps(new_bios_settings) + ' to ' + bios_uri)
        status, headers, response = rest_put(host, bios_uri, None, new_bios_settings, iLO_loginname, iLO_password)
        print('PUT response = ' + str(status))
        print_extended_error(response)
        assert(status < 300)

        # point made...quit
        break

def boot_order_device_type_to_top(device_type_str='NIC', current_boot_order=[]):
    """Returns a modified boot order. 

    Moves boot options matching the given device type to the top of the boot order. 

    device_type_str    -- A device type to match against. 
    current_boot_order -- The current boot order. 

    preconditions: 
    1. device_type_str is valid device type string. e.g "NIC.LOM.1.1.IPv4".
    2. current_boot_order is a valid list of structured boot strings. 
    e.g. ["Shell.Emb.1.1","NIC.LOM.1.1.IPv4","NIC.LOM.1.1.IPv6","Generic.USB.1.1"]

    Refer to the HpServerBootSettings.1 schema for additional details.

    """
    new_boot_order = []
    no_match = [] 
    for struc_boot_str in current_boot_order:
        if struc_boot_str.startswith(device_type_str):
            new_boot_order.append(struc_boot_str)
        else:
            no_match.append(struc_boot_str)

    new_boot_order.extend(no_match)

    return new_boot_order

# noinspection PyPep8Naming
def ex5_change_boot_order(host, iLO_loginname, iLO_password, bios_password):

    print('EXAMPLE 5:  Change Boot Order (UEFI)')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, system, memberuri in collection(host, '/rest/v1/Systems', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(system) == 'ComputerSystem.0' or get_type(system) == 'ComputerSystem.1')

        # find the BIOS URI
        if 'links' not in system['Oem']['Hp'] or 'BIOS' not in system['Oem']['Hp']['links']:
            print('\tBIOS Settings resource or feature is not supported on this system')
            return
        bios_uri = system['Oem']['Hp']['links']['BIOS']['href']

        # get the BIOS object
        status, headers, bios_settings = rest_get(host, bios_uri, None, iLO_loginname, iLO_password)

        # get the BOOT object
        if 'Boot' not in bios_settings['links']:
            print('\t"links" section in Bios settings does not have a Boot order resource')
            return
        boot_uri = bios_settings['links']['Boot']['href']
        status, headers, boot_settings = rest_get(host, boot_uri, None, iLO_loginname, iLO_password)

        # if the BIOS doesn't support PATCH, go get the Settings, which should
        if not operation_allowed(headers, 'PATCH'):   # this is GET-only
            boot_uri = boot_settings['links']['Settings']['href']
            status, headers, boot_settings = rest_get(host, boot_uri, None, iLO_loginname, iLO_password)
            assert(operation_allowed(headers, 'PATCH'))   # this allows PATCH

        # we don't need to PATCH back everything, just the one property we want to change
        new_boot_settings = dict()
        

        # Move any NIC boot options to the top of the boot order, if any exist. 
        new_boot_settings['PersistentBootConfigOrder'] = boot_order_device_type_to_top('NIC', boot_settings['PersistentBootConfigOrder'])

        # supply the BIOS setup iLO_password
        request_headers = dict()
        if bios_password:
            bios_password_hash = hashlib.sha256(bios_password.encode()).hexdigest().upper()
            request_headers['X-HPRESTFULAPI-AuthToken'] = bios_password_hash

        # perform the patch
        print('PATCH ' + json.dumps(new_boot_settings) + ' to ' + boot_uri)
        status, headers, response = rest_patch(host, boot_uri, request_headers, new_boot_settings, iLO_loginname, iLO_password)
        print('PATCH response = ' + str(status))
        print_extended_error(response)
        assert(status < 300)

        # point made...quit
        break


def ex5_1_boot_order_revert_default(host, iLO_loginname, iLO_password, bios_password):
    print('EXAMPLE 5.1:  Revert Boot Order to default (UEFI)')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, system, memberuri in collection(host, '/rest/v1/Systems', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(system) == 'ComputerSystem.0' or get_type(system) == 'ComputerSystem.1')

        # find the BIOS URI
        if 'links' not in system['Oem']['Hp'] or 'BIOS' not in system['Oem']['Hp']['links']:
            print('\tBIOS Settings resource or feature is not supported on this system')
            return
        bios_uri = system['Oem']['Hp']['links']['BIOS']['href']

        # get the BIOS object
        status, headers, bios_settings = rest_get(host, bios_uri, None, iLO_loginname, iLO_password)

        # get the BOOT object
        if 'Boot' not in bios_settings['links']:
            print('\t"links" section in Bios settings does not have a Boot order resource')
            return
        boot_uri = bios_settings['links']['Boot']['href']
        status, headers, boot_settings = rest_get(host, boot_uri, None, iLO_loginname, iLO_password)

        # get the BaseConfigs object and check if the BaseConfig capability is supported before attempting to use it. 
        if 'BaseConfigs' not in boot_settings['links']:
            print('\t"links" section in Boot settings does not have a BaseConfigs resource')
            return

        boot_baseconfigs_uri = boot_settings['links']['BaseConfigs']['href']
        status, baseconfigs_headers, boot_baseconfigs = rest_get(host, boot_baseconfigs_uri, None, iLO_loginname, iLO_password)
        assert(status < 300)
        if not boot_baseconfigs['Capabilities']['BaseConfig']:
            print('Boot BaseConfing capability is not supported.')
            return

        # Save the current default boot order
        new_default_boot_order = boot_baseconfigs['BaseConfigs'][0]['default']['DefaultBootOrder']
        # Change the default boot order policy to move Usb devices to the top of the boot order. 
        for i, boot_type_str in enumerate(new_default_boot_order):
            if boot_type_str == 'Usb':
                new_default_boot_order.pop(i)
                new_default_boot_order.insert(0,boot_type_str)
                break

        # if the BIOS doesn't support PATCH, go get the Settings, which should
        if not operation_allowed(headers, 'PATCH'):   # this is GET-only
            boot_uri = boot_settings['links']['Settings']['href']
            status, headers, boot_settings = rest_get(host, boot_uri, None, iLO_loginname, iLO_password)
            assert(operation_allowed(headers, 'PATCH'))   # this allows PATCH

        # PATCH {"BaseConfig":"default"} to indicate that we want to revert the boot order to its default.
        boot_settings['BaseConfig'] = 'default'
        boot_settings['DefaultBootOrder'] = new_default_boot_order

        # perform the patch
        print('PATCH ' + json.dumps(boot_settings) + ' to ' + boot_uri)
        status, headers, response = rest_patch(host, boot_uri, None, boot_settings, iLO_loginname, iLO_password)
        print('PATCH response = ' + str(status))
        print_extended_error(response)
        assert(status < 300)

        # point made...quit
        break

# noinspection PyPep8Naming
def ex6_change_temporary_boot_order(host, boottarget, iLO_loginname, iLO_password):

    print('EXAMPLE 6:  Change temporary boot order (one time boot or temporary override)')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, system, memberuri in collection(host, '/rest/v1/Systems', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(system) == 'ComputerSystem.0' or get_type(system) == 'ComputerSystem.1')

        # verify it supports PATCH
        assert(operation_allowed(headers, 'PATCH'))

        # verify the requested boot target is supported
        if boottarget in system['Boot']['BootSourceOverrideSupported']:

            # build a PATCH payload to change to the requested boot target
            boot = dict()
            boot['Boot'] = dict()
            boot['Boot']['BootSourceOverrideTarget'] = boottarget

            # perform the POST action
            print('PATCH ' + json.dumps(boot) + ' to ' + memberuri)
            status, headers, response = rest_patch(host, memberuri, None, boot, iLO_loginname, iLO_password)
            print('PATCH response = ' + str(status))
            print_extended_error(response)

        else:  # target not in supported list
            print('\tBootSourceOverrideTarget value "' + boottarget + '" is not supported.  Valid values are:')
            for tgt in system['Boot']['BootSourceOverrideSupported']:
                print('\t\t' + tgt)

        # point made...quit
        break

# noinspection PyPep8Naming
def ex7_find_iLO_MAC_address(host, iLO_loginname, iLO_password):

    print("EXAMPLE 7:  Find iLO's MAC Addresses")

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, manager, memberuri in collection(host, '/rest/v1/Managers', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(manager) == 'Manager.0' or get_type(manager) == 'Manager.1')

        # for each system in the systems collection at /rest/v1/Systems
        for status, headers, nic, memberuri in collection(host, manager['links']['EthernetNICs']['href'], None, iLO_loginname, iLO_password):

            # verify expected type
            # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
            assert(get_type(nic) == 'EthernetNetworkInterface.0' or get_type(nic) == 'EthernetNetworkInterface.1')

            if 'MacAddress' not in nic:
                print('\tNIC resource does not contain "MacAddress" property')
            else:
                print('\t' + manager['Model'] + ' ' + nic['Name'] + ' = ' + nic['MacAddress'] + '\t(' + nic['Status']['State'] + ')')

# noinspection PyPep8Naming
def ex8_add_iLO_user_account(host, iLO_loginname, iLO_password, new_iLO_loginname, new_iLO_username, new_iLO_password, irc=False, cfg=False, vm=False, usercfg=False, vpr=False):

    print('EXAMPLE 8:  Create an iLO User Account')

    # get the URI of the Accounts collection (not standardized)
    status, headers, obj = rest_get(host, '/rest/v1/AccountService', None, iLO_loginname, iLO_password)
    assert(status == 200)
    account_collection = obj['links']['Accounts']['href']

    # build up a new account object to create
    # iLO has two user account properties:
    #     Login name = the string used as the user identity to log in - we use this for 'UserName'
    #     User name = the friendly (or full) name of the user
    #     Potentially easy to reverse, so be careful - use the iLO account login name as 'UserName' in the API
    user = {'UserName': new_iLO_loginname, 'Password': new_iLO_password, 'Oem': {}}

    # Supply the full name as LoginName
    user['Oem']['Hp'] = {}
    user['Oem']['Hp']['LoginName'] = new_iLO_username # again this is tricky:  LoginName gets the friendly user name

    # plug in the requested privileges, by default you get LoginPriv and nothing else
    user['Oem']['Hp']['Privileges'] = {}
    user['Oem']['Hp']['Privileges']['RemoteConsolePriv'] = irc
    user['Oem']['Hp']['Privileges']['iLOConfigPriv'] = cfg
    user['Oem']['Hp']['Privileges']['VirtualMediaPriv'] = vm
    user['Oem']['Hp']['Privileges']['UserConfigPriv'] = usercfg
    user['Oem']['Hp']['Privileges']['VirtualPowerAndResetPriv'] = vpr

    # create the account
    print('POST ' + json.dumps(user) + ' to ' + account_collection)
    status, headers, response = rest_post(host, account_collection, None, user, iLO_loginname, iLO_password)
    print('POST response = ' + str(status))
    print_extended_error(response)

    if status == 201:
        # this is the new account URI
        new_account_uri = headers['location']  # HTTP headers are not case sensitive
        print('Account ' + new_account_uri + ' created')

        # get the new account resource
        # it is possible that a future version of iLO will simply return the new account resource in the create response
        status, headers, acct = rest_get(host, urlparse(new_account_uri).path, None, iLO_loginname, iLO_password)
        assert(status == 200)
        #print('Account info:  ' + json.dumps(acct, indent=4))

        # demonstration of how to remove the account using the Location header
        #status, headers, response = rest_delete(host, urlparse(new_account_uri).path, None, iLO_loginname, iLO_password)
        #assert(status == 200)
        #print('Account ' + new_account_uri + ' removed')

# noinspection PyPep8Naming
def ex9_modify_iLO_user_account(host, iLO_loginname, iLO_password, iLO_login_name_to_modify, new_loginname=None, new_username=None, new_password=None, irc=None, cfg=None, vm=None, usercfg=None, vpr=None):

    print('EXAMPLE 9:  Modify an iLO user account')

    # get the URI of the Accounts collection (not standardized)
    status, headers, obj = rest_get(host, '/rest/v1/AccountService', None, iLO_loginname, iLO_password)
    assert(status == 200)
    account_collection = obj['links']['Accounts']['href']

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, account, memberuri in collection(host, account_collection, None, iLO_loginname, iLO_password):
        # iLO has two user account properties:
        #     Login name = the string used as the user identity to log in - we use this for 'UserName'
        #     User name = the friendly (or full) name of the user
        #     Potentially easy to reverse, so be careful - use the iLO account login name as 'UserName' in the API
        if account['UserName'] == iLO_login_name_to_modify:
            # Cannot read/modify/write same object because iLO will reject non-PATCHable properties
            # i.e. if I just change 'iLO_password' and PATCH back I get an error identifying 'Description' as non-PATCHable

            # this resource handler is a little picky about passing in empty objects, so only add what we need by
            # assembling what's actually used.
            mod_user = {}
            mod_user_oemhp = {}
            mod_user_oemhp_privs = {}

            # if new loginname or password specified
            if new_password: mod_user['Password'] = new_password
            if new_loginname: mod_user['UserName'] = new_loginname

            # if different username specified
            if new_username: mod_user_oemhp['LoginName'] = new_username

            # if different privileges were requested (None = no change)
            if irc != None: mod_user_oemhp_privs['RemoteConsolePriv'] = irc
            if vm != None: mod_user_oemhp_privs['VirtualMediaPriv'] = vm
            if cfg != None: mod_user_oemhp_privs['iLOConfigPriv'] = cfg
            if usercfg != None: mod_user_oemhp_privs['UserConfigPriv'] = usercfg
            if vpr != None: mod_user_oemhp_privs['VirtualPowerAndResetPriv'] = vpr

            # component assembly
            if len(mod_user_oemhp_privs):
                mod_user_oemhp['Privileges'] = mod_user_oemhp_privs
            if len(mod_user_oemhp):
                mod_user['Oem'] = {'Hp': mod_user_oemhp}

            # patch the account
            status, headers, response = rest_patch(host, memberuri, None, mod_user, iLO_loginname, iLO_password)
            # Warning, if you don't change anything, you will get an HTTP 400 back
            #assert(status == 200)
            if status == 200:
                print('Account ' + memberuri + ' account modified')
            else:
                print('Account ' + memberuri + ' account not modified.  HTTP Status = ' + str(status))
            print_extended_error(response)
            return

    print('Account not found')

# noinspection PyPep8Naming
def ex10_remove_iLO_account(host, iLO_loginname, iLO_password, iLO_loginname_to_remove):

    print('EXAMPLE 10:  Remove an iLO account')

    # get the URI of the Accounts collection (not standardized)
    status, headers, obj = rest_get(host, '/rest/v1/AccountService', None, iLO_loginname, iLO_password)
    assert(status == 200)
    account_collection = obj['links']['Accounts']['href']

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, account, memberuri in collection(host, account_collection, None, iLO_loginname, iLO_password):
        # iLO has two user account properties:
        #     Login name = the string used as the user identity to log in - we use this for 'UserName'
        #     User name = the friendly (or full) name of the user
        #     Potentially easy to reverse, so be careful - use the iLO account login name as 'UserName' in the API
        if account['UserName'] == iLO_loginname_to_remove:

            # demonstration of how to remove the account
            status, headers, response = rest_delete(host, memberuri, None, iLO_loginname, iLO_password)
            print_extended_error(response)
            assert(status == 200)
            print('Account ' + memberuri + ' removed')
            return

    print('Account not found')

# noinspection PyPep8Naming
def ex11_dump_iLO_NIC(host, iLO_loginname, iLO_password):

    print('EXAMPLE 11:  Get iLO NIC state')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, manager, memberuri in collection(host, '/rest/v1/Managers', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(manager) == 'Manager.0' or get_type(manager) == 'Manager.1')

        # for each system in the systems collection at /rest/v1/Systems
        for status, headers, nic, memberuri in collection(host, manager['links']['EthernetNICs']['href'], None, iLO_loginname, iLO_password):

            # verify expected type
            # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
            assert(get_type(nic) == 'EthernetNetworkInterface.0' or get_type(nic) == 'EthernetNetworkInterface.1')
            if nic['Status']['State'] == 'Enabled':
                print('\t' + nic['Name'])
                if 'MacAddress' not in nic:
                    print('\tNo MacAddress information available (no "MacAddress" property in NIC resource)')
                else:
                    print('\tMAC: ' + str(nic['MacAddress']))
                print('\tSpeed: ' + str(nic['SpeedMbps']))
                print('\tAutosense:  ' + str(nic['Autosense']))
                print('\tFull Duplex:  ' + str(nic['FullDuplex']))
                if 'FQDN' not in nic:
                    print('\tNo FQDN information available')
                else:
                    print('\tFQDN:  ' + str(nic['FQDN']))
                for addr in nic['IPv4Addresses']:
                    print('\tIPv4 Address:  ' + addr['Address'] + ' from ' + addr['AddressOrigin'])
                if 'IPv6Addresses' not in nic:
                    print('\tIPv6Addresses information not available')
                else:
                    for addr in nic['IPv6Addresses']:
                        print('\tIPv6 Address:  ' + addr['Address'] + ' from ' + addr['AddressOrigin'])
                #print(json.dumps(nic, indent=4))

def ex12_sessions(host, iLO_loginname, iLO_password):

    print('EXAMPLE 12:  Create/Use/Delete a user session')

    # build up a new session object to create
    # iLO has two user account properties:
    #     Login name = the string used as the user identity to log in - we use this for 'UserName'
    #     User name = the friendly (or full) name of the user
    #     Potentially easy to reverse, so be careful - use the iLO account login name as 'UserName' in the API
    new_session = {"UserName": iLO_loginname, "Password": iLO_password}

    # create the session
    print('POST ' + json.dumps(new_session) + ' to /rest/v1/Sessions')
    status, headers, response = rest_post(host, '/rest/v1/Sessions', None, new_session, iLO_loginname, iLO_password)
    print('POST response = ' + str(status) + ', ' + str(response))
    assert(status == 201)

    # this is the new account URI
    session_uri = headers['location']   # iLO returns lower case header names, be careful of casing.  HTTP says headers are case insensitive.
    session_uri = urlparse(session_uri).path
    print('\tSession ' + session_uri + ' created')
    x_auth_token = headers['x-auth-token']

    # get the new session resource
    # This could be returned on the create operation instead of the ExtendedError created result
    # Instead of iLO_loginname/iLO_password here, use the newly supplied x_auth_token and the low level form of rest_op
    request_headers = {'X-Auth-Token': x_auth_token}
    status, headers, session = rest_op('GET', host, session_uri, request_headers, None, None, None, x_auth_token)
    assert(status == 200)
    assert(session['Oem']['Hp']['MySession'] == True)   # this flag is used for "whoami"
    #print('Session info:  ' + json.dumps(session, indent=4))
    print('\tLogged in from IP ' + session['Oem']['Hp']['UserIP'] + ' using session token ' + x_auth_token)

    # demonstration of how to log out
    status, headers, response = rest_delete(host, session_uri, None, iLO_loginname, iLO_password)
    assert(status == 200)
    print('\tSession ' + session_uri + ' logged out')

# noinspection PyPep8Naming
def ex13_set_uid_light(host, uid, iLO_loginname, iLO_password):

    print('EXAMPLE 13:  Set UID Light on or off')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, system, memberuri in collection(host, '/rest/v1/Systems', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(system) == 'ComputerSystem.0' or get_type(system) == 'ComputerSystem.1')

        # verify it supports POST
        assert(operation_allowed(headers, 'PATCH'))

        uid_state = dict()
        if uid:
            uid_state['IndicatorLED'] = 'Lit'
        else:
            uid_state['IndicatorLED'] = 'Off'

        # perform the POST action
        print('PATCH ' + json.dumps(uid_state) + ' to ' + memberuri)
        status, headers, response = rest_patch(host, memberuri, None, uid_state, iLO_loginname, iLO_password)
        print('PATCH response = ' + str(status))
        print_extended_error(response)
        assert(status < 300)

        # point made...quit
        break

# noinspection PyPep8Naming
def ex14_computer_details(host, iLO_loginname, iLO_password):

    print('EXAMPLE 14:  Dump host computer details')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, system, memberuri in collection(host, '/rest/v1/Systems', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(system) == 'ComputerSystem.0' or get_type(system) == 'ComputerSystem.1')

        # wrap these values in str() because some that are normally strings can also be null (None in Python)
        print('\tManufacturer:  ' + str(system['Manufacturer']))
        print('\tModel:  ' + str(system['Model']))
        print('\tSerial Number:  ' + str(system['SerialNumber']))
        if 'VirtualSerialNumber' in system:
            print('\tVirtual Serial Number:  ' + str(system['VirtualSerialNumber']))
        else:
            print('\tVirtual Serial Number information not available on system resource')
        print('\tUUID:  ' + str(system['UUID']))
        if 'VirtualUUID' in system['Oem']['Hp']:
            print('\tVirtualUUID:  ' + str(system['Oem']['Hp']['VirtualUUID']))
        else:
            print('\tVirtualUUID not available system resource')
        if 'AssetTag' in system:
            print('\tAsset Tag:  ' + system['AssetTag'])
        else:
            print('\tNo Asset Tag information on system resource')
        print('\tBIOS Version: ' + system['Bios']['Current']['VersionString'])
        print('\tMemory:  ' + str(system['Memory']['TotalSystemMemoryGB']) + ' GB')
        print('\tProcessors:  ' + str(system['Processors']['Count']) + ' x ' + str(system['Processors']['ProcessorFamily']))
        if 'Status' not in system or 'Health' not in system['Status']:
            print('\tStatus/Health information not available in system resource')
        else:
            print('\tHealth:  ' + str(system['Status']['Health']))

        # additional system properties
        try:
            print('\tPOST State:  ' + str(system['Oem']['Hp']['PostState']))
        except:
            pass
        try:
            print('\tIntelligent Provisioning Version:  ' + str(system['Oem']['Hp']['IntelligentProvisioningVersion']))
        except:
            pass

        if 'HostCorrelation' in system:
            if 'HostFQDN' in system['HostCorrelation']:
                print('\tHost FQDN:  ' + system['HostCorrelation']['HostFQDN'])
            if 'HostMACAddress' in system['HostCorrelation']:
                for mac in system['HostCorrelation']['HostMACAddress']:
                    print('\tHost MAC Address:  ' + str(mac))
            if 'HostName' in system['HostCorrelation']:
                print('\tHost Name:  ' + system['HostCorrelation']['HostName'])
            if 'IPAddress' in system['HostCorrelation']:
                for ip in system['HostCorrelation']['IPAddress']:
                    print('\tHost IP Address:  ' + str(ip))

        # dump DIMM Info
        print('\tDIMM Detail')
        try:
            for status, headers, dimm, memberuri in collection(host, system['Oem']['Hp']['links']['Memory']['href'], None, iLO_loginname, iLO_password):
                print('\t\tDIMM:')
                print('\t\t\tLocation:  ' + str(dimm['SocketLocator']))
                print('\t\t\tTechnology:  ' + str(dimm['DIMMTechnology']))
                print('\t\t\tType:  ' + str(dimm['HPMemoryType']))
                print('\t\t\tData Width:  ' + str(dimm['DataWidth']) + ', Total Width:  ' + str(dimm['TotalWidth']))
                print('\t\t\tError Correction:  ' + str(dimm['ErrorCorrection']))
                print('\t\t\tSize:  ' + str(dimm['SizeMB']) + ' MB')
        except KeyError:
            print('\tNo DIMM detail')

        # dump host network adapters (BaseNetworkAdapter)
        print('\tNetwork Adapters:')
        try:
            for status, headers, adapter, memberuri in collection(host, system['Oem']['Hp']['links']['NetworkAdapters']['href'], None, iLO_loginname, iLO_password):
                if status == 200:
                    try:
                        print('\t\tNetwork Adapter')
                        print('\t\t\tName:  ' + adapter['Name'])
                        print('\t\t\tStructured Name:  ' + str(adapter['StructuredName']))
                        print('\t\t\tPart Number:  ' + str(adapter['PartNumber']))
                        print('\t\t\tFirmware Version:  ' + str(adapter['Firmware']['Current']['VersionString']))
                        print('\t\t\tState:  ' + str(adapter['Status']['State']))
                        print('\t\t\tHealth:  ' + str(adapter['Status']['Health']))
                        for port in adapter['PhysicalPorts']:
                            print('\t\t\tPort')
                            print('\t\t\t\tName:  ' + port['Name'])
                            print('\t\t\t\tStructured Name:  ' + str(port['Oem']['Hp']['StructuredName']))
                            print('\t\t\t\tMAC Address:  ' + str(port['MacAddress']))

                            print('\t\t\t\tState:  ' + str(port['Status']['State']))
                            if port['Status']['State'] != 'Disabled':
                                print('\t\t\t\tHealth:  ' + str(port['Status']['Health']))
                                print('\t\t\t\tFull Duplex:  ' + str(port['FullDuplex']))
                                print('\t\t\t\tSpeed:  ' + str(port['SpeedMbps']) + ' Mbps')
                                for ipv4addr in port['IPv4Addresses']:
                                    print('\t\t\t\tIPv4 Address:  ' + str(ipv4addr['Address']))
                                for ipv6addr in port['IPv6Addresses']:
                                    print('\t\t\t\tIPv6 Address:  ' + str(ipv6addr['Address']))
                                print('\t\t\t\tTeam:  ' + str(port['Oem']['Hp']['Team']) + ' (valid only if AMS is running.)')
                                print('\t\t\t\tGood Transmits:  ' + str(port['Oem']['Hp']['GoodTransmits']) + ' (valid only if AMS is running.)')
                                print('\t\t\t\tBad Transmits:  ' + str(port['Oem']['Hp']['BadTransmits']) + ' (valid only if AMS is running.)')
                                print('\t\t\t\tGood Receives:  ' + str(port['Oem']['Hp']['GoodReceives']) + ' (valid only if AMS is running.)')
                                print('\t\t\t\tBad Receives:  ' + str(port['Oem']['Hp']['BadReceives']) + ' (valid only if AMS is running.)')
                    except:
                        pass
        except KeyError:
            print('\tNo network adapter information')

        # HP Smart Storage info
        print('\tHP Smart Storage:')
        try:
            status, headers, smartstorage = rest_get(host, system['Oem']['Hp']['links']['SmartStorage']['href'], None, iLO_loginname, iLO_password)
            print('\t\tHealth:  ' + str(smartstorage['Status']['Health']))
            for status, headers, adapter, memberuri in collection(host, smartstorage['links']['ArrayControllers']['href'], None, iLO_loginname, iLO_password):
                print('\t\tArray Controller:')
                print('\t\t\tModel:  ' + str(adapter['Model']))
                print('\t\t\tSerial Number:  ' + str(adapter['SerialNumber']))
                print('\t\t\tState:  ' + str(adapter['Status']['State']))
                print('\t\t\tHealth:  ' + str(adapter['Status']['Health']))
                print('\t\t\tLocation:  ' + str(adapter['Location']))
                print('\t\t\tFirmware Version:  ' + str(adapter['FirmwareVersion']['Current']['VersionString']))

                for status, headers, enclosure, memberuri in collection(host, adapter['links']['StorageEnclosures']['href'], None, iLO_loginname, iLO_password):
                    print('\t\t\tEnclosure:')
                    print('\t\t\t\tModel:  ' + str(enclosure['Model']))
                    print('\t\t\t\tSerial Number:  ' + str(enclosure['SerialNumber']))
                    print('\t\t\t\tDrive Bay Count:  ' + str(enclosure['DriveBayCount']))
                    print('\t\t\t\tState:  ' + str(enclosure['Status']['State']))
                    print('\t\t\t\tHealth:  ' + str(enclosure['Status']['Health']))
                    print('\t\t\t\tLocation:  ' + str(enclosure['Location']) + ' (' + str(enclosure['LocationFormat']) + ')')
                    print('\t\t\t\tFirmware Version:  ' + str(enclosure['FirmwareVersion']['Current']['VersionString']))

                for status, headers, drive, memberuri in collection(host, adapter['links']['PhysicalDrives']['href'], None, iLO_loginname, iLO_password):
                    print('\t\t\tPhysical Drive:')
                    print('\t\t\t\tModel:  ' + str(drive['Model']))
                    print('\t\t\t\tSize:  ' + str(drive['CapacityMiB']) + ' Mib')
                    print('\t\t\t\tSerial Number:  ' + str(drive['SerialNumber']))
                    print('\t\t\t\tInterface:  ' + str(drive['InterfaceType']))
                    print('\t\t\t\tState:  ' + str(drive['Status']['State']))
                    print('\t\t\t\tHealth:  ' + str(drive['Status']['Health']))
                    print('\t\t\t\tLocation:  ' + str(drive['Location']) + ' (' + str(drive['LocationFormat']) + ')')
                    print('\t\t\t\tFirmware Version:  ' + str(drive['FirmwareVersion']['Current']['VersionString']))

                for status, headers, drive, memberuri in collection(host, adapter['links']['LogicalDrives']['href'], None, iLO_loginname, iLO_password):
                    print('\t\t\tLogical Drive:')
                    print('\t\t\t\tSize:  ' + str(drive['CapacityMiB']) + ' Mib')
                    print('\t\t\t\tRAID:  ' + str(drive['Raid']))
                    print('\t\t\t\tState:  ' + str(drive['Status']['State']))
                    print('\t\t\t\tHealth:  ' + str(drive['Status']['Health']))

            #for status, headers, adapter, memberuri in collection(host, smartstorage['links']['HostBusAdapters']['href'], None, iLO_loginname, iLO_password):
            #    print(adapter)

        except KeyError:
            print('\tNo HP Smart Storage information')

        # point made...quit
        break

# Mount an ISO to virtual media and optionally specify whether it should be the boot target for the next server reset.
# if iso_url is left out, it unmounts
# if boot_on_next_server_reset is left out the option is not set one way or the other
# noinspection PyPep8Naming
def ex15_mount_virtual_media_dvd_iso(host, iLO_loginname, iLO_password, iso_url = None, boot_on_next_server_reset = None):

    print('EXAMPLE 15:  Mount iLO Virtual Media DVD ISO from URL')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, manager, memberuri in collection(host, '/rest/v1/Managers', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(manager) == 'Manager.0' or get_type(manager) == 'Manager.1')

        if 'VirtualMedia' not in manager['links']:
            print('\tVirtualMedia not available in manager links')
            continue

        # for each system in the systems collection at /rest/v1/Systems
        for status, headers, vm, memberuri in collection(host, manager['links']['VirtualMedia']['href'], None, iLO_loginname, iLO_password):

            # verify expected type
            # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
            assert(get_type(vm) == 'VirtualMedia.0' or get_type(vm) == 'VirtualMedia.1')
            if 'DVD' in vm['MediaTypes']:

                mount = {'Image': iso_url}
                # only add this if we are mounting and user specified something to set
                if iso_url is not None and boot_on_next_server_reset is not None:
                    mount['Oem'] = {'Hp': {'BootOnNextServerReset': boot_on_next_server_reset}}

                # perform the patch
                print('PATCH ' + json.dumps(mount) + ' to ' + memberuri)
                status, headers, response = rest_patch(host, memberuri, None, mount, iLO_loginname, iLO_password)
                print('PATCH response = ' + str(status))
                print_extended_error(response)
                if status == 400:
                    #this will respond with 400 if the vm state is already in this state  assert(status < 300)
                    pass
                else:
                    assert(status < 300)

                # finished
                break
        break

# noinspection PyPep8Naming
def ex16_set_server_asset_tag(host, iLO_loginname, iLO_password, asset_tag):

    print('EXAMPLE 16:  Set Computer Asset Tag')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, system, memberuri in collection(host, '/rest/v1/Systems', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(system) == 'ComputerSystem.0' or get_type(system) == 'ComputerSystem.1')

        a = {'AssetTag': asset_tag}

        # perform the patch
        print('PATCH ' + json.dumps(a) + ' to ' + memberuri)
        status, headers, response = rest_patch(host, memberuri, None, a, iLO_loginname, iLO_password)
        print('PATCH response = ' + str(status))
        print_extended_error(response)
        assert(status < 300)

        # point made...quit
        break

# noinspection PyPep8Naming
def ex17_reset_iLO(host, iLO_loginname, iLO_password):

    print('EXAMPLE 17:  Reset iLO')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, manager, memberuri in collection(host, '/rest/v1/Managers', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(manager) == 'Manager.0' or get_type(manager) == 'Manager.1')

        action = {'Action': 'Reset'}

        # perform the POST
        print('POST ' + json.dumps(action) + ' to ' + memberuri)
        status, headers, response = rest_post(host, memberuri, None, action, iLO_loginname, iLO_password)
        print_extended_error(response)
        assert(status == 200)

        break

# noinspection PyPep8Naming
def ex18_get_iLO_NIC(host, iLO_loginname, iLO_password, get_active=True):

    print("EXAMPLE 18:  Get iLO's NIC configuration")

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, manager, memberuri in collection(host, '/rest/v1/Managers', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(manager) == 'Manager.0' or get_type(manager) == 'Manager.1')

        # for each system in the systems collection at /rest/v1/Systems
        for status, headers, nic, memberuri in collection(host, manager['links']['EthernetNICs']['href'], None, iLO_loginname, iLO_password):

            # verify expected type
            # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
            assert(get_type(nic) == 'EthernetNetworkInterface.0' or get_type(nic) == 'EthernetNetworkInterface.1')

            if get_active and nic['Status']['State'] == 'Enabled':
                # this is the active NIC
                return memberuri, nic
            elif get_active == False and nic['Status']['State'] == 'Disabled':
                # this is the inactive NIC
                return memberuri, nic

def ex19_set_active_iLO_nic(host, iLO_loginname, iLO_password, shared_nic=False):

    print("EXAMPLE 19:  Set the active iLO NIC")

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, manager, memberuri in collection(host, '/rest/v1/Managers', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(manager) == 'Manager.0' or get_type(manager) == 'Manager.1')

        selected_nic_uri = None

        # for each system in the systems collection at /rest/v1/Systems
        for status, headers, nic, memberuri in collection(host, manager['links']['EthernetNICs']['href'], None, iLO_loginname, iLO_password):

            # verify expected type
            # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
            assert(get_type(nic) == 'EthernetNetworkInterface.0' or get_type(nic) == 'EthernetNetworkInterface.1')

            # this is a little complex but we are just looking for the dedicated vs. shared NIC without
            # assuming the order or URIs in the NICs collection.
            try:
                if nic['Oem']['Hp']['SupportsFlexibleLOM'] == True and shared_nic == True:
                    # this is the shared NIC
                    selected_nic_uri = memberuri
                    break
            except KeyError:
                pass
            try:
                if nic['Oem']['Hp']['SupportsLOM'] == True and shared_nic == True:
                    # this is the shared NIC
                    selected_nic_uri = memberuri
                    break
            except KeyError:
                pass

            if not shared_nic:
                selected_nic_uri = memberuri
                break
            elif not selected_nic_uri:
                print('\tShared NIC is not supported')
                break

        # we should have found the desired NIC
        if selected_nic_uri:

            # build the request header
            request = {'Oem': {'Hp': {'NICEnabled': True}}}

            # perform the PATCH
            print('PATCH ' + json.dumps(request) + ' to ' + memberuri)
            status, headers, response = rest_patch(host, selected_nic_uri, None, request, iLO_loginname, iLO_password)
            print_extended_error(response)

            # this will require an iLO reset to take effect (see ex17_reset_iLO)

def ex20_dump_Integrated_Management_Log(host, iLO_loginname, iLO_password):

    print('EXAMPLE 20:  Dump Integrated Management Log')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, system, memberuri in collection(host, '/rest/v1/Systems', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(system) == 'ComputerSystem.0' or get_type(system) == 'ComputerSystem.1')

        if 'Logs' not in system['links']:
            print('\tLogs not available on system resource')
            return
        logsuri = system['links']['Logs']['href']
        for status, headers, log, memberuri in collection(host, logsuri, None, iLO_loginname, iLO_password):

            assert(get_type(log) == 'LogService.0' or get_type(log) == 'LogService.1')

            entries_collection_array = log['links']['Entries']
            for entries_collection in entries_collection_array:

                entries_collection_uri = entries_collection['href']
                for status, headers, log_entry, log_entry_uri in collection(host, entries_collection_uri, None, iLO_loginname, iLO_password):

                    print(log_entry['Severity'] + ': Class ' + str(log_entry['Oem']['Hp']['Class']) + ' / Code ' + str(log_entry['Oem']['Hp']['Code']) + ':\t' + log_entry['Message'])

        # example only - don't iterate all systems
        break

def ex21_dump_iLO_event_log(host, iLO_loginname, iLO_password):

    print('EXAMPLE 21:  Dump iLO Event Log')

    # for each manager in the managers collection at /rest/v1/Managers
    for status, headers, manager, memberuri in collection(host, '/rest/v1/Managers', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(manager) == 'Manager.0' or get_type(manager) == 'Manager.1')

        if 'Logs' not in manager['links']:
            print('\tLogs not available on manager resource')
            return
        logsuri = manager['links']['Logs']['href']
        for status, headers, log, memberuri in collection(host, logsuri, None, iLO_loginname, iLO_password):

            assert(get_type(log) == 'LogService.0' or get_type(log) == 'LogService.1')

            entries_collection_array = log['links']['Entries']
            for entries_collection in entries_collection_array:

                entries_collection_uri = entries_collection['href']
                for status, headers, log_entry, log_entry_uri in collection(host, entries_collection_uri, None, iLO_loginname, iLO_password):

                    print(log_entry['Message'])
                    #status, headers, response = rest_get(host, iml, None, iLO_loginname, iLO_password)

        # example only - don't iterate all managers
        break

def ex22_clear_Integrated_Management_Log(host, iLO_loginname, iLO_password):

    print('EXAMPLE 20:  Clear Integrated Management Log')

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, system, memberuri in collection(host, '/rest/v1/Systems', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(system) == 'ComputerSystem.0' or get_type(system) == 'ComputerSystem.1')

        if 'Logs' not in system['links']:
            print('\tLogs not available on system resource')
            return
        logsuri = system['links']['Logs']['href']
        for status, headers, log, memberuri in collection(host, logsuri, None, iLO_loginname, iLO_password):

            assert(get_type(log) == 'LogService.0' or get_type(log) == 'LogService.1')

            action = {'Action': 'ClearLog'}

            # perform the POST
            print('POST ' + json.dumps(action) + ' to ' + memberuri)
            status, headers, response = rest_post(host, memberuri, None, action, iLO_loginname, iLO_password)
            print_extended_error(response)
            assert(status == 200)

            break

        # example only - don't iterate all systems
        break

def ex23_clear_iLO_event_log(host, iLO_loginname, iLO_password):

    print('EXAMPLE 20:  Clear iLO Event Log')

    # for each manager in the managers collection at /rest/v1/Managers
    for status, headers, manager, memberuri in collection(host, '/rest/v1/Managers', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(manager) == 'Manager.0' or get_type(manager) == 'Manager.1')

        if 'Logs' not in manager['links']:
            print('\tLogs not available on manager resource')
            return
        logsuri = manager['links']['Logs']['href']
        for status, headers, log, memberuri in collection(host, logsuri, None, iLO_loginname, iLO_password):

            assert(get_type(log) == 'LogService.0' or get_type(log) == 'LogService.1')

            action = {'Action': 'ClearLog'}

            # perform the POST
            print('POST ' + json.dumps(action) + ' to ' + memberuri)
            status, headers, response = rest_post(host, memberuri, None, action, iLO_loginname, iLO_password)
            print_extended_error(response)
            assert(status == 200)

            break

        # example only - don't iterate all managers
        break

def ex24_configure_SNMP(host, iLO_loginname, iLO_password, snmp_mode, snmp_alerts):

    print("EXAMPLE 24:  Configure iLO SNMP Settings")

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, manager, memberuri in collection(host, '/rest/v1/Managers', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(manager) == 'Manager.0' or get_type(manager) == 'Manager.1')

        # get the Network Service resource
        status, headers, network_service = rest_get(host, manager['links']['NetworkService']['href'], None, iLO_loginname, iLO_password)
        assert(get_type(network_service) == 'ManagerNetworkService.0' or get_type(network_service) == 'ManagerNetworkService.1')

        # get the SNMP resource
        if 'SNMPService' not in network_service['links']:
            print('\tSNMPService not found in manager network service links')
            continue
            
        status, headers, snmp_service = rest_get(host, network_service['links']['SNMPService']['href'], None, iLO_loginname, iLO_password)
        assert(get_type(snmp_service) == 'SnmpService.0' or get_type(snmp_service) == 'SnmpService.1')

        config = {'Mode': snmp_mode, 'AlertsEnabled': snmp_alerts}

        # perform the POST
        print('PATCH ' + json.dumps(config) + ' to ' + network_service['links']['SNMPService']['href'])
        status, headers, response = rest_patch(host, network_service['links']['SNMPService']['href'], None, config, iLO_loginname, iLO_password)
        print_extended_error(response)
        assert(status == 200)


def ex25_get_schema(host, iLO_loginname, iLO_password, schema_prefix):

    # This could be augmented to return a specific language
    print("EXAMPLE 25:  Find and return schema " + schema_prefix)

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, schemaptr, memberuri in collection(host, '/rest/v1/Schemas', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(schemaptr) == 'SchemaFile.0' or get_type(schemaptr) == 'SchemaFile.1')

        if schemaptr['Schema'].startswith(schema_prefix):
            for location in schemaptr['Location']:
                # this is an extref rather than an href because the actual registries/schemas lie outside the data model
                extref_uri = location['Uri']['extref']
                status, headers, schema = rest_get(host, extref_uri, None, iLO_loginname, iLO_password)
                if status == 200:
                    print('\tFound ' + schema_prefix + ' at ' + extref_uri)
                    return extref_uri, schema
                else:
                    print('\t' + schema_prefix + ' not found at ' + extref_uri)
                    return None, None

    print('Schema ' + schema_prefix + ' not found.')

def ex26_get_registry(host, iLO_loginname, iLO_password, registry_prefix):

    # This could be augmented to return a specific language
    print("EXAMPLE 26:  Find and return registry " + registry_prefix)

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, registryptr, memberuri in collection(host, '/rest/v1/Registries', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(registryptr) == 'SchemaFile.0' or get_type(registryptr) == 'SchemaFile.1')

        if 'Schema' in registryptr and registryptr['Schema'].startswith(registry_prefix):
            for location in registryptr['Location']:
                # this is an extref rather than an href because the actual registries/schemas lie outside the data model
                extref_uri = location['Uri']['extref']
                status, headers, registry = rest_get(host, extref_uri, None, iLO_loginname, iLO_password)
                if status == 200:
                    print('\tFound ' + registry_prefix + ' at ' + extref_uri)
                    return extref_uri, registry
                else:
                    print('\t' + registry_prefix + ' not found at ' + extref_uri)
                    return None, None

    print('Registry ' + registry_prefix + ' not found.')
    return None, None

def ex27_set_iLO_timezone(host, olson_timezone, iLO_loginname, iLO_password):
    # this only works if iLO is NOT configured to take time settings from DHCP v4 or v6

    print("EXAMPLE 27:  Set iLO's Timezone")
    print("\tNOTE:  This only works if iLO is NOT configured to take time settings from DHCP v4 or v6")

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, manager, memberuri in collection(host, '/rest/v1/Managers', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(manager) == 'Manager.0' or get_type(manager) == 'Manager.1')

        # for each system in the systems collection at /rest/v1/Systems
        status, headers, datetime = rest_get(host, manager['Oem']['Hp']['links']['DateTimeService']['href'], None, iLO_loginname, iLO_password)

        # print current time zone
        print('\tCurrent iLO timezone:  ' + datetime['TimeZone']['Name'])

        # find time zone from list
        for tz in datetime['TimeZoneList']:
            if tz['Name'].startswith(olson_timezone):
                request = {'TimeZone': {'Index': tz['Index']}}
                print('PATCH ' + json.dumps(request) + ' to ' + manager['Oem']['Hp']['links']['DateTimeService']['href'])
                status, headers, response = rest_patch(host, manager['Oem']['Hp']['links']['DateTimeService']['href'], None, request, iLO_loginname, iLO_password)
                print_extended_error(response)
                if status == 200:
                    print('\tiLO TimeZone set to ' + tz['Name'])
                return

        print('\tTimeZone value not found')

def ex28_set_iLO_NTP_servers(host, ntp_servers, iLO_loginname, iLO_password):

    print("EXAMPLE 28:  Set iLO's NTP Servers")

    # for each system in the systems collection at /rest/v1/Systems
    for status, headers, manager, memberuri in collection(host, '/rest/v1/Managers', None, iLO_loginname, iLO_password):

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(manager) == 'Manager.0' or get_type(manager) == 'Manager.1')

        # for each system in the systems collection at /rest/v1/Systems
        status, headers, datetime = rest_get(host, manager['Oem']['Hp']['links']['DateTimeService']['href'], None, iLO_loginname, iLO_password)

        # print current time zone
        print('\tCurrent iLO Date/Time Settings:  ' + json.dumps(datetime['ConfigurationSettings']))
        print('\tCurrent iLO NTP Servers:  ' + json.dumps(datetime['NTPServers']))

        request = {'StaticNTPServers': ntp_servers}
        print('PATCH ' + json.dumps(request) + ' to ' + manager['Oem']['Hp']['links']['DateTimeService']['href'])
        status, headers, response = rest_patch(host, manager['Oem']['Hp']['links']['DateTimeService']['href'], None, request, iLO_loginname, iLO_password)
        print_extended_error(response)
        print('\tChanges in pending settings require an iLO reset to become active.')

def ex29_get_PowerMetrics_Average(host, iLO_loginname, iLO_password):

    # https://<host>/rest/v1/Chassis/{item}/PowerMetrics#/PowerMetrics/AverageConsumedWatts
    print("EXAMPLE 29:  Report PowerMetrics Average Watts")

    # for each chassis in the chassis collection at /rest/v1/Chassis
    for status, headers, chassis, memberuri in collection(host, '/rest/v1/Chassis', None, iLO_loginname, iLO_password):
      # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(chassis) == 'Chassis.0' or get_type(chassis) == 'Chassis.1')

        # for each chassis in the chassis collection at /rest/v1/Chassis
        status, headers, pwrmetric = rest_get(host, chassis['links']['PowerMetrics']['href'], None, iLO_loginname, iLO_password)

        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(pwrmetric) == 'PowerMetrics.0' or get_type(pwrmetric) == 'PowerMetrics.1')

        if ('PowerMetrics' not in pwrmetric or
            'AverageConsumedWatts' not in pwrmetric['PowerMetrics'] or
            'IntervalInMin' not in pwrmetric['PowerMetrics']):
            print('\tPowerMetrics resource does not contain "AverageConsumedWatts" or "IntervalInMin" property')
        else:
            print('\t' + chassis['Model'] + ' AverageConsumedWatts = ' + str(pwrmetric['PowerMetrics']['AverageConsumedWatts']) + ' watts over a ' + str(pwrmetric['PowerMetrics']['IntervalInMin']) + ' minute moving average' )

def ex30_set_LicenseKey(host, iLO_loginname, iLO_password, iLO_Key):

    print("EXAMPLE 30:  Set iLO License Key")

    # for each manager in the manager collection at /rest/v1/Managers
    for status, headers, manager, memberuri in collection(host, '/rest/v1/Managers', None, iLO_loginname, iLO_password):
      # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
        assert(get_type(manager) == 'Manager.0' or get_type(manager) == 'Manager.1')

        # for each manager in the manager collection at /rest/v1/Manager
        if 'href' not in manager['Oem']['Hp']['links']['LicenseService']:
            print('\t"LicenseService" section in Manager/Oem/Hp does not exist')
            return
        license_uri = manager['Oem']['Hp']['links']['LicenseService']['href']
        for status, headers, licenseItem, memberuri in collection(host, license_uri, None, iLO_loginname, iLO_password):
            # verify expected type
            # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
            assert(get_type(licenseItem) == 'HpiLOLicense.0' or get_type(licenseItem) == 'HpiLOLicense.1')

            if ('LicenseKey' not in licenseItem):
                print('\tHpiLOLicense resource does not contain "LicenseKey" property')
            else:
                print('\tOld Key: "' + licenseItem['LicenseKey'] + '"' )

        key = dict()
        key['LicenseKey'] = iLO_Key

        # perform the POST action
        print('POST ' + json.dumps(key) + ' to ' + license_uri)
        status, headers, response = rest_post(host, license_uri, None, key, iLO_loginname, iLO_password)
        print('POST response = ' + str(status))
        print_extended_error(response)

        for status, headers, licenseItem, memberuri in collection(host, license_uri, None, iLO_loginname, iLO_password):
            # verify expected type
            # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
            assert(get_type(licenseItem) == 'HpiLOLicense.0' or get_type(licenseItem) == 'HpiLOLicense.1')

            if ('LicenseKey' not in licenseItem):
                print('\tHpiLOLicense resource does not contain "LicenseKey" property')
            else:
                print('\tNew Key: "' + licenseItem['LicenseKey'] + '"' )

#
# BIOS related RESTful APIs
#            
def ex31_set_bios_dhcp (host, iLO_loginname, iLO_password,IPSettings={},dhcpEnabled='Disabled'):
                         #Ipv4Address, Ipv4Gateway, Ipv4PrimaryDNS, Ipv4SecondaryDNS, Ipv4SubnetMask
    print("EXAMPLE: Set DHCP")
    bios_property = []
    value = []
    if IPSettings: #IPSettings isn't empty
        for key in IPSettings:
            bios_property.append(key)
            m = re.match(r"^(?:(1[0-9]{0,2}|2[0-4][0-9]|25[0-4]?|[0-9]{1,2})\.){3}(?:1[0-9]{0,2}|2[0-4][0-9]|25[0-4]?|[0-9]{1,2})$",IPSettings[key])
            if not m:
                print(key + ' format error. \"' + IPSettings[key] + '\" is not supported. Setting example terminated.')
                return
            value.append(IPSettings[key])
        dhcpEnabled = 'Disabled'
    if dhcpEnabled != 'Enabled' and dhcpEnabled != 'Disabled':
        print('Dhcpv4 format error. \"' + dhcpEnabled + '\" is not supported. Setting example terminated.')        
        return
    
    bios_property.append('Dhcpv4')
    value.append(dhcpEnabled)
    
    bios_patch_template(host, iLO_loginname, iLO_password, bios_property, value)
        
def ex32_set_bios_url_boot_file(host, iLO_loginname, iLO_password,url):
    print("EXAMPLE:  Set URL Boot File")
    bios_property = ['UrlBootFile']
    value = []
    m = re.match(r"^(ht|f)tp:\/\/[A-Za-z0-9]([-.\w]*[A-Za-z0-9])([A-Za-z0-9\-\.\?,'\/\\\+&;%\$#~=_]*)?(.iso|.efi)$", url)
    if m:
        value = [url]
    else:
        print('UrlBootFile format error. \"' + url + '\" is not supported. Setting example terminated.')
        return
    bios_patch_template(host, iLO_loginname, iLO_password, bios_property, value)

def ex33_set_bios_service(host, iLO_loginname, iLO_password, serviceSettings={}):
    print("EXAMPLE:  Set Service Number")
    bios_property = []
    value = []
    for key in serviceSettings:
        bios_property.append(key)
        value.append(serviceSettings[key])
    bios_patch_template(host, iLO_loginname, iLO_password, bios_property, value)
    
def ex34_set_bios_uefi_shell_startup(host, iLO_loginname, iLO_password,\
    UefiShellStartup='Enabled',UefiShellStartupLocation='Auto',UefiShellStartupUrl=''):
    print("EXAMPLE:  Set UEFI Shell Startup")
    bios_property = []
    value = []
    m = re.match(r"^(ht|f)tp:\/\/[A-Za-z0-9]([-.\w]*[A-Za-z0-9])([A-Za-z0-9\-\.\?,'\/\\\+&;%\$#~=_]*)?(.nsh)$", UefiShellStartupUrl)
    if m:
        bios_property.append('UefiShellStartup')
        value.append('Enabled')
        bios_property.append('UefiShellStartupLocation')
        value.append('NetworkLocation')
        bios_property.append('UefiShellStartupUrl')
        value.append(UefiShellStartupUrl)
    elif UefiShellStartupUrl == '' and UefiShellStartupLocation:
        bios_property.append('UefiShellStartup')
        value.append('Enabled')
        if UefiShellStartupLocation == 'AttachedMedia'\
        or UefiShellStartupLocation == 'NetworkLocation'\
        or UefiShellStartupLocation == 'Auto':
            bios_property.append('UefiShellStartupLocation')
            value.append(UefiShellStartupLocation)        
        else:
            print('UEFI Shell Startup Location format error. \"' + UefiShellStartupLocation + '\" is not supported. Setting example terminated.')
            return
        
    elif UefiShellStartup == 'Enabled' or UefiShellStartup == 'Disabled':
        bios_property.append('UefiShellStartup')
        value.append(UefiShellStartup)
    elif UefiShellStartupUrl != '':
        print('UEFI Shell Startup URI format error. \"' + UefiShellStartupUrl + '\" is not supported. Setting example terminated.')
        return
    else:
        print('UEFI Shell Startup format error. \"' + UefiShellStartup + '\" is not supported. Setting example terminated.')
        return
    bios_patch_template(host, iLO_loginname, iLO_password, bios_property, value)


def ex35_set_bios_iscsi(host, iLO_loginname, iLO_password, iscsi_attempt):

    # Find the iSCSI resource
    bios_settings = ex0_get_bios_resource(host, iLO_loginname, iLO_password)[0]
    iscsi_current = rest_get(host, bios_settings["links"]["iScsi"]["href"], None, iLO_loginname, iLO_password)[2]
    iscsi_uri = iscsi_current["links"]["Settings"]["href"]
    iscsi_settings = rest_get(host, iscsi_uri, None, iLO_loginname, iLO_password)[2]

    max_num_attempts = len(iscsi_settings["iSCSIBootSources"])
    desired_instance = iscsi_attempt.get("iSCSIBootAttemptInstance", 0)

    if desired_instance > max_num_attempts:
        print("Desired instance number {} is greater than maximum ({})".format(desired_instance, max_num_attempts))
        return -1

    # Find the array entry to change. Configured attempts are always pushed to
    # the front of the array, so that empty/default attempts never appear
    # before valid/configured attempts.
    available_instances = list(range(1, max_num_attempts + 1))
    array_index = 0
    for attempt in iscsi_settings["iSCSIBootSources"]:
        attempt_instance = attempt["iSCSIBootAttemptInstance"]
        if attempt_instance == desired_instance or attempt_instance == 0:
            break
        available_instances.remove(attempt_instance)
        array_index += 1

    if array_index >= max_num_attempts:
        assert(desired_instance == 0)
        assert(len(available_instances) == 0)
        print("All attempts are already configured. Can't add new one")
        return -1

    if desired_instance == 0:
        desired_instance = min(available_instances)
        iscsi_attempt["iSCSIBootAttemptInstance"] = desired_instance

    # Create settings object by overwriting existing settings with new ones
    patch_object = dict()
    patch_boot_sources = patch_object["iSCSIBootSources"] = list()
    for index in range(max_num_attempts):
        if index == array_index:
            patch_boot_sources.append(iscsi_attempt)
        else:
            patch_boot_sources.append(dict())

    response = rest_patch(host, iscsi_uri, None, patch_object, iLO_loginname, iLO_password)[2]
    print_extended_error(response)

    return desired_instance

# Run the tests

# commonly needed function values (typically would be passed in by argument)
host = 'hostname'
iLO_loginname = 'username'
iLO_password = 'password'
bios_password = None
iLO_Key = None

print('Tutorial Examples 0.9.13 BETA for HP RESTful API')
print('Copyright 2002-2014 Hewlett-Packard Development Company, L.P.')
print('For more information see www.hp.com/go/restfulapi')
print('Uncomment the ex* functions in the script file to see use case examples')

# comment this out to get to the test cases - we just don't want to start messing with any network endpoints
# without deliberate alteration to enable.
print('NOTE:  Remove the sys.exit call here to run the test cases.')
sys.exit(-1)

if False:
    ex1_change_bios_setting(host, ['AdminName'], ['Mr. Rest'], iLO_loginname, iLO_password, bios_password)
    ex2_reset_server(host, iLO_loginname, iLO_password)
    ex3_enable_secure_boot(host, False, iLO_loginname, iLO_password)
    ex4_bios_revert_default(host, iLO_loginname, iLO_password)
    ex5_change_boot_order(host, iLO_loginname, iLO_password, bios_password)
    ex5_1_boot_order_revert_default(host, iLO_loginname, iLO_password, bios_password)

if False:
    ex6_change_temporary_boot_order(host, 'Pxe', iLO_loginname, iLO_password)
    ex6_change_temporary_boot_order(host, 'Hdd', iLO_loginname, iLO_password)

if False:
    ex7_find_iLO_MAC_address(host, iLO_loginname, iLO_password)

# iLO User Account Modification
if False:
    # Create new account
    ex8_add_iLO_user_account(host, iLO_loginname, iLO_password, 'jjackson', 'John Jackson', 'newpassword', irc=True, cfg=True, vm=True, usercfg=True, vpr=True)
    # change login name, user name, and password
    ex9_modify_iLO_user_account(host, iLO_loginname, iLO_password, 'jjackson', new_loginname='jjohnson', new_username='Jack Johnson', new_password='adifferentpassword') # change user/pass info
    # Remove some privileges
    ex9_modify_iLO_user_account(host, iLO_loginname, iLO_password, 'jjohnson', irc=False, vm=False, usercfg=False)
    # Remove the account
    ex10_remove_iLO_account(host, iLO_loginname, iLO_password, 'jjohnson')

if False:
    ex11_dump_iLO_NIC(host, iLO_loginname, iLO_password)
    ex12_sessions(host, iLO_loginname, iLO_password)
    ex13_set_uid_light(host, True, iLO_loginname, iLO_password)  # light it up
    ex13_set_uid_light(host, False, iLO_loginname, iLO_password) # turn it off
    ex14_computer_details(host, iLO_loginname, iLO_password)

# virtual media
if False:
    # unmount (should fail with HTTP 400 of nothing is currently mounted)
    ex15_mount_virtual_media_dvd_iso(host, iLO_loginname, iLO_password)  # unmount
    # mount ISO - replace this with a valid URI to an ISO file
    iso_uri = 'http://someuri/dvdimg.iso'
    ex15_mount_virtual_media_dvd_iso(host, iLO_loginname, iLO_password, iso_uri, boot_on_next_server_reset = True) # mount
    # unmount again
    ex15_mount_virtual_media_dvd_iso(host, iLO_loginname, iLO_password)  # unmount

if False:
    ex16_set_server_asset_tag(host, iLO_loginname, iLO_password, 'SampleAssetTag')
    
if False:
    ex17_reset_iLO(host, iLO_loginname, iLO_password)

# Find iLO NIC (active/inactive, dedicated/shared)
if False:
    # find and return the uri and resource of the currently active iLO NIC
    nic_uri, content = ex18_get_iLO_NIC(host, iLO_loginname, iLO_password)
    print ('Active\t' + nic_uri + ": " + json.dumps(content))
    # set the Shared Network Port active
    ex19_set_active_iLO_nic(host, iLO_loginname, iLO_password, shared_nic=True)
    # set the Dedicated Network Port active
    ex19_set_active_iLO_nic(host, iLO_loginname, iLO_password, shared_nic=False)

# Log dump and clearing
if False:
    # dump both logs
    ex20_dump_Integrated_Management_Log(host, iLO_loginname, iLO_password)
    ex21_dump_iLO_event_log(host, iLO_loginname, iLO_password)
    # clear both logs
    ex22_clear_Integrated_Management_Log(host, iLO_loginname, iLO_password)
    ex23_clear_iLO_event_log(host, iLO_loginname, iLO_password)

# SNMP Configuration
if False:
    ex24_configure_SNMP(host, iLO_loginname, iLO_password, snmp_mode='Agentless', snmp_alerts=False)

# Get Schema
if False:
    # getting all the schema from iLO is pretty slow - this is an example of how to get one by name
    schema_uri, schema = ex25_get_schema(host, iLO_loginname, iLO_password, 'ComputerSystem')

if False:
    # Get the message registries (we could just iterate through but for convenience and clarity, we'll just grab 2 of them)
    # This is optional, but nice if you want to turn error structures into nice strings
    reguri, message_registries['Base'] = ex26_get_registry(host, iLO_loginname, iLO_password, 'Base')
    reguri, message_registries['iLO'] = ex26_get_registry(host, iLO_loginname, iLO_password, 'iLO')

# iLO TimeZone
if False:
    ex27_set_iLO_timezone(host, 'America/Chicago', iLO_loginname, iLO_password)

# iLO NTP Servers
if False:
    ex28_set_iLO_NTP_servers(host, ['192.168.0.1', '192.168.0.2'], iLO_loginname, iLO_password)
    
# Get average watts consumed.
if False:
    ex29_get_PowerMetrics_Average(host, iLO_loginname, iLO_password)    
    
# Install iLO LicenseKey
if False:
    ex30_set_LicenseKey(host, iLO_loginname, iLO_password, iLO_Key)
        
# Set bios DHCP setting.
if False:
    ex31_set_bios_dhcp (host, iLO_loginname, iLO_password, {'Ipv4Address':'192.168.0.1', 'Ipv4Gateway':'192.168.0.2','Ipv4PrimaryDNS':'192.168.0.3', 'Ipv4SecondaryDNS':'192.168.0.4', 'Ipv4SubnetMask':'192.168.0.5'})
    
# Set bios boot from URI.
if False:
    ex32_set_bios_url_boot_file (host, iLO_loginname, iLO_password, "http://hp.com/test.efi")
    
# Set service information.
if False:
    ex33_set_bios_service (host, iLO_loginname, iLO_password, {'ServiceName':'HP', 'ServiceEmail':'me@hp.com'})
    
# Set boot from UEFI shell startup URI.
if False:
    ex34_set_bios_uefi_shell_startup (host, iLO_loginname, iLO_password, "Enabled", "Auto", "http://hp.com/test.nsh")

if False:
    # For example, imagine we want to change the "attempt name" and iSCSI retry
    # settings for an existing configuration. Just make sure the "instance
    # number" corresponds to the existing boot attempt, and the example code
    # will take care of finding the correct resource object to patch.
    desired_iscsi_settings = {
        "iSCSIBootAttemptInstance": 2,
        "iSCSIBootAttemptName":     "Updated Attempt Name",
        "iSCSIConnectRetry":        5
        }
    instance = ex35_set_bios_iscsi(host, iLO_loginname, iLO_password, desired_iscsi_settings)
    assert(instance == 2)
    print("Updated iSCSI instance {}".format(instance))

    # If we want to configure a new iSCSI boot attempt, then we may omit the
    # "instance" number and the example code will find the next available
    # instance and return it, if possible. Any other settings not provided will
    # be kept at the default value.
    desired_iscsi_settings = {
        "iSCSIBootAttemptName":     "New Attempt Name",
        "iSCSIBootEnable":          "Enabled",
        "iSCSIBootLUN":             "1",
        "iSCSINicSource":           "NicBoot2",
        "iSCSITargetInfoViaDHCP":   False,
        "iSCSITargetIpAddress":     "10.10.10.128",
        "iSCSITargetName":          "iqn.2003-01.org.linux-iscsi.host:sn.abcdef",
        "iSCSITargetTcpPort":       3260
        }
    instance = ex35_set_bios_iscsi(host, iLO_loginname, iLO_password, desired_iscsi_settings)
    if instance != -1:
        print("Created new iSCSI attempt (instance {})".format(instance))
   
