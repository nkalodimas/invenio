# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012 CERN.
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

"""Unit tests for the search engine."""

__revision__ = \
    "$Id$"

import unittest
from itertools import chain

from invenio.bibauthorid_cluster_set import ClusterSet
from invenio.bibauthorid_bib_matrix import Bib_matrix

class Test_Bib_matrix(unittest.TestCase):

    def setUp(self):
        """
        Set up an empty bibmatrix and one filled with ten clusters of 10 elements each.
        """
        self.bm = Bib_matrix()
        self.css = ClusterSet()
        self.css.clusters = [ClusterSet.Cluster(range(i*10,i*10+10)) for i in range(10)]
        self.css.update_bibs()
        self.bmcs0 = Bib_matrix(self.css)

    def test_resolve_entry_simmetry(self):
        for j in range(100):
            for k in range(100):
                self.assertTrue( self.bmcs0._resolve_entry((j,k))==self.bmcs0._resolve_entry((k,j)) )

    def test_resolve_entry_unicity(self):
        '''
        resolve_entry should produce unuque indexes for any couple of values
        '''
        ntests = 30
        testvalues = set((i,j) for i in range(ntests) for j in range(ntests))
        for k in range(ntests):
            for z in range(ntests):
                tvalues = testvalues - set([(k,z)]) - set([(z,k)])
                val = self.bmcs0._resolve_entry((k,z))
                allvalues = set(self.bmcs0._resolve_entry(v) for v in tvalues)
                self.assertFalse( val in allvalues , str(val)+' is in, from '+str((k,z)))

    def test_matrix_content(self):
        '''
        The matrix should be simmetric, and values should be preserved
        '''
        for i in range(100):
            for j in range(i+1):
                self.bmcs0[i,j] = (i,j)

        for i in range(100):
            for j in range(100):
                val = self.bmcs0[i,j]
                if i < j:
                    k,z = j,i
                else:
                    k,z = i,j
                self.assertTrue(val[0] == k)
                self.assertTrue(val[1] == z)

    def test_create_empty_matrix(self):
        """
        All elements should be None
        """
        for i in range(9,10):
            for j in range(i*10,i*10+10):
                for k in range(i*10,i*10+10):
                        self.assertTrue(self.bmcs0[(j,k)] == None)


if __name__ == '__main__':
    #run_test_suite(TEST_SUITE)
    unittest.main(verbosity=2)