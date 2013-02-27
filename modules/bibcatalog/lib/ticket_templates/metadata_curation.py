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

"""
BibCatalog template
"""
from invenio.bibrecord import record_get_field_instances, \
                              field_get_subfield_values


def check_record(record):
    """ Expects a record object """
    return _is_core_record(record)


def process_ticket(record):
    return "Ticket body"


def _is_core_record(record):
    """
    Returns True/False if given record is a core record.
    """
    for collection_tag in record_get_field_instances(record, "980"):
        for collection in field_get_subfield_values(collection_tag, 'a'):
            if collection.lower() == "core":
                return True
    return False
