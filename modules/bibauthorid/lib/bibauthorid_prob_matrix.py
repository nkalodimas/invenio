# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2011, 2012 CERN.
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


import gc
import invenio.bibauthorid_config as bconfig
from invenio.bibauthorid_comparison import compare_bibrefrecs
from invenio.bibauthorid_comparison import clear_all_caches as clear_comparison_caches
from invenio.bibauthorid_backinterface import get_modified_papers_before
from invenio.bibauthorid_general_utils import bibauthor_print \
                                        , update_status \
                                        , update_status_final \
                                        , is_eq

from invenio.bibauthorid_dbinterface import get_db_time
import numpy
import os
from cPickle import dump, load, UnpicklingError

if bconfig.DEBUG_CHECKS:
    def _debug_is_eq_v(vl1, vl2):
        if isinstance(vl1, str) and isinstance(vl2, str):
            return vl1 == vl2

        if isinstance(vl1, tuple) and isinstance(vl2, tuple):
            return is_eq(vl1[0], vl2[0]) and is_eq(vl1[1], vl2[1])

        return False


class ProbabilityMatrix(object):
    '''
    This class contains and maintains the comparison
    between all virtual authors. It is able to write
    and read from the database and update the results.
    '''
    def __init__(self):
        self._bib_matrix = Bib_matrix()

    def load(self, lname, load_map=True, load_matrix=True):
        update_status(0., "Loading probability matrix...")
        self._bib_matrix.load(lname, load_map, load_matrix)
        update_status_final("Probability matrix loaded.")

    def store(self, name):
        update_status(0., "Saving probability matrix...")
        self._bib_matrix.store(name)
        update_status_final("Probability matrix saved.")

    def __getitem__(self, bibs):
        return self._bib_matrix[bibs[0], bibs[1]]

    def getitem_numeric(self, bibs):
        return self._bib_matrix.getitem_numeric(bibs)


    def __get_up_to_date_bibs(self):
        return frozenset(get_modified_papers_before(
                         self._bib_matrix.get_keys(),
                         self._bib_matrix.creation_time))

    def is_up_to_date(self, cluster_set):
        return self.__get_up_to_date_bibs() >= frozenset(cluster_set.all_bibs())

    def recalculate(self, cluster_set):
        '''
        Constructs probability matrix. If use_cache is true, it will
        try to load old computations from the database. If save cache
        is true it will save the current results into the database.
        @param cluster_set: A cluster set object, used to initialize
        the matrix.
        '''
        last_cleaned = 0
        gc.disable()

        old_matrix = self._bib_matrix
        cached_bibs = self.__get_up_to_date_bibs()
        have_cached_bibs = bool(cached_bibs)
        self._bib_matrix = Bib_matrix(cluster_set)

        ncl = cluster_set.num_all_bibs
        expected = ((ncl * (ncl - 1)) / 2)
        if expected == 0:
            expected = 1

        cur_calc, opti, prints_counter = 0, 0, 0
        for cl1 in cluster_set.clusters:

            if cur_calc+opti - prints_counter > 100000:
                update_status((float(opti) + cur_calc) / expected, "Prob matrix: calc %d, opti %d." % (cur_calc, opti))
                prints_counter = cur_calc+opti

#            #clean caches
            if cur_calc - last_cleaned > 20000000:
                gc.collect()
#                clear_comparison_caches()
                last_cleaned = cur_calc

            for cl2 in cluster_set.clusters:
                if id(cl1) < id(cl2) and not cl1.hates(cl2):
                    for bib1 in cl1.bibs:
                        for bib2 in cl2.bibs:
                            if have_cached_bibs:
                                try:
                                    val = old_matrix[bib1, bib2]
                                    opti += 1
                                    if bconfig.DEBUG_CHECKS:
                                        assert _debug_is_eq_v(val, compare_bibrefrecs(bib1, bib2))
                                except KeyError:
                                    cur_calc += 1
                                    val = compare_bibrefrecs(bib1, bib2)
                                if not val:
                                    cur_calc += 1
                                    val = compare_bibrefrecs(bib1, bib2)
                            else:
                                cur_calc += 1
                                val = compare_bibrefrecs(bib1, bib2)
                            self._bib_matrix[bib1, bib2] = val

        clear_comparison_caches()
        update_status_final("Matrix done. %d calc, %d opt." % (cur_calc, opti))
        gc.enable()


def prepare_matirx(cluster_set, force):
    if bconfig.DEBUG_CHECKS:
        assert cluster_set._debug_test_hate_relation()
        assert cluster_set._debug_duplicated_recs()

    matr = ProbabilityMatrix()
    matr.load(cluster_set.last_name, load_map=True, load_matrix=False)
    if not force and matr.is_up_to_date(cluster_set):
        bibauthor_print("Cluster %s is up-to-date and therefore will not be computed."
            % cluster_set.last_name)
        return False

    matr.load(cluster_set.last_name, load_map=False, load_matrix=True)
    matr.recalculate(cluster_set)
    matr.store(cluster_set.last_name)
    return True

class Bib_matrix(object):
    '''
    Contains the sparse matrix and encapsulates it.
    '''
    # please increment this value every time you
    # change the output of the comparison functions
    current_comparison_version = 10

    __special_items = ((None, -3.), ('+', -2.), ('-', -1.))
    special_symbols = dict((x[0], x[1]) for x in __special_items)
    special_numbers = dict((x[1], x[0]) for x in __special_items)

    def __init__(self, cluster_set=None):
        if cluster_set:
            self._bibmap = dict((b[1], b[0]) for b in enumerate(cluster_set.all_bibs()))
            width = len(self._bibmap)
            size = ((width - 1) * width) / 2
            self._matrix = Bib_matrix.create_empty_matrix(size)
        else:
            self._bibmap = dict()

        self.creation_time = get_db_time()

    @staticmethod
    def create_empty_matrix(lenght):
        ret = numpy.ndarray(shape=(lenght, 2), dtype=float, order='C')
        ret.fill(Bib_matrix.special_symbols[None])
        return ret

    def _resolve_entry(self, bibs):
        #assert len(bibs) == 2
        first = self._bibmap[bibs[0]]
        second = self._bibmap[bibs[1]]
        if first > second:
            first, second = second, first
        #assert first < second
        return first + ((second - 1) * second) / 2

    def __setitem__(self, bibs, val):
        entry = self._resolve_entry(bibs)
        self._matrix[entry] = Bib_matrix.special_symbols.get(val, val)

    def __getitem__(self, bibs):
        entry = self._resolve_entry(bibs)
        ret = self._matrix[entry]
        return Bib_matrix.special_numbers.get(ret[0], ret)

    def getitem_numeric(self, bibs):
        return self._matrix[self._resolve_entry(bibs)]

    def __contains__(self, bib):
        return bib in self._bibmap

    def get_keys(self):
        return self._bibmap.keys()

    @staticmethod
    def get_file_dir(name):
        sub_dir = name[:2]
        if not sub_dir:
            sub_dir = "empty_last_name"
        return "%s%s/" % (bconfig.TORTOISE_FILES_PATH, sub_dir)

    @staticmethod
    def get_map_path(dir_path, name):
        return "%s%s.bibmap" % (dir_path, name)

    @staticmethod
    def get_matrix_path(dir_path, name):
        return "%s%s.npy" % (dir_path, name)

    def load(self, name, load_map=True, load_matrix=True):
        files_dir = Bib_matrix.get_file_dir(name)

        if not os.path.isdir(files_dir):
            self._bibmap = dict()
            return False

        try:
            if load_map:
                bibmap_v = load(open(Bib_matrix.get_map_path(files_dir, name), 'r'))
                rec_v, self.creation_time, self._bibmap = bibmap_v
                if (rec_v != Bib_matrix.current_comparison_version or
                    # you can use negative version to recalculate
                    Bib_matrix.current_comparison_version < 0):

                    self._bibmap = dict()
                    return False

            if load_matrix:
                self._matrix = numpy.load(Bib_matrix.get_matrix_path(files_dir, name))
        except (IOError, UnpicklingError):
            if load_map:
                self._bibmap = dict()
                self.creation_time = get_db_time()
                return False
        return True

    def store(self, name):
        files_dir = Bib_matrix.get_file_dir(name)
        if not os.path.isdir(files_dir):
            try:
                os.mkdir(files_dir)
            except OSError, e:
                if e.errno == 17 or 'file exists' in str(e.strerror).lower():
                    pass
                else:
                    raise e

        bibmap_v = (Bib_matrix.current_comparison_version, self.creation_time, self._bibmap)
        dump(bibmap_v, open(Bib_matrix.get_map_path(files_dir, name), 'w'))

        numpy.save(open(Bib_matrix.get_matrix_path(files_dir, name), "w"), self._matrix)