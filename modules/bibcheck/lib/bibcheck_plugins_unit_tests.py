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


"""BibTask default plugins Test Suite."""

__revision__ = "$Id$"

import unittest
from invenio.testutils import make_test_suite, run_test_suite
from invenio.bibcheck_plugins import mandatory, \
    trailing_space, \
    regexp, \
    utf8, \
    enum, \
    dates, \
    texkey, \
    url, \
    code_exists, \
    enrich_reference, \
    field_in_subset, \
    if_then, \
    mutual_existing_fields, \
    ref_id_consistency, \
    add_recid_to_ref, \
    subfield_in_db, \
    subfield_in_kb
from invenio.bibcheck_task import AmendableRecord

MOCK_RECORD = {
    '001': [([], ' ', ' ', '1', 7)],
    '005': [([], ' ', ' ', '20130621172205.0', 7)],
    '024': [([('a', 'Foo'),('2', '')], '7', ' ', '', 7)], # Code exists(no 0247 without $$2)
    '041': [([('a', 'German')], ' ', ' ', '', 7)], # Mutual existing fields
    '100': [([('a', 'Photolab '),('c', '')], ' ', ' ', '', 7)], # Trailing spaces, mandatory
    '242': [([('a', 'A random german title')], ' ', ' ', '', 7)], # Mutual existing fields
    '260': [([('c', '2000-06-14')], ' ', ' ', '', 7)],
    '261': [([('c', '14 Jun 2000')], ' ', ' ', '', 7)],
    '262': [([('c', '14 06 00')], ' ', ' ', '', 7)],
    '263': [([('c', '2000 06 14')], ' ', ' ', '', 7)],
    '264': [([('c', '1750 06 14')], ' ', ' ', '', 7)],
    '265': [([('c', '2100 06 14')], ' ', ' ', '', 7)],
    '340': [([('a', 'FI\xc3\x28LM')], ' ', ' ', '', 7)], # Invalid utf-8
    '595': [([('a', ' Press')], ' ', ' ', '', 7)], # Leading spaces
    '650': [([('a', 'Experiment-HEP')], '1', '7', '', 7)], # If then(core_in_65017), subfield_in_kb
    '653': [([('a', 'LEP')], '1', ' ', '', 7)],
    '773': [([('w', 'C13-07-15.8')], ' ', ' ', '', 7)], # Subfield in db
    '774': [([('w', 'C19-07-15.8')], ' ', ' ', '', 7)], # Subfield not in db
    '856': [([('f', 'neil.calder@cern.ch')], '0', ' ', '', 7)],
    '980': [([('a', 'HEP')], ' ', ' ', '', 7)], # field_in_subset
    '994': [([('u', 'http://httpstat.us/200')], '4', ' ', '', 7)], # Url that works
    '995': [([('u', 'www.google.com/favicon.ico')], '4', ' ', '', 7)],  # url without protocol
    '996': [([('u', 'httpstat.us/301')], '4', ' ', '', 7)],   # redirection without protocol
    '997': [([('u', 'http://httpstat.us/404')], '4', ' ', '', 7)], # Error 404
    '998': [([('u', 'http://httpstat.us/500')], '4', ' ', '', 7)], # Error 500
    '999': [([('u', 'http://httpstat.us/301')], '4', ' ', '', 7), # Permanent redirect
            ([('a', '10.1007/978-3-642-25947-0'),('i', '978-3-642-25946-3'),('s', 'Lect.Notes Phys.'),('0','11153722')], 'C', '5', '', 8), # Reference id consistency
            ([('a', '10.1007/978-3-642-25947-0'),('i', '978-3-642-25946-3'),('s', 'Lect.Notes Phys.')], 'C', '5', '', 9)] # Add recid to reference
}

RULE_MOCK = {
    "name": "test_rule",
    "holdingpen": True
}

class BibCheckPluginsTest(unittest.TestCase):
    """ Bibcheck default plugins test """

    def assertAmends(self, test, changes, **kwargs):
        """
        Assert that the plugin "test" amends the mock record when called with
        params kwargs.
        """
        record = AmendableRecord(MOCK_RECORD)
        record.set_rule(RULE_MOCK)
        test.check_record(record, **kwargs)
        self.assertTrue(record.amended)
        self.assertEqual(len(record.amendments), len(changes))
        for field, val in changes.iteritems():
            if val is not None:
                self.assertEqual(
                    [((field, 0, 0), val)],
                    list(record.iterfield(field))
                )
            else:
                self.assertEqual(len(list(record.iterfield(field))), 1)

    def assertFails(self, test, **kwargs):
        """
        Assert that the plugin test marks the record as invalid when called with
        params kwargs.
        """
        record = AmendableRecord(MOCK_RECORD)
        record.set_rule(RULE_MOCK)
        test.check_record(record, **kwargs)
        self.assertFalse(record.valid)
        self.assertTrue(len(record.errors) > 0)

    def assertOk(self, test, **kwargs):
        """
        Assert that the plugin test doesn't make any modification to the record
        when called with params kwargs.
        """
        record = AmendableRecord(MOCK_RECORD)
        record.set_rule(RULE_MOCK)
        test.check_record(record, **kwargs)
        self.assertTrue(record.valid)
        self.assertFalse(record.amended)
        self.assertEqual(len(record.amendments), 0)
        self.assertEqual(len(record.errors), 0)

    def test_mandatory(self):
        """ Mandatory fields plugin test """
        self.assertOk(mandatory, fields=["100%%a", "260%%c"], sets_of_fields= [["100__a", "110__a", "710__a"], ["260__c", "269__c", "773__y", "502__c"]])
        self.assertFails(mandatory, fields=["100%%b"])
        self.assertFails(mandatory, fields=["111%%%"])
        self.assertFails(mandatory, fields=[], sets_of_fields=[["100__b", "110__a", "710__a"], ["260__d", "269__c", "773__y", "502__c"]] )

    def test_trailing_space(self):
        """ Trailing space plugin test """
        self.assertAmends(trailing_space, {"100__a": "Photolab"}, fields=["100%%a"])
        self.assertAmends(trailing_space, {"100__a": "Photolab"}, fields=["595%%a", "100%%a"])
        self.assertOk(trailing_space, fields=["653%%a"])

    def test_regexp(self):
        """ Regexp plugin test """
        self.assertOk(regexp, regexps={
            "856%%f": "[^@]+@[^@]+$",
            "260%%c": r"\d{4}-\d\d-\d\d$"
        })
        self.assertFails(regexp, regexps={
            "340%%a": "foobar"
        })

    def test_utf8(self):
        """ Valid utf-8 plugin test """
        self.assertFails(utf8, fields=["%%%%%%"])
        self.assertOk(utf8, fields=["856%%%"])

    def test_enum(self):
        """ Enum plugin test """
        self.assertFails(enum, allowed_values={"100__a": ["Pepe", "Juan"]})
        self.assertOk(enum, allowed_values={"6531_a": ["LEP", "Other"]})

    def test_date(self):
        """ Date plugin test """
        self.assertOk(dates, fields=["260__c"])
        self.assertAmends(dates, {"261__c": "2000-06-14"}, fields=["261__c"])
        self.assertAmends(dates, {"262__c": "2000-06-14"}, fields=["262__c"])
        self.assertAmends(dates, {"263__c": "2000-06-14"}, fields=["263__c"])
        self.assertFails(dates, fields=["264__c"]) # Date in the far past
        self.assertFails(dates, fields=["265__c"], allow_future=False) # Date in the future
        self.assertFails(dates, fields=["100__a"]) # Invalid date

    def test_texkey(self):
        """ TexKey plugin test """
        self.assertAmends(texkey, {"035__a": None})

    def test_code_exists(self):
        """ Code exists plugin test """
        self.assertOk( code_exists, code_in_fields={"0247_" : "a"}) # Code exists
        self.assertFails( code_exists, code_in_fields={"0247_" : "2"}) # Missing code

    def test_subfield_in_db(self):
        """ Subfield value exists in db plugin test """
        self.assertOk( subfield_in_db, field_in_db = { "773__w" : ( "111__g", "Conferences" )} )
        self.assertFails( subfield_in_db, field_in_db = { "774__w" : ( "111__g", "Conferences" )} ) # Value should not exist

    def test_subfield_in_kb(self):
        """ Subfield value exists in kb plugin test """
        self.assertOk( subfield_in_kb, field_in_kb = { "65017a" : "SUBJECT" } )
        self.assertFails( subfield_in_kb, field_in_kb = { "65017a" : "JOURNALS" } ) # Value should not exist
        self.assertFails( subfield_in_kb, field_in_kb = { "65017a" : "Unknown" } ) # Knowledge Base that does not exist

    def test_field_in_subset(self):
        """ Field exists in subset plugin test """
        self.assertOk( field_in_subset, field_in_source = { "980__a" : { 'SET' : ['HEP','Conferences', 'CORE'] } } )
        self.assertFails( field_in_subset, field_in_source = { "980__a" : { 'SET' : ['Jobs'] } } )
        # TODO add cases for DB,KB

    def test_mutual_existing_fields(self):
        """ Mutual existing fields plugin test"""
        self.assertOk( mutual_existing_fields, pairs_of_fields = { "242%%%" : "041%%%" } )
        self.assertFails( mutual_existing_fields, pairs_of_fields = { "242%%%" : "041__b" } )

    def test_if_then(self):
        """ If then plugin test"""
        self.assertFails( if_then, if_func = 'core_in_65017', then_func = 'core_should_exist')

    def test_ref_id_consistency(self):
        """ Reference Id consistency plugin test"""
        self.assertFails( ref_id_consistency) # Non-existent Inspire id in 999C50

    def test_add_recid_to_ref(self):
        """ Add record id to reference plugin test"""
        self.assertAmends( add_recid_to_ref, {"999C50":"1115372"} )

    def test_enrich_reference(self):
        """ Enrich reference plugin test"""

    # Test skipped by default because it involved making slow http requests
    #def test_url(self):
    #    """ Url checker plugin test. This plugin is disabled by default """
    #    self.assertOk(url, fields=["994%%u"])
    #    self.assertAmends(url, {"9954_u": "http://www.google.com/favicon.ico"}, fields=["995%%u"])
    #    self.assertAmends(url, {"9964_u": "http://httpstat.us"}, fields=["996%%u"])
    #    self.assertFails(url, fields=["997%%u"])
    #    self.assertFails(url, fields=["998%%u"])
    #    self.assertAmends(url, {"9994_u": "http://httpstat.us"}, fields=["999%%u"])


TEST_SUITE = make_test_suite(BibCheckPluginsTest)

if __name__ == "__main__":
    run_test_suite(TEST_SUITE)

