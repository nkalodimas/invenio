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

""" Bibcheck plugin which applies plugin functions when the given condition is true"""

def check_record(record, if_func, then_func, if_func_args={}, then_func_args={} ):
	""" If if_func returns true then then_func is called """

	from invenio.bibcheck_plugins import if_then_plugins

	if_func = getattr(if_then_plugins,if_func)
	then_func = getattr(if_then_plugins,then_func)
	result = if_func(record, **if_func_args)
	if result:
		then_func(record, **then_func_args)
