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

""" Bibcheck plugin to check the id consistency of references' fields """

from invenio.bibrecord import record_get_field_instances, \
	field_get_subfield_values, record_add_subfield_into
from invenio.bibcheck_plugins.ref_id_consistency import find_inspire_id_from_reference

def check_record(record):
	""" For every reference field, checks whether Inspire id misses and if all the related
	    subfields refer to the same Inspire Id it adds it to subfield 999C50
	"""
	for field_instance in record_get_field_instances(record,'999','C','5'):
		if not field_get_subfield_values(field_instance, '0'):
			recid_set = find_inspire_id_from_reference(field_instance)
			if len(recid_set) == 1:
				record_add_subfield_into(record, '999', '0', str(recid_set.pop()),subfield_position=0,
											field_position_global=field_instance[4])
				record.set_amended("Added Inspire id to reference")
