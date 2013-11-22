# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2013 CERN.
##
## Invenio is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
##
## Invenio is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Invenio; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

""" Bibcheck plugin to enforce the presence of a field in a subset of values """

from invenio.bibrecord import *
from invenio.bibcheck_plugins import subfield_in_db

def check_record(record, field_in_source):
    """
    Mark record as invalid if there is no field contained in the set of given values.
    The source of the values can be one of the next:
    A set of values : '980__a': {'SET' : ['HEP','Conference']}
    The values of a field in the db given also a collection : '980__a': {'DB' : ('700__a', 'HEP')}
    A Knowledge Base : '980__a': {'KB' : 'Subjects'}
    The source structure is a dictionary with one of the three possible type of pairs:
    'SET' : list of strings
    'DB' : (<field>, <collection>)
    'KB' : <KB name>
    """
    for field, source in field_in_source:
        if not field_exists_in_source(field, source):
            record.set_invalid("There should be at least one field %s in the set of %s" % (field, ' or '.join(set_of_fields)))

def field_exists_in_source(field, source):
    if len(source.items()) < 1:
        return False
    source_type, source_value = source.items()[0]
    if source_type == 'SET':
        for position, value in record.iterfield(field):
            if value in source_value:
                return True
        return False
    elif source_type == 'DB':
        field_to_search , collection = source_value
        values_in_db = subfield_in_db.get_values_of_field_in_db(field_to_search, collection)
        for position, value in record.iterfield(field):
            if value in values_in_db:
                return True
        return False
    elif source_type == 'KB':
        for position, value in record.iterfield(field):
            if get_kba_values(source_value, searchname=value, searchtype="e"):
                return True
        return False
    else:
        return False