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
'''
    bibauthorid_frontinterface
    This file aims to filter and modify the interface given by
    bibauthorid_bdinterface in order to make it usable by the
    frontend so to keep it as clean as possible.
'''
import re
from invenio.bibauthorid_name_utils import most_relevant_name
from invenio.bibauthorid_name_utils import split_name_parts  # emitting #pylint: disable-msg=W0611
from invenio.bibauthorid_name_utils import soft_compare_names
from invenio.bibauthorid_name_utils import create_normalized_name  # emitting #pylint: disable-msg=W0611
from invenio.bibauthorid_search_engine import find_personids_by_name
import invenio.bibauthorid_dbinterface as dbinter
from cgi import escape

# Well this is bad, BUT otherwise there must 100+ lines
# of the form from dbinterface import ...  # emitting
from invenio.bibauthorid_dbinterface import *  # pylint:  disable-msg=W0614
from invenio.bibauthorid_dbinterface import _get_orcid_id_of_author
canonical_name_format = re.compile("\S*[.](\d)+$")


def set_person_data(person_id, tag, value, user_level=None):
    '''
    @param person_id:
    @type person_id: int
    @param tag:
    @type tag: string
    @param value:
    @type value: string
    @param user_level:
    @type user_level: int
    '''
    old = dbinter.get_author_data(person_id, tag)
    old_data = [tup[0] for tup in old]
    if value not in old_data:
        dbinter.add_author_data(person_id, tag, value, opt2=user_level)

def get_person_data(person_id, tag):
    res = dbinter.get_author_data(person_id, tag)
    if res:
        return (res[1], res[0])
    else:
        return []

def del_person_data(tag, person_id=None, value=None):
    dbinter.remove_author_data(tag, person_id, value)

def get_bibrefrec_name_string(bibref):
    '''
    Returns the name string associated to a name string
    @param bibref: bibrefrec '100:123,123'
    @return: string
    '''
    name = ""
    ref = ""

    if not ((bibref and isinstance(bibref, str) and bibref.count(":"))):
        return name

    if bibref.count(","):
        try:
            ref = bibref.split(",")[0]
        except (ValueError, TypeError, IndexError):
            return name
    else:
        ref = bibref

    table, ref = ref.split(":")
    dbname = get_name_by_bibref((int(table), int(ref)))

    if dbname:
        name = dbname

    return name


def add_person_paper_needs_manual_review(pid, bibrec):
    '''
    Adds to a person a paper which needs manual review before bibref assignment
    @param pid: personid, int
    @param bibrec: the bibrec, int
    '''
    set_person_data(pid, 'paper_needs_bibref_manual_confirm', bibrec)


def get_person_papers_to_be_manually_reviewed(pid):
    '''
    Returns the set of papers awaiting for manual review for a person for bibref assignment
    @param pid: the personid, int
    '''
    return get_person_data(pid, 'paper_needs_bibref_manual_confirm')


def del_person_papers_needs_manual_review(pid, bibrec):
    '''
    Deletes from the set of papers awaiting for manual review for a person
    @param pid: personid, int
    @param bibrec: the bibrec, int
    '''
    del_person_data(person_id=pid, tag='paper_needs_bibref_manual_confirm', value=str(bibrec))


def set_processed_external_recids(pid, recid_list_str):
    '''
    Set processed external recids
    @param pid: pid
    @param recid_list_str: str
    '''
    del_person_data(person_id=pid, tag='processed_external_recids')
    set_person_data(pid, "processed_external_recids", recid_list_str)


def assign_person_to_uid(uid, pid):
    '''
    Assigns a person to a userid. If person already assigned to someone else, create new person.
    Returns two value. Firstly the person id assigned and secondly if uid was succesfully assigned to given pid.
    If parameter pid equals to -1 then we assign the uid to a new person
    @param uid: user id, int
    @param pid: person id, int, if -1 creates new person.
    @return: pid int, bool
    '''
    if pid == -1:
        pid = dbinter.create_new_author_by_uid(uid, uid_is_owner=True)
        return pid, True
    else:
        current_uid = get_person_data(pid, 'uid')
        if len(current_uid) == 0:
            set_person_data(pid, 'uid', str(uid))
            return pid, True
        return -1, False

def get_processed_external_recids(pid):
    '''
    Returns processed external recids
    @param pid: pid
    @return: [str]
    '''
    db_data = get_person_data(pid, "processed_external_recids")
    recid_list_str = ''

    if db_data and db_data[0] and db_data[0][1]:
        recid_list_str = db_data[0][1]

    return recid_list_str


def get_all_personids_recs(pid, claimed_only=False):
    return dbinter.get_papers_of_author(pid, claimed_only)

def mark_internal_id_as_old(person_id, uid):
    remove_author_data('uid', pid=person_id, value = uid)
    add_author_data(person_id, 'uid-old', value = uid)

def fallback_find_personids_by_name_string(target):
    '''
    Search engine to find persons matching the given string
    The matching is done on the surname first, and names if present.
    An ordered list (per compatibility) of pids and found names is returned.

    @param namestring: string name, 'surname, names I.'
    @type: string
    @param strict: Define if this shall perform an exact or a fuzzy match
    @type strict: boolean
    @return: pid list of lists
    [pid,[[name string, occur count, compatibility]]]
    '''
    splitted_name = split_name_parts(target)
    family = splitted_name[0]

    levels = (# target + '%', #this introduces a weird problem: different results for mele, salvatore and salvatore mele
              family + ',%',
              family[:-2] + '%',
              '%' + family + ',%',
              '%' + family[1:-1] + '%')

    if len(family) <= 4:
        levels = [levels[0], levels[2]]

    for lev in levels:
        names = dbinter.get_authors_by_name_regexp(lev)
        if names:
            break

    is_canonical = False
    if not names:
        names = dbinter.get_authors_by_canonical_name_regexp(target)
        is_canonical = True

    names = groupby(sorted(names))
    names = [(key[0], key[1], len(list(data)), soft_compare_names(target, key[1])) for key, data in names]
    names = groupby(names, itemgetter(0))
    names = [(key, sorted([(d[1], d[2], d[3]) for d in data if (d[3] > 0.5 or is_canonical)],
             key=itemgetter(2), reverse=True)) for key, data in names]
    names = [name for name in names if name[1]]
    names = sorted(names, key=lambda x: (x[1][0][2], x[1][0][0], x[1][0][1]), reverse=True)

    return names


def person_search_engine_query(query_string):
    '''
    docstring

    @param query_string:
    @type query_string:

    @return:
    @rtype:
    '''
    search_engine_status = dbinter.search_engine_is_operating()

    personid_name_list = list()
    if search_engine_status:
        personid_name_list = find_personids_by_name(query_string)

    if canonical_name_format.match(query_string):
        canonical_name_matches = list(get_authors_by_canonical_name_regexp(query_string))
        if canonical_name_matches:
            personid_name_list = canonical_name_matches + personid_name_list

    if personid_name_list:
        return personid_name_list

    return fallback_find_personids_by_name_string(query_string)


def find_personIDs_by_name_string(query_string):
    return person_search_engine_query(query_string)

def find_top5_personid_for_new_arxiv_user(bibrecs, name):

    top5_list = []

    pidlist = get_author_to_papers_mapping(bibrecs, limit_by_name=name)

    for p in pidlist:
        if not get_uid_of_author(p[0]):
            top5_list.append(p[0])
            if len(top5_list) > 4:
                break

    escaped_name = ""

    if name:
        escaped_name = escape(name, quote=True)
    else:
        return top5_list

    pidlist = find_personIDs_by_name_string(escaped_name)

    for p in pidlist:
        if not get_uid_of_author(p[0]) and not p[0] in top5_list:
            top5_list.append(p[0])
            if len(top5_list) > 4:
                break

    return top5_list


def check_personids_availability(picked_profile, uid):

    if picked_profile == -1:
        return create_new_author_by_uid(uid, uid_is_owner=True)
    else:
        if not get_uid_of_author(picked_profile):
            dbinter.add_author_data(picked_profile, 'uid', uid)
            return picked_profile
        else:
            return create_new_author_by_uid(uid, uid_is_owner=True)


def find_most_compatible_person(bibrecs, name_variants):
    if name_variants:
        relevant_name = most_relevant_name(name_variants)

        pidlist = get_author_to_papers_mapping(bibrecs, limit_by_name=relevant_name)

        for p in pidlist:
            if not get_uid_of_author(p[0]):
                return p[0]
    return -1
