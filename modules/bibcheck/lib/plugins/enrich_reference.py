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

""" Bibcheck plugin to enrich referenced records """

from invenio.bibrecord import record_get_field_instances, field_get_subfield_instances, \
	field_get_subfield_values, field_get_subfield_codes, record_add_field
from invenio.search_engine import perform_request_search

def check_record(record):
	"""
	Checks whether the record contains a repnr and a journal pubnote and adds
	the pub info to the cited record if not yet existent
	"""
	for field_instance in record_get_field_instances(record,'999','C','5'):
		codes = field_get_subfield_codes(field_instance)
		if 'r' and 's' in codes and pub_info:
			referenced_record = retrieve_referenced_record(field_instance)
			if referenced_record:
				# TODO add publication info to the record
				referenced_record.addfield(record.get-pub-info)
			# subfields = field_get_subfield_instances(field_instance)
			# for code, value in subfields:
			# 	if dictionary.haskey(code):
			# 		if referenced_record.not_contains(dictionary[code]) and record.contains(code):
			# 			referenced_record.addfield(record[code])

def retrieve_referenced_record(field_instance):
	subfields = field_get_subfield_instances(field_instance)
	for code, value in subfields:
		if code == '0' and value:
			from invenio.search_engine import get_record
			record = get_record(value)
			if record:
				return record
	return None
