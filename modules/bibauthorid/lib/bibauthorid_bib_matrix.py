import invenio.bibauthorid_config as bconfig
import numpy
import os
from cPickle import dump, load, UnpicklingError
from invenio.bibauthorid_dbinterface import get_db_time
import h5py


class Bib_matrix(object):
    """
    This is the low-ground representation of a simmetric matrix with mapped elements.
    Bib_matrix[a,b] resolves indexes of a and b to get or set to the relust.
    Bib_matrix has a persistence layer and operates directly on disk.
    """

    __special_items = ((None, -3.), ('+', -2.), ('-', -1.))
    special_symbols = dict((x[0], x[1]) for x in __special_items)
    special_numbers = dict((x[1], x[0]) for x in __special_items)

    def __init__(self, name, aliases=None, storage_dir_override=None):
        '''
        aliases: objects to be addressed in the matrix
        '''
        self.name = name
        self._f = None
        self._bibmap = None
        self._size = None
        self._matrix = None

        if storage_dir_override:
            self.get_file_dir = lambda : storage_dir_override

        self._prepare_destination_directory()
        #if os.path.exists(get)

    def open_h5py_file(self):
        self._prepare_destination_directory()
        try:
            self._f = h5py.File(self.get_matrix_path())
        except IOError:
            #If the file is corrupted h5py fails with IOErorr.
            #Give it a second try with an empty file before raising.
            os.remove(self.get_matrix_path())
            self._f = h5py.File(self.get_matrix_path())

    def get_file_dir(self):
        sub_dir = self.name[:2]
        if not sub_dir:
            sub_dir = "empty_last_name"
        return "%s%s/" % (bconfig.TORTOISE_FILES_PATH, sub_dir)

    def get_map_path(self):
        return "%s%s.bibmap" % (self.get_file_dir(), self.name)

    def get_matrix_path(self):
        return "%s%s.npy" % (self.get_file_dir(), self.name)

    def _prepare_destination_directory(self):
        files_dir = self.get_file_dir()
        if not os.path.isdir(files_dir):
            try:
                os.mkdir(files_dir)
            except OSError, e:
                if e.errno == 17 or 'file exists' in str(e.strerror).lower():
                    pass
                else:
                    raise e

class Bib_matrix(object):
    '''
    Contains the sparse matrix and encapsulates it.
    '''
    # please increment this value every time you
    # change the output of the comparison functions
    current_comparison_version = 0

    __special_items = ((None, -3.), ('+', -2.), ('-', -1.))
    special_symbols = dict((x[0], x[1]) for x in __special_items)
    special_numbers = dict((x[1], x[0]) for x in __special_items)

    def __init__(self, name, cluster_set=None, storage_dir_override=None):
        self.name = name
        self._f = None
        if storage_dir_override:
            self.get_file_dir = lambda : storage_dir_override

        if cluster_set:
            self._bibmap = dict((b[1], b[0]) for b in enumerate(cluster_set.all_bibs()))
            width = len(self._bibmap)
            self._size = ((width + 1) * width) / 2
        else:
            self._bibmap = dict()
        self._matrix = None

        self.creation_time = get_db_time()

    def _initialize_matrix(self):
        self.open_h5py_file()
        try:
            self._matrix = self._f.create_dataset("array", (self._size, 2), 'f')
        except RuntimeError:
            self._matrix = self._f["array"]
        self._matrix[...] = self.special_symbols[None]

    def _resolve_entry(self, bibs):
        first, second = bibs
        first, second = self._bibmap[first], self._bibmap[second]
        if first > second:
            first, second = second, first
        return first + (second * second + second) / 2

    def __setitem__(self, bibs, val):
        entry = self._resolve_entry(bibs)
        try:
            self._matrix[entry] = Bib_matrix.special_symbols.get(val, val)
        except TypeError:
            self._initialize_matrix()
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

    def get_file_dir(self):
        sub_dir = self.name[:2]
        if not sub_dir:
            sub_dir = "empty_last_name"
        return "%s%s/" % (bconfig.TORTOISE_FILES_PATH, sub_dir)

    def get_map_path(self):
        return "%s%s.bibmap" % (self.get_file_dir(), self.name)

    def get_matrix_path(self):
        return "%s%s.npy" % (self.get_file_dir(), self.name)

    def open_h5py_file(self):
        self._prepare_destination_directory()
        try:
            self._f = h5py.File(self.get_matrix_path())
        except IOError:
            #If the file is corrupted h5py fails with IOErorr.
            #Give it a second try with an empty file before raising.
            os.remove(self.get_matrix_path())
            self._f = h5py.File(self.get_matrix_path())

    def load(self, load_map=True, load_matrix=True):
        files_dir = self.get_file_dir()
        if not os.path.isdir(files_dir):
            self._bibmap = dict()
            return False

        try:
            if load_map:
                bibmap_v = load(open(self.get_map_path(), 'r'))
                rec_v, self.creation_time, self._bibmap = bibmap_v
                if (rec_v != Bib_matrix.current_comparison_version or
                    # you can use negative version to recalculate
                    Bib_matrix.current_comparison_version < 0):
                    self._bibmap = dict()
                    return False

            if load_matrix:
                if self._f:
                    self._f.close()
                self.open_h5py_file()
                self._matrix = self._f['array']

        except (IOError, UnpicklingError, KeyError):
            if load_map:
                self._bibmap = dict()
                self.creation_time = get_db_time()
            self._matrix = None
            return False
        return True

    def _prepare_destination_directory(self):
        files_dir = self.get_file_dir()
        if not os.path.isdir(files_dir):
            try:
                os.mkdir(files_dir)
            except OSError, e:
                if e.errno == 17 or 'file exists' in str(e.strerror).lower():
                    pass
                else:
                    raise e

    def store(self):
        self._prepare_destination_directory()
        bibmap_v = (Bib_matrix.current_comparison_version, self.creation_time, self._bibmap)
        dump(bibmap_v, open(self.get_map_path(), 'w'))

        if self._f:
            self._f.close()