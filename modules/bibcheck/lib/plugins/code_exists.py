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

""" Bibcheck plugin to enforce mandatory subfields """

from invenio.bibrecord import *

def check_record(record, code_in_fields):
    """
    Mark record as invalid if a field doesn't contain the specified code
    e.g {'100__': 'a'}
    """
    for field, code in code_in_fields.items():
        for field_instance in record_get_field_instances(record,'100','_','_'):
            found = False
            subfields = field_get_subfield_instances(field_instance)
            for subfield in subfields:
                if subfield[0] is code and subfield[1]:
                    found = True
                    break
            if not found:
                record.set_invalid("Field %s must contain a subfield with code %s" % (field, code))