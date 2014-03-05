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

""" Bibcheck plugin to ensure that certain pairs of fields exist """

def check_record(record, pairs_of_fields):
    """
    If key field exists in the record the value field must also exist
    e.g {'242': '041'}
    """
    for key_field, value_field in pairs_of_fields.items():
        if len(list(record.iterfield(key_field))) and not len(list(record.iterfield(value_field))):
            record.set_invalid("Field %s exists, but field %s doesn't" % (key_field, value_field))