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

""" Bibcheck plugin to check the existence of a subfield's value in the database """

from invenio.bibrecord import record_get_field_values
from invenio.search_engine import perform_request_search, get_fieldvalues
def check_record(record, field_in_db):
    """
    Mark record as invalid if a field's value is not contained in the database
    e.g {'773__p': ('711__a', 'Journals')}
    """
    for field, field_in_collection in field_in_db.items():
        if '%' in field or len(field) is not 6:
            continue
        # values_of_field = record_get_field_values(record,field[:3],field[3],field[4],field[5])
        field_to_search , collection = field_in_collection
        values_in_db = get_values_of_field_in_db(field_to_search, collection)
        for position, value in record.iterfield(field):
        # for value in values_of_field:
            if value not in values_in_db:
                record.set_invalid("Field's %s value does not match a %s in the %s database" % (field, field_to_search, collection))
                break

def get_values_of_field_in_db( field, collection):
    results = []
    pattern = "%s:/.*/" % field
    # find records that contain a field like field_to_search
    rec_ids = perform_request_search(p=pattern, of="intbitset", cc=collection)
    if rec_ids:
        # get the value of the field from every found record
        for rec in rec_ids:
            results.extend(get_fieldvalues(rec, field))
    return results
