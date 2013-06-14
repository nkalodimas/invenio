import invenio.bibauthorid_config as bconfig
import numpy
import os
from cPickle import dump, load, UnpicklingError
from invenio.bibauthorid_dbinterface import get_db_time


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
            size = ((width + 1) * width) / 2
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
        first, second = bibs
        first, second = self._bibmap[first], self._bibmap[second]
        if first > second:
            first, second = second, first
        return first + (second * second + second) / 2

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
