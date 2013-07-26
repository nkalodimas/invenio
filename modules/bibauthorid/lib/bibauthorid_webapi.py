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
Bibauthorid_webapi
Point of access to the documents clustering facility.
Provides utilities to safely interact with stored data.
'''
from copy import deepcopy

import invenio.bibauthorid_config as bconfig
import invenio.bibauthorid_frontinterface as dbapi
import invenio.bibauthorid_name_utils as nameapi
import invenio.webauthorprofile_interface as webauthorapi
from invenio.bibauthorid_general_utils import defaultdict

import invenio.search_engine as search_engine
from invenio.search_engine import perform_request_search
from cgi import escape
from invenio.dateutils import strftime
from time import time, gmtime, ctime
from invenio.access_control_admin import acc_find_user_role_actions
from invenio.webuser import collect_user_info, get_session, getUid
from invenio.webuser import isUserSuperAdmin
from invenio.access_control_engine import acc_authorize_action
from invenio.access_control_admin import acc_get_role_id, acc_get_user_roles
from invenio.external_authentication_robot import ExternalAuthRobot
from invenio.external_authentication_robot import load_robot_keys
from invenio.config import CFG_INSPIRE_SITE, CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL, CFG_BIBAUTHORID_ENABLED_REMOTE_LOGIN_SYSTEMS
from invenio.config import CFG_SITE_URL
from invenio.mailutils import send_email
from invenio.bibauthorid_name_utils import most_relevant_name

from itertools import chain

from invenio.bibauthorid_dbinterface import get_external_ids_of_author  #pylint: disable-msg=W0614



############################################
#           DB Data Accessors              #
############################################


def is_profile_available(pid):
    uid = get_uid_from_personid(pid)

    if uid == -1:
        return True
    return False

def get_bibrec_from_bibrefrec(bibrefrec):
    tmp_split_list = bibrefrec.split(':')
    if len(tmp_split_list) == 1:
        return -1
    tmp_split_list = bibrefrec.split[1](',')
    if len(tmp_split_list) == 1:
        return -1
    return int(tmp_split_list[1])

def get_bibrefs_from_bibrecs(bibreclist):
    '''
    Retrieve all bibrefs for all the recids in the list

    @param bibreclist: list of record IDs
    @type bibreclist: list of int

    @return: a list of record->bibrefs
    @return: list of lists
    '''
    return [[bibrec, dbapi.get_matching_bibrefs_for_paper([''], bibrec, always_match=True)]
            for bibrec in bibreclist]

def get_canonical_id_from_person_id(person_id):
    '''
    Finds the person  canonical name from personid (e.g. 1)

    @param person_id: person id
    @type person_id: int

    @return: result from the request or person_id on failure
    @rtype: int
    '''
    if not person_id:
        return None

    canonical_name = person_id

    try:
        canonical_name = dbapi.get_canonical_name_of_author(person_id)[0][0]
    except IndexError:
        pass

    return canonical_name

def get_external_ids_from_person_id(pid):
    '''
    Finds the person  external ids (doi, arxivids, ..) from personid (e.g. 1)

    @param person_id: person id
    @type person_id: int

    @return: dictionary of external ids
    @rtype: dict()
    '''
    if not pid or not (isinstance(pid, str) or isinstance(pid, (int, long))):
        return dict()

    if isinstance(pid, str):
        return None

    external_ids = dbapi.get_external_ids_of_author(pid)
    return external_ids

def get_longest_name_from_pid(person_id= -1):
    '''
    Finds the longest name of a person to be representative for this person.

    @param person_id: the person ID to look at
    @type person_id: int

    @return: returns the longest normalized name of a person
    @rtype: string
    '''
    if (not person_id > -1) or (not isinstance(person_id, (int, long))):
        return "This doesn't look like a person ID!"

    longest_name = ""

    for name in dbapi.get_names_count_of_author(person_id):
        if name and len(name[0]) > len(longest_name):
            longest_name = name[0]

    if longest_name:
        return longest_name
    else:
        return "This person does not seem to have a name!"


def get_most_frequent_name_from_pid(person_id= -1, allow_none=False):
    '''
    Finds the most frequent name of a person to be
    representative for this person.

    @param person_id: the person ID to look at
    @type person_id: int

    @return: returns the most frequent normalized name of a person
    @rtype: string
    '''
    pid = wash_integer_id(person_id)

    if (not pid > -1) or (not isinstance(pid, int)):
        if allow_none:
            return None
        else:
            return "'%s' doesn't look like a person ID!" % person_id
    person_id = pid

    mf_name = ""

    try:
        nn = dbapi.get_names_count_of_author(person_id)
        mf_name = sorted(nn, key=lambda k:k[1], reverse=True)[0][0]
    except IndexError:
        pass

    if mf_name:
        return mf_name
    else:
        if allow_none:
            return None
        else:
            return "This person does not seem to have a name!"

def get_papers_by_person_id(person_id= -1, rec_status= -2, ext_out=False):
    '''
    Returns all the papers written by the person

    @param person_id: identifier of the person to retrieve papers from
    @type person_id: int
    @param rec_status: minimal flag status a record must have to be displayed
    @type rec_status: int
    @param ext_out: Extended output (w/ author aff and date)
    @type ext_out: boolean

    @return: list of record info
    @rtype: list of lists of info
    '''
    if not isinstance(person_id, (int, long)):
        try:
            person_id = int(person_id)
        except (ValueError, TypeError):
            return []

    if person_id < 0:
        return []

    if not isinstance(rec_status, int):
        return []

    records = []
    db_data = dbapi.get_papers_info_of_author(person_id,
                                              rec_status,
                                              show_author_name=True,
                                              show_title=False,
                                              show_rt_status=True,
                                              show_affiliations=ext_out,
                                              show_date=ext_out,
                                              show_experiment=ext_out)
    if not ext_out:
        records = [[int(row["data"].split(",")[1]), row["data"], row["flag"],
                    row["authorname"]] for row in db_data]
    else:
        for row in db_data:
            recid = row["data"].split(",")[1]
            bibref = row["data"]
            flag = row["flag"]
            authorname = row["authorname"]
            rt_status = row['rt_status']
            authoraff = ", ".join(row['affiliation'])

            try:
                date = sorted(row['date'], key=len)[0]
            except IndexError:
                date = "Not available"

            exp = ", ".join(row['experiment'])
            # date = ""
            records.append([int(recid), bibref, flag, authorname,
                            authoraff, date, rt_status, exp])


    return records

def get_papers_cluster(bibref):
    '''
    Returns the cluster of documents connected with this one

    @param bibref: the table:bibref,bibrec pair to look for
    @type bibref: str

    @return: a list of record IDs
    @rtype: list of int
    '''
    papers = []
    person_id = get_person_id_from_paper(bibref)

    if person_id > -1:
        papers = get_papers_by_person_id(person_id)

    return papers

def get_paper_status(bibref):
    '''
    Finds an returns the status of a bibrec to person assignment

    @param bibref: the bibref-bibrec pair that unambiguously identifies a paper
    @type bibref: string
    '''
    db_data = dbapi.get_author_and_status_of_signature(bibref)
    # data,PersonID,flag
    status = None

    try:
        status = db_data[0][2]
    except IndexError:
        status = -10

    status = wash_integer_id(status)

    return status

def get_person_redirect_link(pid):
    '''
    Returns the canonical name of a pid if found, the pid itself otherwise
    @param pid: int
    '''
    cname = dbapi.get_canonical_name_of_author(pid)
    if len(cname) > 0:
        return str(cname[0][0])
    else:
        return str(pid)

def get_person_id_from_canonical_id(canonical_id):
    '''
    Finds the person id from a canonical name (e.g. Ellis_J_R_1)

    @param canonical_id: the canonical ID
    @type canonical_id: string

    @return: result from the request or -1 on failure
    @rtype: int
    '''
    if not canonical_id or not isinstance(canonical_id, str):
        return -1

    pid = -1

    try:
        pid = dbapi.get_author_by_canonical_name(canonical_id)[0][0]
    except IndexError:
        pass

    return pid

def get_person_id_from_paper(bibref=None):
    '''
    Returns the id of the person who wrote the paper

    @param bibref: the bibref,bibrec pair that identifies the person
    @type bibref: str

    @return: the person id
    @rtype: int
    '''
    if not is_valid_bibref(bibref):
        return -1

    person_id = -1
    db_data = dbapi.get_author_and_status_of_signature(bibref)

    try:
        person_id = db_data[0][1]
    except (IndexError):
        pass

    return person_id

def get_person_comments(person_id):
    '''
    Get all comments from a person

    @param person_id: person id to get the comments from
    @type person_id: int

    @return the message incl. the metadata if everything was fine, False on err
    @rtype: string or boolean
    '''
    pid = -1
    comments = []

    try:
        pid = int(person_id)
    except (ValueError, TypeError):
        return False

    for row in dbapi.get_persons_data([pid], "comment"):
        comments.append(row[1])

    return comments

def get_person_db_names_from_id(person_id= -1):
    '''
    Finds and returns the names associated with this person as stored in the
    meta data of the underlying data set along with the
    frequency of occurrence (i.e. the number of papers)

    @param person_id: an id to find the names for
    @type person_id: int

    @return: name and number of occurrences of the name
    @rtype: tuple of tuple
    '''
    ##retrieve all rows for the person
    if (not person_id > -1) or (not isinstance(person_id, (int, long))):
        return []

    return dbapi.get_names_of_author(person_id)

def get_person_names_from_id(person_id= -1):
    '''
    Finds and returns the names associated with this person along with the
    frequency of occurrence (i.e. the number of papers)

    @param person_id: an id to find the names for
    @type person_id: int

    @return: name and number of occurrences of the name
    @rtype: tuple of tuple
    '''
    ##retrieve all rows for the person
    if (not person_id > -1) or (not isinstance(person_id, (int, long))):
        return []

    return dbapi.get_names_count_of_author(person_id)

def get_person_request_ticket(pid= -1, tid=None):
    '''
    Returns the list of request tickets associated to a person.
    @param pid: person id
    @param tid: ticket id, to select if want to retrieve only a particular one
    @return: tickets [[],[]]
    '''
    if pid < 0:
        return []
    else:
        return dbapi.get_validated_request_tickets_for_author(pid, tid)

def get_persons_with_open_tickets_list():
    '''
    Finds all the persons with open tickets and returns pids and count of tickets
    @return: [[pid,ticket_count]]
    '''
    return dbapi.get_authors_with_open_tickets()

def get_pid_from_uid(uid):
    '''
    Return the PID associated with the uid

    @param uid: the internal ID of a user
    @type uid: int

    @return: the Person ID attached to the user or -1 if none found
    '''
    if isinstance(uid, tuple):
        uid = uid[0][0]
        assert False, ("AAAAARGH problem in get_pid_from_uid webapi. Got uid as a tuple instead of int.Uid = %s" % str(uid))
    pid, exists = dbapi.get_author_by_uid(uid)
    if exists:
        return pid
    return -1


def get_possible_bibrefs_from_pid_bibrec(pid, bibreclist, always_match=False, additional_names=None):
    '''
    Returns for each bibrec a list of bibrefs for which the surname matches.
    @param pid: person id to gather the names strings from
    @param bibreclist: list of bibrecs on which to search
    @param always_match: match all bibrefs no matter the name
    @param additional_names: [n1,...,nn] names to match other then the one from personid
    '''
    pid = wash_integer_id(pid)

    pid_names = dbapi.get_author_names_from_db(pid)
    if additional_names:
        pid_names += zip(additional_names)
    lists = []
    for bibrec in bibreclist:
        lists.append([bibrec, dbapi.get_matching_bibrefs_for_paper([n[0] for n in pid_names], bibrec,
                                                        always_match)])
    return lists

def get_processed_external_recids(pid):
    '''
    Get list of records that have been processed from external identifiers

    @param pid: Person ID to look up the info for
    @type pid: int

    @return: list of record IDs
    @rtype: list of strings
    '''

    list_str = dbapi.get_processed_external_recids(pid)

    return list_str.split(";")

def get_review_needing_records(pid):
    '''
    Returns list of records associated to pid which are in need of review
    (only bibrec ma no bibref selected)
    @param pid: pid
    '''
    pid = wash_integer_id(pid)
    db_data = dbapi.get_person_papers_to_be_manually_reviewed(pid)

    return [int(row[0][1]) for row in db_data if row[0][1]]

def get_uid_from_personid(pid):
    '''
    Return the uid associated with the pid

    @param pid: the person id
    @type uid: int

    @return: the internal ID of a user or -1 if none found
    '''
    result = dbapi.get_uid_of_author(pid)

    if not result:
        return -1
    return result

def get_user_level(uid):
    '''
    Finds and returns the aid-universe-internal numeric user level

    @param uid: the user's id
    @type uid: int

    @return: A numerical representation of the maximum access level of a user
    @rtype: int
    '''
    actions = [row[1] for row in acc_find_user_role_actions({'uid': uid})]
    return max([dbapi.get_paper_access_right(acc) for acc in actions])

def search_person_ids_by_name(namequery):
    '''
    Prepares the search to search in the database

    @param namequery: the search query the user enquired
    @type namequery: string

    @return: information about the result w/ probability and occurrence
    @rtype: tuple of tuple
    '''
    query = ""
    escaped_query = ""

    try:
        query = str(namequery)
    except (ValueError, TypeError):
        return []

    if query:
        escaped_query = escape(query, quote=True)
    else:
        return []

    return dbapi.find_personIDs_by_name_string(escaped_query)

############################################
#           DB Data Mutators               #
############################################

def add_person_comment(person_id, message):
    '''
    Adds a comment to a person after enriching it with meta-data (date+time)

    @param person_id: person id to assign the comment to
    @type person_id: int
    @param message: defines the comment to set
    @type message: string

    @return the message incl. the metadata if everything was fine, False on err
    @rtype: string or boolean
    '''
    msg = ""
    pid = -1
    try:
        msg = str(message)
        pid = int(person_id)
    except (ValueError, TypeError):
        return False

    strtimestamp = strftime("%Y-%m-%d %H:%M:%S", gmtime())
    msg = escape(msg, quote=True)
    dbmsg = "%s;;;%s" % (strtimestamp, msg)
    dbapi.set_person_data(pid, "comment", dbmsg)

    return dbmsg

def add_person_external_id(person_id, ext_sys, ext_id, userinfo=''):
    '''
    Adds an external id for the person
    @param person_id: person id
    @type person_id: int
    @param ext_sys: external system
    @type ext_sys: str
    @param ext_id: external id
    @type ext_id: str
    '''
    if userinfo.count('||'):
        uid = userinfo.split('||')[0]
    else:
        uid = ''

    tag = 'extid:%s' % ext_sys
    dbapi.set_person_data(person_id, tag, ext_id)

    log_value = '%s %s %s' % (person_id, tag, ext_id)
    dbapi.insert_user_log(userinfo, person_id, 'data_insertion', 'CMPUI_addexternalid', log_value, 'External id manually added.', userid=uid)

def add_review_needing_record(pid, bibrec_id):
    '''
    Add record in need of review to a person
    @param pid: pid
    @param bibrec_id: bibrec
    '''
    pid = wash_integer_id(pid)
    bibrec_id = wash_integer_id(bibrec_id)
    dbapi.add_person_paper_needs_manual_review(pid, bibrec_id)

def delete_person_external_ids(person_id, existing_ext_ids, userinfo=''):
    '''
    Deletes external ids of the person
    @param person_id: person id
    @type person_id: int
    @param existing_ext_ids: external ids to delete
    @type existing_ext_ids: list
    '''
    if userinfo.count('||'):
        uid = userinfo.split('||')[0]
    else:
        uid = ''

    deleted_ids = []
    for el in existing_ext_ids:
        if el.count('||'):
            ext_sys = el.split('||')[0]
            ext_id = el.split('||')[1]
        else:
            continue
        tag = 'extid:%s' % ext_sys
        dbapi.del_person_data(tag, person_id, ext_id)
        deleted_ids.append((person_id, tag, ext_id))

    dbapi.insert_user_log(userinfo, person_id, 'data_deletion', 'CMPUI_deleteextid', '', 'External ids manually deleted: ' + str(deleted_ids), userid=uid)

def del_review_needing_record(pid, bibrec_id):
    '''
    Removes a record in need of review from a person
    @param pid: personid
    @param bibrec_id: bibrec
    '''
    pid = wash_integer_id(pid)
    bibrec_id = wash_integer_id(bibrec_id)
    dbapi.del_person_papers_needs_manual_review(pid, bibrec_id)

def insert_log(userinfo, personid, action, tag, value, comment='', transactionid=0):
    '''
    Log an action performed by a user

    Examples (in the DB):
    1 2010-09-30 19:30  admin||10.0.0.1  1  assign  paper  1133:4442 'from 23'
    1 2010-09-30 19:30  admin||10.0.0.1  1  assign  paper  8147:4442
    2 2010-09-30 19:35  admin||10.0.0.1  1  reject  paper  72:4442

    @param userinfo: information about the user [UID|IP]
    @type userinfo: string
    @param personid: ID of the person this action is targeting
    @type personid: int
    @param action: intended action
    @type action: string
    @param tag: A tag to describe the data entered
    @type tag: string
    @param value: The value of the action described by the tag
    @type value: string
    @param comment: Optional comment to describe the transaction
    @type comment: string
    @param transactionid: May group bulk operations together
    @type transactionid: int

    @return: Returns the current transactionid
    @rtype: int
    '''
    userinfo = escape(str(userinfo))
    action = escape(str(action))
    tag = escape(str(tag))
    value = escape(str(value))
    comment = escape(str(comment))

    if not isinstance(personid, int):
        try:
            personid = int(personid)
        except (ValueError, TypeError):
            return -1

    if not isinstance(transactionid, int):
        try:
            transactionid = int(transactionid)
        except (ValueError, TypeError):
            return -1

    if userinfo.count('||'):
        uid = userinfo.split('||')[0]
    else:
        uid = ''

    return dbapi.insert_user_log(userinfo, personid, action, tag,
                       value, comment, transactionid, userid=uid)

def move_internal_id(person_id_of_owner, person_id_of_receiver):
    '''
    Assign an existing uid to another profile while keeping it to the old profile under the tag 'uid-old'

    @param person_id_of_owner pid: Person ID of the profile that currently has the internal id
    @type pid: int
    @param person_id_of_receiver pid: Person ID of the profile that will be assigned the internal id
    @type pid: int
    '''
    internal_id = dbapi.get_uid_of_author(person_id_of_owner)

    if not internal_id:
        return False

    dbapi.mark_internal_id_as_old(person_id_of_owner, internal_id)
    dbapi.add_author_data(person_id_of_receiver, 'uid', internal_id)
    return True

def move_external_ids(person_id_of_owner, person_id_of_receiver):
    '''
    Assign existing external ids to another profile

    @param person_id_of_owner pid: Person ID of the profile that currently has the internal id
    @type pid: int
    @param person_id_of_receiver pid: Person ID of the profile that will be assigned the internal id
    @type pid: int
    '''
    pass

def set_processed_external_recids(pid, recid_list):
    '''
    Set list of records that have been processed from external identifiers

    @param pid: Person ID to set the info for
    @type pid: int
    @param recid_list: list of recids
    @type recid_list: list of int
    '''
    if isinstance(recid_list, list):
        recid_list_str = ";".join(recid_list)

    dbapi.set_processed_external_recids(pid, recid_list_str)

def swap_person_canonical_name(person_id, desired_cname, userinfo=''):
    '''
    Swaps the canonical names of person_id and the person who withholds the desired canonical name.
    @param person_id: int
    @param desired_cname: string
    '''
    personid_with_desired_cname = get_person_id_from_canonical_id(desired_cname)
    if personid_with_desired_cname == person_id:
        return

    if userinfo.count('||'):
        uid = userinfo.split('||')[0]
    else:
        uid = ''

    current_cname = get_canonical_id_from_person_id(person_id)
    create_log_personid_with_desired_cname = False

    # nobody withholds the desired canonical name
    if personid_with_desired_cname == -1:
        dbapi.modify_canonical_name_of_authors([(person_id, desired_cname)])
    # person_id doesn't own a canonical name
    elif not isinstance(current_cname, str):
        dbapi.modify_canonical_name_of_authors([(person_id, desired_cname)])
        dbapi.update_canonical_names_of_authors([personid_with_desired_cname], overwrite=True)
        create_log_personid_with_desired_cname = True
    # both person_id and personid_with_desired_cname own a canonical name
    else:
        dbapi.modify_canonical_name_of_authors([(person_id, desired_cname), (personid_with_desired_cname, current_cname)])
        create_log_personid_with_desired_cname = True

    dbapi.insert_user_log(userinfo, person_id, 'data_update', 'CMPUI_changecanonicalname', '', 'Canonical name manually updated.', userid=uid)
    if create_log_personid_with_desired_cname:
        dbapi.insert_user_log(userinfo, personid_with_desired_cname, 'data_update', 'CMPUI_changecanonicalname', '', 'Canonical name manually updated.', userid=uid)

def update_person_canonical_name(person_id, canonical_name, userinfo=''):
    '''
    Updates a person's canonical name
    @param person_id: person id
    @param canonical_name: string
    '''
    if userinfo.count('||'):
        uid = userinfo.split('||')[0]
    else:
        uid = ''
    dbapi.update_canonical_names_of_authors([person_id], overwrite=True, suggested=canonical_name)
    dbapi.insert_user_log(userinfo, person_id, 'data_update', 'CMPUI_changecanonicalname', '', 'Canonical name manually updated.', userid=uid)

############################################
#           NOT TAGGED YET                 #
############################################

def wash_integer_id(param_id):
    '''
    Creates an int out of either int or string

    @param param_id: the number to be washed
    @type param_id: int or string

    @return: The int representation of the param or -1
    @rtype: int
    '''
    pid = -1

    try:
        pid = int(param_id)
    except (ValueError, TypeError):
        return (-1)

    return pid

def is_valid_bibref(bibref):
    '''
    Determines if the provided string is a valid bibref-bibrec pair

    @param bibref: the bibref-bibrec pair that unambiguously identifies a paper
    @type bibref: string

    @return: True if it is a bibref-bibrec pair and False if it's not
    @rtype: boolean
    '''
    if (not isinstance(bibref, str)) or (not bibref):
        return False

    if not bibref.count(":"):
        return False

    if not bibref.count(","):
        return False

    try:
        table = bibref.split(":")[0]
        ref = bibref.split(":")[1].split(",")[0]
        bibrec = bibref.split(":")[1].split(",")[1]
    except IndexError:
        return False

    try:
        table = int(table)
        ref = int(ref)
        bibrec = int(bibrec)
    except (ValueError, TypeError):
        return False

    return True


def is_valid_canonical_id(cid):
    '''
    Checks if presented canonical ID is valid in structure
    Must be of structure: ([Initial|Name]\.)*Lastname\.Number
    Example of valid cid: J.Ellis.1

    @param cid: The canonical ID to check
    @type cid: string

    @return: Is it valid?
    @rtype: boolean
    '''
    if not cid.count("."):
        return False

    xcheck = -1
    sp = cid.split(".")

    if not (len(sp) > 1 and sp[-1]):
        return False

    try:
        xcheck = int(sp[-1])
    except (ValueError, TypeError, IndexError):
        return False

    if xcheck and xcheck > -1:
        return True
    else:
        return False

def author_has_papers(pid):
    '''
    Checks if the given author identifier has papers.

    @param pid: author identifier
    @type pid: int

    @return: author has papers
    @rtype: bool
    '''
    try:
        pid = int(pid)
    except ValueError:
        return False

    papers = dbapi.get_papers_of_author(pid)
    if papers:
        return True

    return False


def user_can_modify_data(uid, pid):
    '''
    Determines if a user may modify the data of a person

    @param uid: the id of a user (invenio user id)
    @type uid: int
    @param pid: the id of a person
    @type pid: int

    @return: True if the user may modify data, False if not
    @rtype: boolean

    @raise ValueError: if the supplied parameters are invalid
    '''
    if not isinstance(uid, int):
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            raise ValueError("User ID has to be a number!")

    if not isinstance(pid, int):
        try:
            pid = int(pid)
        except (ValueError, TypeError):
            raise ValueError("Person ID has to be a number!")

    return dbapi.user_can_modify_data_of_author(uid, pid)


def user_can_modify_paper(uid, paper):
    '''
    Determines if a user may modify the record assignments of a person

    @param uid: the id of a user (invenio user id)
    @type uid: int
    @param pid: the id of a person
    @type pid: int

    @return: True if the user may modify data, False if not
    @rtype: boolean

    @raise ValueError: if the supplied parameters are invalid
    '''
    if not isinstance(uid, int):
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            raise ValueError("User ID has to be a number!")

    if not paper:
        raise ValueError("A bibref is expected!")

    return dbapi.user_can_modify_paper(uid, paper)


def person_bibref_is_touched_old(pid, bibref):
    '''
    Determines if an assignment has been touched by a user (i.e. check for
    the flag of an assignment being 2 or -2)

    @param pid: the id of the person to check against
    @type pid: int
    @param bibref: the bibref-bibrec pair that unambiguously identifies a paper
    @type bibref: string

    @raise ValueError: if the supplied parameters are invalid
    '''
    if not isinstance(pid, int):
        try:
            pid = int(pid)
        except (ValueError, TypeError):
            raise ValueError("Person ID has to be a number!")

    if not bibref:
        raise ValueError("A bibref is expected!")

    return dbapi.paper_affirmed_from_user_input(pid, bibref)

def is_logged_in_through_arxiv(req):
    '''
    Checks if the user is logged in through the arXiv.

    @param req: Apache request object
    @type req: Apache request object
    '''
    session = get_session(req)
    #THOMAS: ask samK about this variables: probably it would be better to rename them in the session as arxiv_sso_blabla
    #THOMAS: ask samK if this is correct, what other way there is to discover is we are SSOed through arxiv?
    #user_info = collect_user_info(req)
    #isGuestUser(req)
    # TO DO THIS SHOULD BE CHANGED
    if 'user_info' in session.keys() and 'email' in session['user_info'].keys() and session['user_info']['email']:
        return True
    return False

def is_logged_in_through_orcid(req):
    '''
    Checks if the user is logged in through the orcid.

    @param req: Apache request object
    @type req: Apache request object
    '''
    #THOMAS: right!
    return False

def login_status(req):
    '''
    Checks if the user is logged in and return his uid and external systems that he is logged in through.

    @param req: Apache request object
    @type req: Apache request object
    '''
    status = dict()
    # are we sure that we can get only one? ask SamK
    status['uid'] = getUid(req)
    status['logged_in'] = False
    status['remote_logged_in_systems'] = []

    if status['uid'] == 0:
        return status

    status['logged_in'] = True

    # for every system available
    for system in CFG_BIBAUTHORID_ENABLED_REMOTE_LOGIN_SYSTEMS:
        if IS_LOGGED_IN_THROUGH[system](req):
            status['remote_logged_in_systems'].append(system)

    return status

def session_bareinit(req):
    session = get_session(req)

    changed = False

    if 'personinfo' not in session:
        session['personinfo'] = dict()
        changed = True

    pinfo = session['personinfo']
    if 'marked_visit' not in pinfo:
        pinfo['marked_visit'] = None
    if 'visit diary' not in pinfo:
        pinfo['visit_diary'] = defaultdict(list)
        changed = True
    if 'diary_size_per_category' not in pinfo:
        pinfo['diary_size_per_category'] = 5
        changed = True
    if 'most_compatible_person' not in pinfo:
        pinfo['most_compatible_person'] = None
        changed = True
    if 'profile_suggestion_info' not in pinfo:
        pinfo["profile_suggestion_info"] = None
        changed = True
    if 'ticket' not in pinfo:
        pinfo["ticket"] = []
        changed = True
    if 'users_open_tickets_storage' not in pinfo:
        pinfo["users_open_tickets_storage"] = []
        changed = True
    if 'incomplete_autoclaimed_tickets_storage' not in pinfo:
        pinfo["incomplete_autoclaimed_tickets_storage"] = []
        changed = True
    if 'remote_login_system' not in pinfo:
        pinfo["remote_login_system"] = dict()
        changed = True
    if 'external_ids' not in pinfo:
        pinfo["external_ids"] = dict()
        changed = True
    for system in CFG_BIBAUTHORID_ENABLED_REMOTE_LOGIN_SYSTEMS:
        if system not in pinfo["remote_login_system"]:
            pinfo['remote_login_system'][system] = {'name': None, 'email': None}
            changed = True

    if changed:
        session.dirty = True

# all teh get_info methods should standardize the content:
def get_arxiv_info(req, uinfo):
    session_bareinit(req)
    session = get_session(req)
    arXiv_info = dict()

    try:
        name = uinfo['external_firstname']
    except KeyError:
        name = ''
    try:
        surname = uinfo['external_familyname']
    except KeyError:
        surname = ''

    if surname:
        session['personinfo']['remote_login_system']['arXiv']['name'] = nameapi.create_normalized_name(
                                          nameapi.split_name_parts(surname + ', ' + name))
    else:
        session['personinfo']['remote_login_system']['arXiv']['name'] = ''

    session['personinfo']['remote_login_system']['arXiv']['email'] = uinfo['email']
    arXiv_info['name'] = session['personinfo']['remote_login_system']['arXiv']['name']
    arXiv_info['email'] = uinfo['email']
    session.dirty = True

    return arXiv_info
    # {the dictionary we define in _webinterface}

# all teh get_info methods should standardize the content:
def get_orcid_info(req, uinfo):
    return dict()
    # {the dictionary we define in _webinterface}

def get_remote_login_systems_info(req, remote_logged_in_systems):
    '''
    For every remote_login_system get all of their info but for records and store them into a session dictionary

    @param req: Apache request object
    @type req: Apache request object

    @param remote_logged_in_systems: contains all remote_logged_in_systems tha the user is logged in through
    @type remote_logged_in_systems: dict
    '''
    session_bareinit(req)
    user_remote_logged_in_systems_info = dict()

    uinfo = collect_user_info(req)

    for system in remote_logged_in_systems:
        user_remote_logged_in_systems_info[system] = REMOTE_LOGIN_SYSTEMS_FUNCTIONS[system](req, uinfo)

    return user_remote_logged_in_systems_info

def get_arxivids(req):
    uinfo = collect_user_info(req)
    current_external_ids = []

    if 'external_arxivids' in uinfo.keys() and uinfo['external_arxivids']:
        current_external_ids = uinfo['external_arxivids'].split(';')
    # return ['2','3']
    return current_external_ids

def get_dois(req):
    return []

def get_remote_login_systems_ids(req, remote_logged_in_systems):
    session_bareinit(req)
    remote_login_systems_ids = dict()

    for system in remote_logged_in_systems:
        system_ids = REMOTE_LOGIN_SYSTEMS_GET_IDS_FUNCTIONS[system](req)
        remote_login_systems_ids[system] = system_ids

    #return {'arXiv':[2]}
    return remote_login_systems_ids


def get_arxiv_recids(req ):
    session = get_session(req)
    pinfo = session['personinfo']

    current_external_ids = get_arxivids(req)
    recids_from_arxivids = []
    cached_ids_association = pinfo['external_ids']

    #THOMAS: investigate with annette/skaplun what's the best way of using perform_request_search for this.
    #Alternatives: p='doi', p='doiID:doi', others? aka: is 037:arxiv really needed, only arxiv identifier is better or worse?

    if current_external_ids and not cached_ids_association:
        for arxivid in current_external_ids:
            # recid_list = perform_request_search(p=bconfig.CFG_BIBAUTHORID_REMOTE_LOGIN_SYSTEMS_IDENTIFIERS['arXiv'] + str(arxivid), of='id', rg=0)
            recid_list = perform_request_search(p=arxivid, f=bconfig.CFG_BIBAUTHORID_REMOTE_LOGIN_SYSTEMS_IDENTIFIERS['arXiv'], m1='e', cc='HEP')
            if recid_list:
                recid = recid_list[0]
                recids_from_arxivids.append(recid)
                cached_ids_association[('arxivid', arxivid)] = recid
            else:
                cached_ids_association[('arxivid', arxivid)] = -1
    elif current_external_ids:
        for arxivid in current_external_ids:
            if ('arxivid', arxivid) in cached_ids_association.keys():
                recid = cached_ids_association[('arxivid', arxivid)]
                recids_from_arxivids.append(recid)
            else:
                # recid_list = perform_request_search(p=bconfig.CFG_BIBAUTHORID_REMOTE_LOGIN_SYSTEMS_IDENTIFIERS['arXiv'] + str(arxivid), of='id', rg=0)
                recid_list = perform_request_search(p=arxivid, f=bconfig.CFG_BIBAUTHORID_REMOTE_LOGIN_SYSTEMS_IDENTIFIERS['arXiv'], m1='e', cc='HEP')
                if recid_list:
                    recid = recid_list[0]
                    recids_from_arxivids.append(recid)
                    cached_ids_association[('arxivid', arxivid)] = recid
    # cached_ids_association= { ('arxivid', '2'):  2, ('arxivid', '3'):  3}
    # recids_from_arxivids = [2,3]
    pinfo['external_ids'] = cached_ids_association
    session.dirty = True
    return recids_from_arxivids

def get_orcid_recids(req):
    return []

def get_remote_login_systems_recids(req, remote_logged_in_systems):
    session_bareinit(req)
    remote_login_systems_recids = []

    for system in remote_logged_in_systems:
        system_recids = REMOTE_LOGIN_SYSTEMS_GET_RECIDS_FUNCTIONS[system](req)
        remote_login_systems_recids += system_recids

    #return [2]
    return list(set(remote_login_systems_recids))

def get_cached_id_association(req):
    session_bareinit(req)
    session = get_session(req)
    pinfo = session['personinfo']

    return pinfo['external_ids']

def get_user_pid(uid):

    pid, pid_found = dbapi.get_author_by_uid(uid)

    if not pid_found:
        return -1

    return pid


def is_merge_allowed(profiles, user_pid, is_admin):
    '''
    Check if merging is allowed by finding the number of profiles that are owned by user. Merging can be perform
    only if at most one profile is connected to a user. Only admins can merge profile when 2 or more of them have claimed papers

    @param profiles: all the profiles that are going to be merged including the primary profile
    @type list

    '''
    owned_profiles = 0
    num_of_profiles_with_claimed_papers = 0

    for profile in profiles:
        if not is_profile_available(profile):
            if owned_profiles > 0:
                return False
            if not is_admin and user_pid != profile:
                return False
            owned_profiles += 1
        if len(dbapi.get_all_personids_recs(profile, claimed_only=True)) > 0:
            num_of_profiles_with_claimed_papers += 1

        if not is_admin and num_of_profiles_with_claimed_papers > 1:
            return False
    return True

def open_ticket_for_papers_of_merged_profiles(req, primary_profile, profiles):
    records = dbapi.defaultdict(list)

    profiles.append(primary_profile)
    for pid in profiles:
        papers = get_papers_by_person_id(pid)
        if papers:
            for rec_info in papers:
                records[rec_info[0]] += [rec_info[1]]

    recs_to_merge = []
    for recid in records.keys():
        # if more than one with the same recid we append only the recid and we let the user to solve tha problem in ticket_review
        if len(records[recid]) > 1:
            recs_to_merge.append(recid)
        else:
            recs_to_merge.append(records[recid][0])

    add_tickets(req, primary_profile, recs_to_merge, 'confirm')

def get_papers_of_merged_profiles(primary_profile, profiles):
    records = dict()
    # firstly the papers of the primary profile should be added as they should
    # be preffered from similar papers of other profiles with the same level of claim

    for pid in [primary_profile] + profiles:
        papers = get_papers_by_person_id(pid)
        for paper in papers:
            # if paper is rejected skip
            if paper[2] == -2:
                continue
            # if there is already a paper with the same record
            # and the new one is claimed while the existing one is not
            # keep only the claimed one
            if not paper[0] in records:
                records[paper[0]] = paper
            elif records[paper[0]] and records[paper[0]][2] == 0 and paper[2] == 2 :
                records[paper[0]] = paper

    return [records[recid] for recid in records.keys()]

def get_uid_for_merged_profiles(persons_data):
    for pid in persons_data.keys():
        for data in persons_data[pid]:
            if data[-1] == 'uid':
                return data
    return None

def get_data_union_for_merged_profiles(persons_data, new_profile_bibrecrefs):
    new_profile_data = list()
    # rt_new_counter will deal with the enumeration of rt_ticket in the merged profile
    rt_new_counter = 1
    rt_old_counter = -1

    for pid in persons_data.keys():
        for data in persons_data[pid]:
            if data[-1].startswith("rt_repeal") and not data[0] in new_profile_bibrecrefs:
                continue
            elif data[-1] == 'uid':
                continue
            elif data[-1] == 'canonical_name':
                continue
            elif data[-1].startswith("rt_"):
                if rt_old_counter != data[1]:
                    rt_old_counter = data[1]
                    rt_new_counter += 1
                data = (data[0],rt_new_counter,data[2],data[3],data[4])
            new_profile_data.append(data)
    return list(set(new_profile_data))


def merge_profiles(primary_profile, profiles):
    res = dbapi.get_persons_data([primary_profile], 'canonical_name')
    canonical_id_data = ''
    if res and res[primary_profile] and res[primary_profile][0]:
        canonical_id_data = res[primary_profile][0]

    persons_data = dbapi.get_persons_data([primary_profile] + profiles)

    new_profile_uid = get_uid_for_merged_profiles(persons_data)
    # move papers from the profiles to the primary profile
    new_profile_papers = get_papers_of_merged_profiles(primary_profile, profiles)
    new_profile_data = get_data_union_for_merged_profiles(persons_data, [paper[1] for paper in new_profile_papers])

    dbapi.del_person_data(None, primary_profile)
    if canonical_id_data:
        dbapi.add_author_data(primary_profile, canonical_id_data[4], canonical_id_data[0], canonical_id_data[1], canonical_id_data[2], canonical_id_data[3])
    else:
        dbapi.update_canonical_names_of_authors([primary_profile])
    # fill primary with data
    if new_profile_uid:
        dbapi.add_author_data(primary_profile, new_profile_uid[4], new_profile_uid[0], new_profile_uid[1], new_profile_uid[2], new_profile_uid[3])
    for data in new_profile_data:
        dbapi.add_author_data(primary_profile, data[4], data[0], data[1], data[2], data[3])

    for paper in new_profile_papers:
        recid = paper[0]
        splitted_bibrecref = paper[1].split(":")
        bibref_table = splitted_bibrecref[0]
        bibref_value = splitted_bibrecref[1].split(",")[0]
        sig = (bibref_table, bibref_value, recid)
        dbapi.move_signature(sig, primary_profile, force_claimed=False)

    for profile in profiles:
        dbapi.del_person_data(None, profile)

    dbapi.remove_empty_authors()

    profiles_to_update_can_id = list()
    for profile in profiles:
        if author_has_papers(profile):
            profiles_to_update_can_id.append(profile)

    dbapi.update_canonical_names_of_authors(profiles_to_update_can_id)

def auto_claim_papers(req, pid, recids):
    session_bareinit(req)

    # retrieve users existing papers
    pid_bibrecs = set([i[0] for i in dbapi.get_all_personids_recs(pid, claimed_only=True)])
    # retrieve the papers that need to be imported
    missing_bibrecs = list(set(recids) - pid_bibrecs)

    # store any users open ticket elsewhere until we have processed the autoclaimed tickets
    store_users_open_tickets(req)

    # add autoclaimed tickets to the session
    add_tickets(req, pid, missing_bibrecs, 'confirm')

def get_name_variants_list_from_remote_systems_names(remote_login_systems_info):
    name_variants = []

    for system in remote_login_systems_info.keys():
        name = remote_login_systems_info[system]['name']
        name_variants.append(name)

    return list(set(name_variants))

def match_profile(req, recids, remote_login_systems_info):
    session_bareinit(req)
    session = get_session(req)
    pinfo = session['personinfo']
    most_compatible_person = pinfo['most_compatible_person']

    if most_compatible_person != None:
        return most_compatible_person

    name_variants = get_name_variants_list_from_remote_systems_names(remote_login_systems_info)
    most_compatible_person = dbapi.find_most_compatible_person(recids, name_variants)
    pinfo['most_compatible_person'] = most_compatible_person
    return most_compatible_person

def get_profile_suggestion_info(req, pid):
    session_bareinit(req)
    session = get_session(req)
    pinfo = session['personinfo']
    profile_suggestion_info = pinfo['profile_suggestion_info']

    if profile_suggestion_info != None and pid == profile_suggestion_info['pid']:
        return profile_suggestion_info

    profile_suggestion_info = dict()
    profile_suggestion_info['canonical_id'] = dbapi.get_canonical_name_of_author(pid)
    name_variants = [element[0] for element in get_person_names_from_id(pid)]
    name = most_relevant_name(name_variants)
    profile_suggestion_info['name_string'] = "[No name available]  "

    if name != None:
        profile_suggestion_info['name_string'] = name

    if len(profile_suggestion_info['canonical_id']) > 0:
        profile_suggestion_info['canonical_name_string'] = "(" + profile_suggestion_info['canonical_id'][0][0] + ")"
        profile_suggestion_info['canonical_id'] = str(profile_suggestion_info['canonical_id'][0][0])
    else:
        profile_suggestion_info['canonical_name_string'] = "(" + str(pid) + ")"
        profile_suggestion_info['canonical_id'] = str(pid)

    profile_suggestion_info['pid'] = pid
    pinfo['profile_suggestion_info'] = profile_suggestion_info
    return profile_suggestion_info

def claim_profile(uid, pid):
    return dbapi.assign_person_to_uid(uid, pid)

def external_user_can_perform_action(uid):
    '''
    Check for SSO user and if external claims will affect the
    decision wether or not the user may use the Invenio claiming platform

    @param uid: the user ID to check permissions for
    @type uid: int

    @return: is user allowed to perform actions?
    @rtype: boolean
    '''
    # If no EXTERNAL_CLAIMED_RECORDS_KEY we bypass this check
    if not bconfig.EXTERNAL_CLAIMED_RECORDS_KEY:
        return True

    uinfo = collect_user_info(uid)
    keys = []
    for k in bconfig.EXTERNAL_CLAIMED_RECORDS_KEY:
        if k in uinfo:
            keys.append(k)

    full_key = False
    for k in keys:
        if uinfo[k]:
            full_key = True
            break

    return full_key

def is_external_user(uid):
    '''
    Check for SSO user and if external claims will affect the
    decision wether or not the user may use the Invenio claiming platform

    @param uid: the user ID to check permissions for
    @type uid: int

    @return: is user allowed to perform actions?
    @rtype: boolean
    '''
    # If no EXTERNAL_CLAIMED_RECORDS_KEY we bypass this check
    if not bconfig.EXTERNAL_CLAIMED_RECORDS_KEY:
        return False

    uinfo = collect_user_info(uid)
    keys = []
    for k in bconfig.EXTERNAL_CLAIMED_RECORDS_KEY:
        if k in uinfo:
            keys.append(k)

    full_key = False
    for k in keys:
        if uinfo[k]:
            full_key = True
            break

    return full_key

def check_transaction_permissions(uid, bibref, pid, action):
    '''
    Check if the user can perform the given action on the given pid,bibrefrec pair.
    return in: granted, denied, warning_granted, warning_denied

    @param uid: The internal ID of a user
    @type uid: int
    @param bibref: the bibref pair to check permissions for
    @type bibref: string
    @param pid: the Person ID to check on
    @type pid: int
    @param action: the action that is to be performed
    @type action: string

    @return: granted, denied, warning_granted xor warning_denied
    @rtype: string
    '''
    c_own = True
    c_override = False
    is_superadmin = isUserSuperAdmin({'uid': uid})

    access_right = _resolve_maximum_acces_rights(uid)
    bibref_status = dbapi.get_status_of_signature(bibref)
    old_flag = bibref_status[0]

    if old_flag == 2 or old_flag == -2:
        if action in ['confirm', 'assign']:
            new_flag = 2
        elif action in ['repeal']:
            new_flag = -2
        elif action in ['reset']:
            new_flag = 0
        if old_flag != new_flag:
            c_override = True

    uid_pid = dbapi.get_author_by_uid(uid)
    if not uid_pid[1] or pid != uid_pid[0]:
        c_own = False

    # if we cannot override an already touched bibref, no need to go on checking
    if c_override:
        if is_superadmin:
            return 'warning_granted'
        if access_right[1] < bibref_status[1]:
            return "warning_denied"
    else:
        if is_superadmin:
            return 'granted'

    # let's check if invenio is allowing us the action we want to perform
    if c_own:
        action = bconfig.CLAIMPAPER_CLAIM_OWN_PAPERS
    else:
        action = bconfig.CLAIMPAPER_CLAIM_OTHERS_PAPERS
    auth = acc_authorize_action(uid, action)
    if auth[0] != 0:
        return "denied"

    # now we know if claiming for ourselfs, we can ask for external ideas
    if c_own:
        action = 'claim_own_paper'
    else:
        action = 'claim_other_paper'

    ext_permission = external_user_can_perform_action(uid)

    # if we are here invenio is allowing the thing and we are not overwriting a
    # user with higher privileges, if externals are ok we go on!
    if ext_permission:
        if not c_override:
            return "granted"
        else:
            return "warning_granted"

    return "denied"


def delete_request_ticket(pid, ticket):
    '''
    Delete a request ticket associated to a person
    @param pid: pid (int)
    @param ticket: ticket id (int)
    '''
    dbapi.remove_request_ticket_for_author(pid, ticket)


def delete_transaction_from_request_ticket(pid, tid, action, bibref):
    '''
    Deletes a transaction from a ticket. If ticket empty, deletes it.
    @param pid: pid
    @param tid: ticket id
    @param action: action
    @param bibref: bibref
    '''
    rt = get_person_request_ticket(pid, tid)
    if len(rt) > 0:
#        rt_num = rt[0][1]
        rt = rt[0][0]
    else:
        return
    for t in list(rt):
        if str(t[0]) == str(action) and str(t[1]) == str(bibref):
            rt.remove(t)

    action_present = False
    for t in rt:
        if str(t[0]) in ['confirm', 'repeal']:
            action_present = True

    if not action_present:
        delete_request_ticket(pid, tid)
        return

    dbapi.update_request_ticket_for_author(pid, rt, tid)


def create_request_ticket(userinfo, ticket):
    '''
    Creates a request ticket
    @param usernfo: dictionary of info about user
    @param ticket: dictionary ticket
    '''
    # write ticket to DB
    # send eMail to RT
    udata = []
    mailcontent = []
    m = mailcontent.append
    m("A user sent a change request through the web interface.")
    m("User Information:")

    for k, v in userinfo.iteritems():
        if v:
            m("    %s: %s" % (k, v))

    m("\nLinks to all issued Person-based requests:\n")

    for i in userinfo:
        udata.append([i, userinfo[i]])

    tic = {}
    for t in ticket:
        if not t['action'] in ['confirm', 'assign', 'repeal', 'reset']:
            return False
        elif t['pid'] < 0:
            return False
        elif not is_valid_bibref(t['bibref']):
            return False
        if t['action'] == 'reset':
            # we ignore reset tickets
            continue
        else:
            if t['pid'] not in tic:
                tic[t['pid']] = []
        if t['action'] == 'assign':
            t['action'] = 'confirm'

        tic[t['pid']].append([t['action'], t['bibref']])

    for pid in tic:
        data = []
        for i in udata:
            data.append(i)
        data.append(['date', ctime()])
        for i in tic[pid]:
            data.append(i)
        dbapi.update_request_ticket_for_author(pid, data)
        pidlink = get_person_redirect_link(pid)

        m("%s/author/claim/%s?open_claim=True#tabTickets" % (CFG_SITE_URL, pidlink))

    m("\nPlease remember that you have to be logged in "
      "in order to see the ticket of a person.\n")

    if ticket and tic and mailcontent:
        sender = CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL

        if bconfig.TICKET_SENDING_FROM_USER_EMAIL and userinfo['email']:
            sender = userinfo['email']

        send_email(sender,
                   CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL,
                   subject="[Author] Change Request",
                   content="\n".join(mailcontent))

    return True

def create_request_message(userinfo, subj = None):
    mailcontent = []

    for info_type in userinfo:
        mailcontent.append(info_type + ': ')
        mailcontent.append(str(userinfo[info_type]) + '\n')

    sender = CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL

    if bconfig.TICKET_SENDING_FROM_USER_EMAIL and userinfo['email']:
        sender = userinfo['email']
    
    if not subj:
        subj = "[Author] Help Request"
    send_email(sender,
               CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL,
               subject=subj,
               content="\n".join(mailcontent))

def send_user_commit_notification_email(userinfo, ticket):
    '''
    Sends commit notification email to RT system
    '''
    # send eMail to RT
    mailcontent = []
    m = mailcontent.append
    m("A user committed a change through the web interface.")
    m("User Information:")

    for k, v in userinfo.iteritems():
        if v:
            m("    %s: %s" % (k, v))

    m("\nChanges:\n")

    for t in ticket:
        m(" --- <start> --- \n")
        for k, v in t.iteritems():
            m("    %s: %s \n" % (str(k), str(v)))
            if k == 'bibref':
                try:
                    br = int(v.split(',')[1])
                    m("        Title: %s\n" % search_engine.get_fieldvalues(br, "245__a"))
                except (TypeError, ValueError, IndexError):
                    pass
        m(" --- <end> --- \n")

    if ticket and mailcontent:
        sender = CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL
        send_email(sender,
                   CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL,
                   subject="[Author] NO ACTIONS NEEDED. Changes performed by SSO user.",
                   content="\n".join(mailcontent))

    return True


def user_can_view_CMP(uid):
    action = bconfig.CLAIMPAPER_VIEW_PID_UNIVERSE
    auth = acc_authorize_action(uid, action)
    if auth[0] == 0:
        return True
    else:
        return False


def _resolve_maximum_acces_rights(uid):
    '''
    returns [max_role, lcul] to use in execute_action and check_transaction_permissions.
    Defaults to ['guest',0] if user has no roles assigned.
    Always returns the maximum privilege.
    '''

    roles = {bconfig.CLAIMPAPER_ADMIN_ROLE: acc_get_role_id(bconfig.CLAIMPAPER_ADMIN_ROLE),
            bconfig.CLAIMPAPER_USER_ROLE: acc_get_role_id(bconfig.CLAIMPAPER_USER_ROLE)}
    uroles = acc_get_user_roles(uid)

    max_role = ['guest', 0]

    for r in roles:
        if roles[r] in uroles:
            rright = bconfig.CMPROLESLCUL[r]
            if rright >= max_role[1]:
                max_role = [r, rright]

    return max_role


def create_new_person(uid, uid_is_owner=False):
    '''
    Create a new person.

    @param uid: User ID to attach to the person
    @type uid: int
    @param uid_is_owner: Is the uid provided owner of the new person?
    @type uid_is_owner: bool

    @return: the resulting person ID of the new person
    @rtype: int
    '''
    pid = dbapi.create_new_author_by_uid(uid, uid_is_owner=uid_is_owner)

    return pid


def execute_action(action, pid, bibref, uid, userinfo='', comment=''):
    '''
    Executes the action, setting the last user right according to uid

    @param action: the action to perform
    @type action: string
    @param pid: the Person ID to perform the action on
    @type pid: int
    @param bibref: the bibref pair to perform the action for
    @type bibref: string
    @param uid: the internal user ID of the currently logged in user
    @type uid: int

    @return: list of a tuple: [(status, message), ] or None if something went wrong
    @rtype: [(bool, str), ]
    '''
    pid = wash_integer_id(pid)

    if not action in ['confirm', 'assign', 'repeal', 'reset']:
        return None
    elif pid == bconfig.CREATE_NEW_PERSON:
        pid = create_new_person(uid, uid_is_owner=False)
    elif pid < 0:
        return None
    elif not is_valid_bibref(bibref):
        return None

    if userinfo.count('||'):
        uid = userinfo.split('||')[0]
    else:
        uid = ''

    user_level = _resolve_maximum_acces_rights(uid)[1]

    res = None
    if action in ['confirm', 'assign']:
        dbapi.insert_user_log(userinfo, pid, 'assign', 'CMPUI_ticketcommit', bibref, comment, userid=uid)
        res = dbapi.confirm_papers_to_author(pid, [bibref], user_level)
    elif action in ['repeal']:
        dbapi.insert_user_log(userinfo, pid, 'repeal', 'CMPUI_ticketcommit', bibref, comment, userid=uid)
        res = dbapi.reject_papers_from_author(pid, [bibref], user_level)
    elif action in ['reset']:
        dbapi.insert_user_log(userinfo, pid, 'reset', 'CMPUI_ticketcommit', bibref, comment, userid=uid)
        res = dbapi.reset_papers_of_author(pid, [bibref])

    # This is the only point which modifies a person, so this can trigger the
    # deletion of a cached page
    webauthorapi.expire_all_cache_for_personid(pid)

    return res


def sign_assertion(robotname, assertion):
    '''
    Sign an assertion for the export of IDs

    @param robotname: name of the robot. E.g. 'arxivz'
    @type robotname: string
    @param assertion: JSONized object to sign
    @type assertion: string

    @return: The signature
    @rtype: string
    '''
    robotname = ""
    secr = ""

    if not robotname:
        return ""

    robot = ExternalAuthRobot()
    keys = load_robot_keys()

    try:
        secr = keys["Robot"][robotname]
    except:
        secr = ""

    return robot.sign(secr, assertion)

def get_orcids_by_pid(pid):
    orcids = dbapi.get_orcid_id_of_author(pid)

    return tuple(str(x[0]) for x in orcids)

def get_person_info_by_pid(pid):
    person_info = dict()
    person_info['pid'] = pid
    name_variants = [x for (x,y) in get_person_db_names_from_id(pid)]
    person_info['name'] = most_relevant_name(name_variants)
    person_info['canonical_name'] = get_canonical_id_from_person_id(pid)
    return person_info

############################################
#           Ticket Functions               #
############################################

def add_tickets(req, pid, bibrefs, action):
    session = get_session(req)
    pinfo = session["personinfo"]
    ticket = pinfo["ticket"]
    # the user wanted to create a new person to resolve the tickets to it
    if pid == bconfig.CREATE_NEW_PERSON:
        uid = getUid(req)
        pid = create_new_person(uid)

    tempticket = []
    for bibref in bibrefs:
        tempticket.append({'pid': pid, 'bibref': bibref, 'action': action})

    # check if ticket targets (bibref for pid) are already in ticket
    for t in tempticket:
        tempticket_is_valid_bibref = is_valid_bibref(t['bibref'])
        should_append = True
        for e in list(ticket):
            ticket_is_valid_bibref = is_valid_bibref(e['bibref'])
            # if they are the same leave ticket as it is and continue to the next tempticket
            if e['bibref'] == t['bibref'] and e['pid'] == t['pid']:
                ticket.remove(e)
                break
            # if we are comparing two different bibrefrecs with the same recids we remove the current bibrefrec and we add their recid
            elif e['pid'] == t['pid'] and tempticket_is_valid_bibref and ticket_is_valid_bibref and t['bibref'].split(',')[1] == e['bibref'].split(',')[1]:
                ticket.remove(e)
                ticket.append({'pid': pid, 'bibref': t['bibref'].split(',')[1], 'action': action})
                should_append = False
                break
            elif e['pid'] == t['pid'] and is_valid_bibref(e['bibref']) and str(t['bibref']) == e['bibref'].split(',')[1]:
                should_append = False
                break
            elif e['pid'] == t['pid'] and is_valid_bibref(t['bibref']) and str(e['bibref']) == t['bibref'].split(',')[1]:
                ticket.remove(e)
                break

        if should_append:
            ticket.append(t)

def manage_tickets(req, autoclaim_show_review, autoclaim):
    session = get_session(req)
    pinfo = session["personinfo"]
    ticket = pinfo["ticket"]
    page_info = dict()

    reviews_to_handle = is_ticket_review_handling_required(req)

    if not reviews_to_handle:
        is_required, incomplete_tickets = is_ticket_review_required(req)

        if is_required:
            if not autoclaim or autoclaim_show_review:
                bibrefs_auto_assigned, bibrefs_to_confirm = ticket_review(req, incomplete_tickets)
                page_info['type'] = 'Submit Attribution'
                page_info['title'] = 'Submit Attribution Information'
                page_info['body_params'] = [bibrefs_auto_assigned, bibrefs_to_confirm]
                return page_info
            else:
                guess_signature(req, incomplete_tickets)
                failed_to_autoclaim_tickets = []
                for t in list(ticket):
                    if 'incomplete' in t:
                        failed_to_autoclaim_tickets.append(t)
                        ticket.remove(t)

                store_incomplete_autoclaim_tickets(req, failed_to_autoclaim_tickets)
                session.dirty = True
    else:
        handle_ticket_review_results(req, autoclaim_show_review)

    for t in ticket:
        if 'incomplete' in t:
            assert False, "Wtf one ticket is incomplete " + str(pinfo)
        if ',' not in str(t['bibref']) or  ':' not in str(t['bibref']):
            assert False, "Wtf one ticket is invalid " + str(pinfo)
    uid = getUid(req)
    for t in ticket:
        t['status'] = check_transaction_permissions(uid,
                                                       t['bibref'],
                                                       t['pid'],
                                                       t['action'])
    session.dirty = True
    add_user_data_to_ticket(req)

    if not can_commit_ticket(req):
        mark_yours, mark_not_yours, mark_theirs, mark_not_theirs = confirm_valid_ticket(req)
        page_info['type'] = 'review actions'
        page_info['title'] = 'Please review your actions'
        page_info['body_params'] = [mark_yours, mark_not_yours, mark_theirs, mark_not_theirs]
        return page_info


    ticket_commit(req)
    page_info['type'] = 'dispatch end'
    return page_info


def confirm_valid_ticket(req):
    '''
    displays the user what can/cannot finally be done
    '''
    session = get_session(req)
    pinfo = session["personinfo"]
    ticket = pinfo["ticket"]
    ticket = [row for row in ticket if not "execution_result" in row]
    upid = pinfo["upid"]

    for tt in list(ticket):
        if not 'bibref' in tt or not 'pid' in tt:
            del(ticket[tt])
            continue

        tt['authorname_rec'] = dbapi.get_bibrefrec_name_string(tt['bibref'])
        tt['person_name'] = get_most_frequent_name_from_pid(tt['pid'])

    mark_yours = []
    mark_not_yours = []

    if upid >= 0:
        mark_yours = [row for row in ticket
                      if (str(row["pid"]) == str(upid) and
                          row["action"] in ["to_other_person", "confirm"])]
        mark_not_yours = [row for row in ticket
                          if (str(row["pid"]) == str(upid) and
                              row["action"] in ["repeal", "reset"])]
    mark_theirs = [row for row in ticket
                   if ((not str(row["pid"]) == str(upid)) and
                       row["action"] in ["to_other_person", "confirm"])]

    mark_not_theirs = [row for row in ticket
                       if ((not str(row["pid"]) == str(upid)) and
                           row["action"] in ["repeal", "reset"])]

    session.dirty = True

    return mark_yours, mark_not_yours, mark_theirs, mark_not_theirs

def guess_signature(req, incomplete_tickets):
    session = get_session(req)
    pinfo = session["personinfo"]
    tickets = pinfo["ticket"]
    
    if 'arxiv_name' in pinfo:
        arxiv_name = [pinfo['arxiv_name']]
    else:
        arxiv_name = None
        
    for incomplete_ticket in incomplete_tickets:
        # convert recid from string to int
        recid = wash_integer_id(incomplete_ticket['bibref'])
        
        if recid < 0:
            # this doesn't look like a recid--discard!
            tickets.remove(incomplete_ticket)
        else:
            pid = incomplete_ticket['pid']
            possible_signatures_per_rec = get_possible_bibrefs_from_pid_bibrec(pid, [recid], additional_names=arxiv_name)

            for [rec, possible_signatures] in possible_signatures_per_rec:
                # if there is only one bibreceref candidate for the given recid
                if len(possible_signatures) == 1:
                    # fix the incomplete ticket with the retrieved bibrecref
                    for ticket in list(tickets):
                        if incomplete_ticket['bibref'] == ticket['bibref'] and incomplete_ticket['pid'] == ticket['pid']:
                            ticket['bibref'] = possible_signatures[0][0]+','+str(rec)
                            ticket.pop('incomplete', True)
                            break
    session.dirty = True

def ticket_review(req, needs_review):
    session = get_session(req)
    pinfo = session["personinfo"]
    tickets = pinfo["ticket"]
    
    if 'arxiv_name' in pinfo:
        arxiv_name = [pinfo['arxiv_name']]
    else:
        arxiv_name = None
    
    
    bibrefs_auto_assigned = {}
    bibrefs_to_confirm = {}
    
    guess_signature(req, needs_review)

    for ticket in list(tickets):
        pid = ticket['pid']
        person_name = get_most_frequent_name_from_pid(pid, allow_none=True)
    
        if not person_name:
            if arxiv_name:
                person_name = ''.join(arxiv_name)
            else:
                person_name = " "

        if 'incomplete' not in ticket:
            recid = get_bibrec_from_bibrefrec(ticket['bibref'])
    
            if recid == -1:
                # No bibrefs on record--discard
                tickets.remove(ticket)
                continue     
            bibrefs_per_recid = get_bibrefs_from_bibrecs([recid])
            for bibref in bibrefs_per_recid[0]:
                if bibref[0] == ticket['bibref'].split(",")[0]:
                    more_possible_bibref = bibrefs_per_recid[0].pop(bibref)

            sorted_bibrefs = more_possible_bibref + sorted(bibrefs_per_recid[0][1], key=lambda x: x[1])
            if not pid in bibrefs_to_confirm:
                bibrefs_to_confirm[pid] = {
                    'person_name': person_name,
                    'canonical_id': "TBA",
                    'bibrecs': {recid: sorted_bibrefs}}
            else:
                bibrefs_to_confirm[pid]['bibrecs'][recid] = sorted_bibrefs
        else:
            # convert recid from string to int
            recid = wash_integer_id(ticket['bibref'])
            bibrefs_per_recid = get_bibrefs_from_bibrecs([recid])
    
            try:
                name = bibrefs_per_recid[0][1]
                sorted_bibrefs = sorted(name, key=lambda x: x[1])
            except IndexError:
                # No bibrefs on record--discard
                tickets.remove(ticket)
                continue

            # and add it to bibrefs_to_confirm list
            if not pid in bibrefs_to_confirm:
                bibrefs_to_confirm[pid] = {
                    'person_name': person_name,
                    'canonical_id': "TBA",
                    'bibrecs': {recid: sorted_bibrefs}}
            else:
                bibrefs_to_confirm[pid]['bibrecs'][recid] = sorted_bibrefs
    
        if bibrefs_to_confirm or bibrefs_auto_assigned:
            pinfo["bibref_check_required"] = True
            baa = deepcopy(bibrefs_auto_assigned)
            btc = deepcopy(bibrefs_to_confirm)
    
            for pid in baa:
                for rid in baa[pid]['bibrecs']:
                    baa[pid]['bibrecs'][rid] = []
    
            for pid in btc:
                for rid in btc[pid]['bibrecs']:
                    btc[pid]['bibrecs'][rid] = []
    
            pinfo["bibrefs_auto_assigned"] = baa
            pinfo["bibrefs_to_confirm"] = btc
        else:
            pinfo["bibref_check_required"] = False
    
    session.dirty = True
    return bibrefs_auto_assigned, bibrefs_to_confirm

def old_ticket_review(req, needs_review):
    session = get_session(req)
    pinfo = session["personinfo"]

    if 'arxiv_name' in pinfo:
        arxiv_name = [pinfo['arxiv_name']]
    else:
        arxiv_name = None


    bibrefs_auto_assigned = {}
    bibrefs_to_confirm = {}

    # if ("bibrefs_auto_assigned" in pinfo and pinfo["bibrefs_auto_assigned"]):
    #     bibrefs_auto_assigned = pinfo["bibrefs_auto_assigned"]
    #
    # if ("bibrefs_to_confirm" in pinfo and pinfo["bibrefs_to_confirm"]):
    #     bibrefs_to_confirm = pinfo["bibrefs_to_confirm"]

    for transaction in needs_review:
        # convert recid from string to int
        recid = wash_integer_id(transaction['bibref'])

        if recid < 0:
            # this doesn't look like a recid--discard!
            continue

        pid = transaction['pid']

        if ((pid in bibrefs_auto_assigned
             and 'bibrecs' in bibrefs_auto_assigned[pid]
             and recid in bibrefs_auto_assigned[pid]['bibrecs'])
            or
            (pid in bibrefs_to_confirm
             and 'bibrecs' in bibrefs_to_confirm[pid]
             and recid in bibrefs_to_confirm[pid]['bibrecs'])):
            # we already accessed those bibrefs.
            continue

        # access to possible bibrefs by arxiv  name and pid's name variants
        fctptr = get_possible_bibrefs_from_pid_bibrec
        bibrec_refs = fctptr(pid, [recid], additional_names=arxiv_name)
        person_name = get_most_frequent_name_from_pid(pid, allow_none=True)

        if not person_name:
            if arxiv_name:
                person_name = ''.join(arxiv_name)
            else:
                person_name = " "

        for brr in bibrec_refs:
            # if bibrefrec seems ok add it to the auto assign list
            if len(brr[1]) == 1:
                tmp = get_bibrefs_from_bibrecs([brr[0]])
                tmp[0][1].remove(brr[1][0])
                brr[1] = brr[1] + sorted(tmp[0][1], key=lambda x: x[1])
                if not pid in bibrefs_auto_assigned:
                    bibrefs_auto_assigned[pid] = {
                        'person_name': person_name,
                        'canonical_id': "TBA",
                        'bibrecs': {brr[0]: brr[1]}}
                else:
                    bibrefs_auto_assigned[pid]['bibrecs'][brr[0]] = brr[1]
            else:
                # if there is no bibreckref try to fix it

                tmp = get_bibrefs_from_bibrecs([brr[0]])

                try:
                    brr[1] = sorted(tmp[0][1], key=lambda x: x[1])
                except IndexError:
                    # No bibrefs on record--discard
                    continue
                # and add it to bibrefs_to_confirm list
                if not pid in bibrefs_to_confirm:
                    bibrefs_to_confirm[pid] = {
                        'person_name': person_name,
                        'canonical_id': "TBA",
                        'bibrecs': {brr[0]: brr[1]}}
                else:
                    bibrefs_to_confirm[pid]['bibrecs'][brr[0]] = brr[1]

    if bibrefs_to_confirm or bibrefs_auto_assigned:
        pinfo["bibref_check_required"] = True
        baa = deepcopy(bibrefs_auto_assigned)
        btc = deepcopy(bibrefs_to_confirm)

        for pid in baa:
            for rid in baa[pid]['bibrecs']:
                baa[pid]['bibrecs'][rid] = []

        for pid in btc:
            for rid in btc[pid]['bibrecs']:
                btc[pid]['bibrecs'][rid] = []

        pinfo["bibrefs_auto_assigned"] = baa
        pinfo["bibrefs_to_confirm"] = btc
    else:
        pinfo["bibref_check_required"] = False

    session.dirty = True
    return bibrefs_auto_assigned, bibrefs_to_confirm

def add_user_data_to_ticket(req):
    session = get_session(req)
    uid = getUid(req)
    userinfo = collect_user_info(uid)
    pinfo = session["personinfo"]
    upid = -1
    user_first_name = ""
    user_first_name_sys = False
    user_last_name = ""
    user_last_name_sys = False
    user_email = ""
    user_email_sys = False

    if ("external_firstname" in userinfo
          and userinfo["external_firstname"]):
        user_first_name = userinfo["external_firstname"]
        user_first_name_sys = True
    elif "user_first_name" in pinfo and pinfo["user_first_name"]:
        user_first_name = pinfo["user_first_name"]

    if ("external_familyname" in userinfo
          and userinfo["external_familyname"]):
        user_last_name = userinfo["external_familyname"]
        user_last_name_sys = True
    elif "user_last_name" in pinfo and pinfo["user_last_name"]:
        user_last_name = pinfo["user_last_name"]

    if ("email" in userinfo
          and not userinfo["email"] == "guest"):
        user_email = userinfo["email"]
        user_email_sys = True
    elif "user_email" in pinfo and pinfo["user_email"]:
        user_email = pinfo["user_email"]

    pinfo["user_first_name"] = user_first_name
    pinfo["user_first_name_sys"] = user_first_name_sys
    pinfo["user_last_name"] = user_last_name
    pinfo["user_last_name_sys"] = user_last_name_sys
    pinfo["user_email"] = user_email
    pinfo["user_email_sys"] = user_email_sys

    # get pid by user id
    if "upid" in pinfo and pinfo["upid"]:
        upid = pinfo["upid"]
    else:
        upid = get_pid_from_uid(uid)

        pinfo["upid"] = upid


    session.dirty = True

def can_commit_ticket(req):
    session = get_session(req)
    pinfo = session["personinfo"]
    ticket = pinfo["ticket"]
    ticket = [row for row in ticket if not "execution_result" in row]
    skip_checkout_page = True
    skip_checkout_page2 = True

    if not (pinfo["user_first_name"] or pinfo["user_last_name"] or pinfo["user_email"]):
        skip_checkout_page = False

    if [row for row in ticket
        if row["status"] in ["denied", "warning_granted",
                             "warning_denied"]]:
        skip_checkout_page2 = False

    if 'external_first_entry_skip_review' in pinfo and pinfo['external_first_entry_skip_review']:
        del(pinfo["external_first_entry_skip_review"])
        skip_checkout_page = True
        session.dirty = True

    if (not ticket or skip_checkout_page2
        or ("checkout_confirmed" in pinfo
            and pinfo["checkout_confirmed"]
            and "checkout_faulty_fields" in pinfo
            and not pinfo["checkout_faulty_fields"]
            and skip_checkout_page)):
        return True
    return False

def clean_ticket(req):
    '''
    Removes from a ticket the transactions with an execution_result flag
    '''
    session = get_session(req)
    pinfo = session["personinfo"]
    ticket = pinfo["ticket"]
    for t in list(ticket):
        if 'execution_result' in t:
            ticket.remove(t)
    session.dirty = True

def ticket_commit(req):
    '''
    Executes/Creates the tickets for the specified user permission level.

    @param ulevel: user permission level
    @type ulevel: str
    @param req: apache request object
    @type req: apache request object
    '''
    def ticket_commit_guest(req):
        clean_ticket(req)
        uid = getUid(req)
        userinfo = {'uid-ip': "userid: %s (from %s)" % (uid, req.remote_ip)}

        session = get_session(req)
        pinfo = session["personinfo"]
        if "user_ticket_comments" in pinfo:
            if pinfo["user_ticket_comments"]:
                userinfo['comments'] = pinfo["user_ticket_comments"]
            else:
                userinfo['comments'] = "No comments submitted."
        if "user_first_name" in pinfo:
            userinfo['firstname'] = pinfo["user_first_name"]
        if "user_last_name" in pinfo:
            userinfo['lastname'] = pinfo["user_last_name"]
        if "user_email" in pinfo:
            userinfo['email'] = pinfo["user_email"]

        ticket = pinfo['ticket']
        create_request_ticket(userinfo, ticket)

        for t in ticket:
            t['execution_result'] = [(True, ''), ]

        session.dirty = True


    def ticket_commit_user(req):
        clean_ticket(req)
        uid = getUid(req)
        userinfo = {'uid-ip': "%s||%s" % (uid, req.remote_ip)}

        session = get_session(req)
        pinfo = session["personinfo"]

        if "user_ticket_comments" in pinfo:
            userinfo['comments'] = pinfo["user_ticket_comments"]
        if "user_first_name" in pinfo:
            userinfo['firstname'] = pinfo["user_first_name"]
        if "user_last_name" in pinfo:
            userinfo['lastname'] = pinfo["user_last_name"]
        if "user_email" in pinfo:
            userinfo['email'] = pinfo["user_email"]

        ticket = pinfo["ticket"]
        ok_tickets = list()
        for t in list(ticket):
            if t['status'] in ['granted', 'warning_granted']:
                t['execution_result'] = execute_action(t['action'],
                                                    t['pid'], t['bibref'], uid,
                                                    userinfo['uid-ip'], str(userinfo))
                ok_tickets.append(t)
                ticket.remove(t)

        if ticket:
            create_request_ticket(userinfo, ticket)

        if CFG_INSPIRE_SITE and ok_tickets:
            send_user_commit_notification_email(userinfo, ok_tickets)

        for t in ticket:
            t['execution_result'] = [(True, 'confirm_ticket'), ]

        ticket += ok_tickets
        session.dirty = True

    def ticket_commit_admin(req):
        clean_ticket(req)
        uid = getUid(req)
        userinfo = {'uid-ip': "%s||%s" % (uid, req.remote_ip)}

        session = get_session(req)
        pinfo = session["personinfo"]

        if "user_ticket_comments" in pinfo:
            userinfo['comments'] = pinfo["user_ticket_comments"]
        if "user_first_name" in pinfo:
            userinfo['firstname'] = pinfo["user_first_name"]
        if "user_last_name" in pinfo:
            userinfo['lastname'] = pinfo["user_last_name"]
        if "user_email" in pinfo:
            userinfo['email'] = pinfo["user_email"]

        ticket = pinfo["ticket"]
        for t in ticket:
            t['execution_result'] = execute_action(t['action'], t['pid'], t['bibref'], uid,
                                                          userinfo['uid-ip'], str(userinfo))
        session.dirty = True

    commit = {'guest': ticket_commit_guest,
                     'user': ticket_commit_user,
                     'admin': ticket_commit_admin}


    session = get_session(req)
    pinfo = session["personinfo"]
    ulevel = pinfo["ulevel"]

    commit[ulevel](req)

    if "checkout_confirmed" in pinfo:
        del(pinfo["checkout_confirmed"])

    if "checkout_faulty_fields" in pinfo:
        del(pinfo["checkout_faulty_fields"])

    if "bibref_check_required" in pinfo:
        del(pinfo["bibref_check_required"])

    session.dirty = True

def is_ticket_review_handling_required(req):
    '''
    checks if the results of ticket reviewing should be handled
    @param req: Apache request object
    @type req: Apache request object
    '''

    session = get_session(req)
    pinfo = session["personinfo"]

    # if check is needed
    if ("bibref_check_required" in pinfo and pinfo["bibref_check_required"]
                                and "bibref_check_reviewed_bibrefs" in pinfo):
        return True
    return False

def handle_ticket_review_results(req, autoclaim):
    '''
    handle the results of ticket reviewing by either fixing tickets or removing them based on the review performed
    @param req: Apache request object
    @type req: Apache request object
    '''

    session = get_session(req)
    pinfo = session["personinfo"]
    ticket = pinfo["ticket"]
    print "xooo" + str(pinfo["bibref_check_reviewed_bibrefs"])
    # for every bibref in need of review
    for rbibreft in pinfo["bibref_check_reviewed_bibrefs"]:
        # if it's not in proper form skip it ( || delimiter is being added in bibauthorid_templates:tmpl_bibref_check function, coma delimiter
        # are being added in bibauthorid_webinterface: action function )
        # rbibreft ex: 'pid||bibrecref','8||100:4,45'
        if not rbibreft.count("||") or not rbibreft.count(","):
            continue

        # get pid and bibrecref
        rpid, rbibref = rbibreft.split("||")
        # get recid out of bibrecref
        rrecid = rbibref.split(",")[1]
        # convert string pid to int
        rpid = wash_integer_id(rpid)
        # updating ticket status with fixed bibrefs
        # and removing them from incomplete
        for ticket_update in [row for row in ticket
                              if (str(row['bibref']) == str(rrecid) and
                                  str(row['pid']) == str(rpid))]:
            ticket_update["bibref"] = rbibref
            
            if "incomplete" in ticket_update:
                del(ticket_update["incomplete"])
        session.dirty = True
    # tickets that could't be fixed will be removed or if they were to be autoclaimed they will be stored elsewhere
    if autoclaim:
        failed_to_autoclaim_tickets = []

        for ticket_remove in [row for row in ticket
                              if ('incomplete' in row)]:
            failed_to_autoclaim_tickets.append(ticket_remove)
            ticket.remove(ticket_remove)
        if failed_to_autoclaim_tickets:
            store_incomplete_autoclaim_tickets(req, failed_to_autoclaim_tickets)
    else:
        for ticket_remove in [row for row in ticket
                              if ('incomplete' in row)]:
            ticket.remove(ticket_remove)

    # delete also all bibrefs_auto_assigned, bibrefs_to_confirm and bibref_check_reviewed_bibrefs since the have been handled
    if ("bibrefs_auto_assigned" in pinfo):
        del(pinfo["bibrefs_auto_assigned"])

    if ("bibrefs_to_confirm" in pinfo):
        del(pinfo["bibrefs_to_confirm"])

    del(pinfo["bibref_check_reviewed_bibrefs"])
    # now there is no check required
    pinfo["bibref_check_required"] = False
    session.dirty = True

def is_ticket_review_required(req):
    '''
    checks if there are transactions inside ticket in need for review
    @param req: Apache request object
    @type req: Apache request object
    '''
    session = get_session(req)
    pinfo = session["personinfo"]
    ticket = pinfo["ticket"]
    needs_review = []

    # for every transaction in tickets check if there ara transaction that require review
    for transaction in ticket:
        if not is_valid_bibref(transaction['bibref']):
            transaction['incomplete'] = True
            needs_review.append(transaction)
    session.dirty = True
    if not needs_review:
        return (False, [])
    return (True, needs_review)

# restore any users open ticket, that is in storage , in session as autoclaiming has finished
def restore_users_open_tickets(req):
    session_bareinit(req)
    session = get_session(req)
    ticket = session['personinfo']['ticket']
    temp_storage = session['personinfo']['users_open_tickets_storage']

    for t in list(temp_storage):
        ticket.append(t)
        temp_storage.remove(t)
    temp_storage = []

# store any users open ticket elsewhere until we have processed the autoclaimed tickets
def store_users_open_tickets(req):
    session_bareinit(req)
    session = get_session(req)
    ticket = session['personinfo']['ticket']
    temp_storage = session['personinfo']['users_open_tickets_storage']
    for t in list(ticket):
        temp_storage.append(t)
        ticket.remove(t)

# store incomplete autoclaim's tickets elsewhere waiting for user interference in order not to mess with new tickets
def store_incomplete_autoclaim_tickets(req, failed_to_autoclaim_tickets):
    session_bareinit(req)
    session = get_session(req)
    temp_storage = session['personinfo']['incomplete_autoclaimed_tickets_storage']

    for incomplete_ticket in failed_to_autoclaim_tickets:
        if incomplete_ticket not in temp_storage:
            temp_storage.append(incomplete_ticket)

# restore any users open ticket, that is in storage , in session as autoclaiming has finished
def restore_incomplete_autoclaim_tickets(req):
    session_bareinit(req)
    session = get_session(req)
    ticket = session['personinfo']['ticket']
    temp_storage = session['personinfo']['incomplete_autoclaimed_tickets_storage']

    for t in list(temp_storage):
        ticket.append(t)
        temp_storage.remove(t)

def get_stored_incomplete_autoclaim_tickets(req):
    session_bareinit(req)
    session = get_session(req)
    temp_storage = session['personinfo']['incomplete_autoclaimed_tickets_storage']
    return temp_storage



############################################
#         Visit diary Functions            #
############################################

def history_log_visit(req, page, pid=None, params=None):
    """
    @param page: string (claim, manage_profile, profile, search)
    @param parameters: string (?param=aoeuaoeu&param2=blabla)
    """
    session_bareinit(req)
    session = get_session(req)
    pinfo = session['personinfo']
    my_diary = pinfo['visit_diary']

    my_diary[page].append({'page':page, 'pid':pid, 'params':params, 'timestamp':time()})

    if len(my_diary[page]) >  pinfo['diary_size_per_category']:
        my_diary[page].pop(0)

def _get_sorted_history(req, limit_to_page=None):
    session_bareinit(req)
    session = get_session(req)
    pinfo = session['personinfo']
    my_diary = pinfo['visit_diary']

    history = list()

    if not limit_to_page:
        history = my_diary.values()
    else:
        for page in limit_to_page:
            history += my_diary[page]

    history = list(chain(*my_diary.values()))

    history = sorted(history, key=lambda x: x['timestamp'], reverse=True)

    return history

def history_get_last_visited_url(req, limit_to_page=None):

    history = _get_sorted_history(req, limit_to_page)
    try:
        history = history[0]
    except IndexError:
        return ''

    link = [CFG_SITE_URL+'/author/', history['page']]

    if history['pid']:
        link.append('/'+str(get_canonical_id_from_person_id(history['pid'])))
    if history['params']:
        link.append(history['params'])

    return ''.join(link)

def history_get_last_visited_pid(req, limit_to_page=None):
    history = _get_sorted_history(req, limit_to_page)
    for visit in history:
        if visit['pid']:
            return visit['pid']

def set_marked_visit_link(req, page, pid = None, params = None):
    session_bareinit(req)
    session = get_session(req)
    pinfo = session['personinfo']
    if not page:
        pinfo['marked_visit'] = None
    else:
        link = [CFG_SITE_URL+'/author/', page]

        if pid:
            link.append('/'+str(get_canonical_id_from_person_id(pid)))
        if params:
            link.append(params)

        pinfo['marked_visit'] = ''.join(link)
    session.dirty = True

def get_marked_visit_link(req):
    session_bareinit(req)
    session = get_session(req)
    pinfo = session['personinfo']

    return pinfo['marked_visit']

def reset_marked_visit_link(req):
    set_marked_visit_link(req, None)

def get_fallback_redirect_link(req):
    uid = getUid(req)
    pid = get_pid_from_uid(uid)
    if uid <= 0 and pid < 0:
        return '%s' % (CFG_SITE_URL,)
    return '%s/author/manage_profiles/%s' % (CFG_SITE_URL, get_canonical_id_from_person_id(pid))
REMOTE_LOGIN_SYSTEMS_FUNCTIONS = {'arXiv': get_arxiv_info, 'orcid': get_orcid_info}
IS_LOGGED_IN_THROUGH = {'arXiv': is_logged_in_through_arxiv, 'orcid': is_logged_in_through_orcid}
REMOTE_LOGIN_SYSTEMS_GET_RECIDS_FUNCTIONS = {'arXiv': get_arxiv_recids, 'orcid': get_orcid_recids}
REMOTE_LOGIN_SYSTEMS_GET_IDS_FUNCTIONS = {'arXiv': get_arxivids, 'orcid': get_dois}
