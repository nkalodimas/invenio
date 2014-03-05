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

""" Bibcheck plugin to enforce mandatory fields """

def check_record(record, fields=None, sets_of_fields=None):
    """
    Mark record as invalid if it doesn't contain all the specified fields
    or if it doesn't contain at least one field of the specified fieldset
    """
    if fields is None:
    	fields = list()
    if sets_of_fields is None:
    	sets_of_fields = list()
    for field in fields:
        if len(list(record.iterfield(field))) == 0:
            record.set_invalid("Missing mandatory field %s" % field)
	for set_of_fields in sets_of_fields:
		found = False
		for field in set_of_fields:
			if len(list(record.iterfield(field))) != 0:
				found = True
				break
		if not found:
			record.set_invalid("Missing all fields from mandatory set of fields %s" % ' or '.join(set_of_fields))
