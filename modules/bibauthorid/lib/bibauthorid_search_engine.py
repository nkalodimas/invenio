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

""" Approximate search engine for authors. """

from invenio.bibauthorid_config import QGRAM_LEN, MATCHING_QGRAMS_PERCENTAGE, \
        MAX_T_OCCURANCE_RESULT_LIST_CARDINALITY, MIN_T_OCCURANCE_RESULT_LIST_CARDINALITY, \
        NAME_SCORE_COEFFICIENT

from Queue import Queue
from threading import Thread
from operator import itemgetter
from msgpack import packb as serialize
from msgpack import unpackb as deserialize

from invenio.textutils import translate_to_ascii
from invenio.intbitset import intbitset
from invenio.bibauthorid_name_utils import create_indexable_name, distance, split_name_parts
from bibauthorid_dbinterface import get_confirmed_name_to_authors_mapping, get_authors_data_from_indexable_name_ids, get_inverted_lists, \
                                    set_inverted_lists_ready, set_dense_index_ready, populate_table, search_engine_is_operating


# TODO: rename create_indexable_name to create_indexable_string


def get_qgrams_from_string(string, q):
    '''
    It decomposes the given string to its qgrams. The qgrams of a string are
    its substrings of length q. For example the 2-grams (q=2) of string cathey
    are (ca,at,th,he,ey).

    @param string: string to be decomposed
    @type string: str
    @param q: length of the grams
    @type q: int

    @return: the string qgrams ordered accordingly to the position they withhold in the string
    @rtype: list
    '''
    qgrams = list()

    for i in range(len(string)+1-q):
        qgrams.append(string[i:i+q])

    return qgrams


#####################################
###                               ###
###     Preprocessing/Indexing    ###
###                               ###
#####################################


def create_bibauthorid_indexer():
    '''
    It constructs the disk-based indexer. It consists of the dense index
    which maps a name/surname to the set of authors who withhold that name/surname
    and the inverted lists which map a qgram to the set of string ids (name/surname)
    that share that qgram.
    '''
    indexable_strings_to_authors_mapping = dict()

    name_to_authors_mapping = get_confirmed_name_to_authors_mapping()
    index_author_names(indexable_strings_to_authors_mapping, name_to_authors_mapping)

    index_author_surnames(indexable_strings_to_authors_mapping, name_to_authors_mapping)

    if not indexable_strings_to_authors_mapping:
        return

    # Convenient for assigning the same identifier to
    # each indexable string in different threads.
    indexable_strings = indexable_strings_to_authors_mapping.keys()

    # Threading is used because it reduces execution time to half.
    threads = list()

    # If an exception/error occurs in any of the threads it is
    # not detectable, hence inter-thread communication is used.
    queue = Queue()

    threads.append(Thread(target=create_dense_index, args=(indexable_strings_to_authors_mapping, indexable_strings, queue)))
    threads.append(Thread(target=create_inverted_lists, args=(indexable_strings, queue)))

    for t in threads:
        t.start()

    for t in threads:
        all_ok, error = queue.get(block=True)
        if not all_ok:
            raise error
        queue.task_done()

    for t in threads:
        t.join()


def index_author_names(indexable_strings_to_authors_mapping, name_to_authors_mapping):
    '''
    It makes a mapping which associates an indexable name to the authors who
    carry that name.

    @param indexable_strings_to_authors_mapping: mapping between indexable strings
        and authors who are associated to that string (e.g. full name, surname)
    @type indexable_strings_to_authors_mapping: dict {str: set(int,)}
    @param name_to_authors_mapping: mappping between names and authors who carry that name
    @type name_to_authors_mapping: dict {str: set(int,)}
    '''
    for name in name_to_authors_mapping:
        asciified_name = translate_to_ascii(name)[0]
        indexable_name = create_indexable_name(asciified_name)
        if indexable_name:
            try:
                indexable_strings_to_authors_mapping[indexable_name] |= name_to_authors_mapping[name]
            except KeyError:
                indexable_strings_to_authors_mapping[indexable_name] = name_to_authors_mapping[name]


def index_author_surnames(indexable_strings_to_authors_mapping, name_to_authors_mapping):
    '''
    It makes a mapping which associates an indexable surname to the authors who
    carry that surname.

    @param indexable_strings_to_authors_mapping: mapping between indexable strings
        and authors who are associated to that string (e.g. full name, surname)
    @type indexable_strings_to_authors_mapping: dict {str: set(int,)}
    @param name_to_authors_mapping: mappping between names and authors who carry that name
    @type name_to_authors_mapping: dict {str: set(int,)}
    '''
    for name in name_to_authors_mapping:
        surname = split_name_parts(name)[0]
        asciified_surname = translate_to_ascii(surname)[0]
        indexable_surname = create_indexable_name(asciified_surname)
        if indexable_surname:
            try:
                indexable_strings_to_authors_mapping[indexable_surname] |= name_to_authors_mapping[name]
            except KeyError:
                indexable_strings_to_authors_mapping[indexable_surname] = name_to_authors_mapping[name]


def create_dense_index(indexable_strings_to_authors_mapping, indexable_strings, queue):
    '''
    It saves in the disk the dense index which maps an indexable string to the
    set of authors who are associated to that string. Each indexable string is
    assigned a unique id.

    @param indexable_strings_to_authors_mapping: mapping between indexable strings
        and authors who are associated to that string (e.g. full name, surname)
    @type indexable_strings_to_authors_mapping: dict
    @param indexable_strings: indexable strings
    @type indexable_strings: list
    @param queue: queue used for inter-thread communication
    @type queue: Queue
    '''
    def _create_dense_index(indexable_strings_to_authors_mapping, indexable_strings):
        args = list()
        string_id = 0
        for string in indexable_strings:
            authors = indexable_strings_to_authors_mapping[string]
            args += [string_id, string, serialize(list(authors))]
            string_id += 1

        populate_table('aidDENSEINDEX', ['name_id', 'person_name', 'personids'], args)
        set_dense_index_ready()


    result = (True, None)

    try:
        _create_dense_index(indexable_strings_to_authors_mapping, indexable_strings)
    except Exception as e:
        result = (False, e)

    queue.put(result)


def create_inverted_lists(indexable_strings, queue):
    '''
    It saves in the disk the inverted lists which map a qgram to the set of
    string ids that share that qgram. It does so by decomposing each string
    into its qgrams and adds its id to the corresponding inverted list.

    @param indexable_strings: indexable strings
    @type indexable_strings: list
    @param queue: queue used for inter-thread communication
    @type queue: Queue
    '''
    def _create_inverted_lists(indexable_strings):
        inverted_lists = dict()
        string_id = 0
        for string in indexable_strings:
            qgrams = set(get_qgrams_from_string(string, QGRAM_LEN))
            for qgram in qgrams:
                try:
                    inverted_list, cardinality = inverted_lists[qgram]
                    inverted_list.add(string_id)
                    inverted_lists[qgram][1] = cardinality + 1
                except KeyError:
                    inverted_lists[qgram] = [set([string_id]), 1]
            string_id += 1

        args = list()
        for qgram in inverted_lists:
            inverted_list, cardinality = inverted_lists[qgram]
            args += [qgram, serialize(list(inverted_list)), cardinality]

        populate_table('aidINVERTEDLISTS', ['qgram', 'inverted_list', 'list_cardinality'], args)
        set_inverted_lists_ready()


    result = (True, None)

    try:
        _create_inverted_lists(indexable_strings)
    except Exception as e:
        result = (False, e)

    queue.put(result)


#####################################
###                               ###
###            Querying           ###
###                               ###
#####################################


def find_authors_by_name(query_string):
    '''
    @param query_string: the query string
    @type query_string: str

    @return:
    @rtype: list
    '''
    query_string_surname = split_name_parts(query_string)[0]

    # TODO: should there be duplicates?
    string_similarity_scores = get_string_similarity_scores(query_string)
    string_similarity_scores |= get_string_similarity_scores(query_string_surname)
    string_ranking = sorted(string_similarity_scores, key=itemgetter(1), reverse=True)

    author_scores = calculate_author_score(string_ranking)
    author_ranking = sorted(author_scores, key=itemgetter(2), reverse=True)
    author_ranking = [pid for pid, _, _ in author_ranking]

    return author_ranking


def get_string_similarity_scores(string):
    '''
    It finds a collection of personids who own a signature that is similar to the given query string.
    Its approach is by solving a 'T-occurance problem' and then it applies some filters to the candidate
    answers so it can remove the false positives. In the end it sorts the result set based on the score
    they obtained.

    @param query_string: the query string
    @type query_string: str

    @return:
    @rtype: set
    '''
    search_engine_is_functioning = search_engine_is_operating()
    if not search_engine_is_functioning:
        return set()

    asciified_string = translate_to_ascii(string)[0]
    indexable_string = create_indexable_name(asciified_string)
    if not indexable_string:
        return set()

    string_ids = solve_T_occurence_problem(indexable_string)

    if not string_ids:
        return set()

    string_similarity_scores = calculate_string_similarity_scores(indexable_string, string_ids)

    return string_similarity_scores


def solve_T_occurence_problem(query_string):
    '''
    It solves a 'T-occurence problem' which is defined as follows: find the
    string ids that appear at least T times in the inverted lists which
    correspond to each of the query string qgrams. T respresents the amount of
    qgrams that the query string and the strings in the result dataset must
    share. If the result dataset is bigger than a threshold it tries to limit
    it further.

    @param query_string: the query string
    @type query_string: str

    @return: strings that share T (or more) common qgrams with the query string
    @rtype: intbitset
    '''
    qgrams = set(get_qgrams_from_string(query_string, QGRAM_LEN))
    if not qgrams:
        return intbitset()

    inverted_lists = get_inverted_lists(qgrams)
    if not inverted_lists:
        return intbitset()

    inverted_lists = sorted(inverted_lists, key=itemgetter(1), reverse=True)
    # TODO: if a qgram exists more than on time, then the T-occurence problem may not return what we want
    T = int(MATCHING_QGRAMS_PERCENTAGE * len(inverted_lists))
    string_ids = intbitset(deserialize(inverted_lists[0][0]))

    for i in range(1, T):
        inverted_list = intbitset(deserialize(inverted_lists[i][0]))
        string_ids &= inverted_list

    for i in range(T, len(inverted_lists)):
        if len(string_ids) < MAX_T_OCCURANCE_RESULT_LIST_CARDINALITY:
            break
        inverted_list = intbitset(deserialize(inverted_lists[i][0]))
        string_ids_temp = string_ids & inverted_list
        if len(string_ids_temp) > MIN_T_OCCURANCE_RESULT_LIST_CARDINALITY:
            string_ids = string_ids_temp
        else:
            break

    return string_ids


def calculate_string_similarity_scores(string, string_ids):
    '''
    @param string:
    @type string: str
    @param string_ids:
    @type string_ids: intbitset

    @return:
    @rtype: set
    '''
    string_to_authors_mapping = get_authors_data_from_indexable_name_ids(string_ids)
    query_last_name = split_name_parts(string)[0]
    query_last_name_len = len(query_last_name)
    name_score_list = set()

    for name, personids in string_to_authors_mapping:
        current_last_name = split_name_parts(name)[0]
        current_last_name_len = len(current_last_name)
        if abs(query_last_name_len - current_last_name_len) == 0:
            dist = distance(query_last_name, current_last_name)
            limit = min([query_last_name_len, current_last_name_len])
            name_score = sum([1/float(2**(i+1)) for i in range(limit) if query_last_name[i] == current_last_name[i]])/(dist + 1)
            if name_score > 0.5:
                name_score_list.add((name, name_score, deserialize(personids)))

    return name_score_list


def calculate_author_score(string_ranking):
    '''
    @param string_ranking:
    @type string_ranking:

    @return:
    @rtype: list
    '''
    max_appearances = 1
    pid_metrics_dict = dict()

    for name, name_score, personids in string_ranking:
        for pid in personids:
            try:
                appearances = pid_metrics_dict[pid][2]+1
                pid_metrics_dict[pid][2] = appearances
                if appearances > max_appearances:
                    max_appearances = appearances
            except KeyError:
                pid_metrics_dict[pid] = [name, name_score, 1]

    pids_score_list = list()

    for pid in pid_metrics_dict.keys():
        name, name_score, appearances = pid_metrics_dict[pid]
        final_score = NAME_SCORE_COEFFICIENT*name_score + (1-NAME_SCORE_COEFFICIENT)*(appearances/float(max_appearances))
        pids_score_list.append((pid, name, final_score))

    return pids_score_list
