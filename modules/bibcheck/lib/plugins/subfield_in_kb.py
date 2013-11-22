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

""" Bibcheck plugin to check the existence of a subfield's value in a Knowledge Base """

from invenio.bibknowledge import get_kba_values

def check_record(record, field_in_kb):
    """
    Mark record as invalid if a field's value is not contained in the specified KB
    e.g {'100__a': 'Subjects'}
    """
    for field, kb in field_in_kb.items():
        if '%' in field or len(field) is not 6:
            continue
        for position, value in record.iterfield(field):
            if not get_kba_values(kb, searchname=value, searchtype="e"):
                record.set_invalid("Field %s must exist in Knowledge Base %s" % (field, kb))