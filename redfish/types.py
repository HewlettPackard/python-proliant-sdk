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
Redfish Resource Types
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

LOG = logging.getLogger('redfish')


class Base(object):
    def __init__(self, obj, connection=None):
        self._conn = connection
        """handle to the redfish connection"""

        self._attrs = []
        """list of discovered attributes"""

        self._links = []
        """list of linked resources"""

        # parse the individual resources, appending them to
        # the list of object attributes
        for k in obj.keys():
            ref = k.lower()
            if ref in ["links", "oem", "items"]:
                continue
            setattr(self, ref, obj[k])
            self._attrs.append(ref)

        # make sure the required attributes are present
        if not getattr(self, 'name', False):
            raise ObjectLoadException(
                    "Failed to load object. Reason: could not determine name.")
        if not getattr(self, 'type', False):
            raise ObjectLoadException(
                    "Failed to load object. Reason: could not determine type.")

        if getattr(self, 'serviceversion', False):
            self.type = self.type.replace('.' + self.serviceversion, '')
        else:
            # TODO: use a regex here to strip and store the version
            # instead of assuming it is 7 chars long
            self.type = self.type[:-7]

        # Lastly, parse the 'links' resource.
        # Note that this may have different nested structure, depending on
        # what type of resource this is, or what vendor it is.
        # subclasses may follow this by parsing other resources / collections
        self._parse_links(obj)

    def _parse_links(self, obj):
        """Map linked resources to getter functions

        The root resource returns a dict of links to top-level resources
        """
        def getter(connection, href):
            def _get():
                return connection.rest_get(href, {})
            return _get

        for k in obj['links']:
            ref = "get_" + k.lower()
            self._links.append(ref)
            href = obj['links'][k]['href']
            setattr(self, ref, getter(self._conn, href))

    def __repr__(self):
        """Return this object's _attrs as a dict"""
        res = {}
        for a in self._attrs:
            res[a] = getattr(self, a)
        return res

    def __str__(self):
        """Return the string representation of this object's _attrs"""
        return json.dumps(self.__repr__())


class BaseCollection(Base):
    """Base class for collection types"""
    def __init__(self, obj, connection=None):
        super(BaseCollection, self).__init__(obj, connection=connection)
        self._parse_items(obj)
        self._attrs.append('items')

    def _parse_links(self, obj):
        """links are special on a chassis; dont parse them"""
        pass

    def _parse_items(self, obj):
        """Map linked items to getter methods

        The chassis resource returns a list of items and corresponding
        link data in a separate entity.
        """
        def getter(connection, href):
            def _get():
                return connection.rest_get(href, {})
            return _get

        self.items = []
        self._item_getters = []

        if 'links' in obj and 'Member' in obj['links']:
            # NOTE: this assumes the lists are ordered the same
            counter = 0
            for item in obj['links']['Member']:
                self.items.append(obj['Items'][counter])
                self._item_getters.append(
                        getter(self._conn, item['href']))
                counter+=1
        elif 'Items' in obj:
            # TODO: find an example of this format and make sure it works
            for item in obj['Items']:
                if 'links' in item and 'self' in item['links']:
                    href = item['links']['self']['href']
                    self.items.append(item)

        # TODO: implement paging support
        # if 'links' in obj and 'NextPage' in obj['links']:
        #    next_page = THIS_URI + '?page=' + str(obj['links']['NextPage']['page'])
        #    do something with next_page URI

    def __iter__(self):
        for getter in self._item_getters:
            yield getter()


class Root(Base):
    """Root '/' resource class"""
    def _parse_links(self, obj):
        """Map linked resources to getter functions

        The root resource returns a dict of links to top-level resources

        TODO: continue implementing customizations for top-level resources

        """
        mapping = {
                'Systems': Systems,
                'Chassis': Chassis,
                'Managers': Base,
                'Schemas': Base,
                'Registries': Base,
                'Tasks': Base,
                'AccountService': Base,
                'Sessions': Base,
                'EventService': Base,
                }

        def getter(connection, href, type):
            def _get():
                return mapping[type](connection.rest_get(href, {}), self._conn)
            return _get

        for k in obj['links']:
            ref = "get_" + k.lower()
            self._links.append(ref)
            href = obj['links'][k]['href']
            setattr(self, ref, getter(self._conn, href, k))


class Chassis(BaseCollection):
    """Chassis resource class"""
    def __len__(self):
        return len(self.items)


class Systems(Base):
    pass
