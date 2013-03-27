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
BibCatalog unit tests
"""

import unittest
from invenio.testutils import make_test_suite, run_test_suite

from invenio.bibcatalog_utils import \
    load_tag_code_from_name, \
    split_tag_code, \
    record_get_value_with_provenence, \
    record_id_from_record, \
    record_in_collection, \
    BibCatalogTagNotFound
from invenio.bibformat_dblayer import get_all_name_tag_mappings


class TestUtilityFunctions(unittest.TestCase):
    """Test non-data-specific utility functions for BibCatalog."""

    def test_load_tag_code_from_name(self):
        """Tests function bibcatalog_utils.load_tag_code_from_name"""
        if 'record ID' in get_all_name_tag_mappings():
            self.assertEqual(load_tag_code_from_name("record ID"), "001")
        # Name "foo" should not exist and raise an exception
        self.assertRaises(BibCatalogTagNotFound, load_tag_code_from_name, "foo")

    def test_split_tag_code(self):
        """Tests function bibcatalog_utils.split_tag_code"""
        self.assertEqual()

    def test_load_tag_code_from_name(self):
        """Tests function bibcatalog_utils.load_tag_code_from_name"""
        pass

    def test_load_tag_code_from_name(self):
        """Tests function bibcatalog_utils.load_tag_code_from_name"""
        pass


TEST_SUITE = make_test_suite(TestUtilityFunctions)

if __name__ == "__main__":
    run_test_suite(TEST_SUITE)