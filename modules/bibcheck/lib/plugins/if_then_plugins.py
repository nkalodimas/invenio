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

""" Bibcheck plugin helper functions called by if-then plugin """

from invenio.bibrecord import *

def core_in_65017(record,*args):
	""" Checks whether the record contains one of the CORE subjects in 65017a """
	values = record_get_field_values(record,'650','1','7','a')
	for value in values:
		if value in ['Experiment-HEP', 'Lattice', 'Phenomenology-HEP', 'Theory-HEP']:
			return True
	return False

def core_should_exist(record):
	""" Checks whether the record contains a 980__a field with CORE value"""
	values = record_get_field_values(record,'980','_','_','a')
	if not 'CORE' in values:
		record.set_invalid("980__a field with value CORE should be added")