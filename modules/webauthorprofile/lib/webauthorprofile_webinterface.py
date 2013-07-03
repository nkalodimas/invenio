# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2011 CERN.
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
WebAuthorProfile web interface logic and URL handler
"""

# pylint: disable=W0105
# pylint: disable=C0301
# pylint: disable=W0613

from sys import hexversion
from operator import itemgetter
from datetime import datetime, timedelta

from invenio.bibauthorid_webauthorprofileinterface import is_valid_canonical_id, \
    get_person_id_from_paper, get_person_id_from_canonical_id, author_has_papers, \
    search_person_ids_by_name, get_papers_by_person_id, get_person_redirect_link, \
    is_valid_bibref

from invenio.webauthorprofile_corefunctions import get_pubs, get_person_names_dicts, \
    get_institute_pubs, get_pubs_per_year, get_coauthors, get_summarize_records, \
    get_total_downloads, get_kwtuples, get_fieldtuples, get_veryfy_my_pubs_list_link, \
    get_hepnames_data, get_self_pubs, get_collabtuples, expire_all_cache_for_person

from invenio.webpage import pageheaderonly
from invenio.webinterface_handler import wash_urlargd, WebInterfaceDirectory
from invenio.urlutils import redirect_to_url
from invenio.jsonutils import json_unicode_to_utf8

import invenio.template
websearch_templates = invenio.template.load('websearch')
webauthorprofile_templates = invenio.template.load('webauthorprofile')
bibauthorid_template = invenio.template.load('bibauthorid')

from invenio.search_engine import page_end
JSON_OK = False

if hexversion < 0x2060000:
    try:
        import simplejson as json
        JSON_OK = True
    except ImportError:
        # Okay, no Ajax app will be possible, but continue anyway,
        # since this package is only recommended, not mandatory.
        JSON_OK = False
else:
    try:
        import json
        JSON_OK = True
    except ImportError:
        JSON_OK = False

from webauthorprofile_config import CFG_SITE_LANG, CFG_SITE_URL, \
    CFG_WEBAUTHORPROFILE_USE_BIBAUTHORID

RECOMPUTE_ALLOWED_DELAY = timedelta(minutes=30)

class WebAuthorPages(WebInterfaceDirectory):
    """ Handle webauthorpages. /author/ """
    _exports = ['']

    def _lookup(self, component, path):
        '''
        This handler parses dynamic URLs:
        - /person/1332 shows the page of person 1332
        - /person/100:5522,1431 shows the page of the person
            identified by the table: bibref, bibrec pair
        '''
        if not component in self._exports:
            return WebAuthorPages(component), path

        if not CFG_WEBAUTHORPROFILE_USE_BIBAUTHORID:
            return

    def __init__(self, identifier=None):
        '''
        Constructor of the web interface.

        @param identifier: identifier of an author. Can be one of:
            - an author id: e.g. "14"
            - a canonical id: e.g. "J.R.Ellis.1"
            - a bibrefrec: e.g. "100:1442,155"
        @type identifier: str
        '''
        self.person_id = -1   # -1 is a not valid author identifier
        self.cid = None
        self.original_search_parameter = identifier

        if (not CFG_WEBAUTHORPROFILE_USE_BIBAUTHORID or
            identifier is None or
            not isinstance(identifier, str)):
            return

        # check if it's a canonical id: e.g. "J.R.Ellis.1"
        pid = int(get_person_id_from_canonical_id(identifier))
        if pid >= 0:
            self.person_id = pid
            self.cid = get_person_redirect_link(self.person_id)
            return

        # check if it's an author id: e.g. "14"
        try:
            pid = int(identifier)
            if author_has_papers(pid):
                self.person_id = pid
                cid = get_person_redirect_link(pid)
                # author may not have a canonical id
                if is_valid_canonical_id(cid):
                    self.cid = cid
                return
        except ValueError:
            pass

        # check if it's a bibrefrec: e.g. "100:1442,155"
        if is_valid_bibref(identifier):
            pid = int(get_person_id_from_paper(identifier))
            if pid >= 0:
                self.person_id = pid
                self.cid = get_person_redirect_link(self.person_id)
                return

    def index(self, req, form):
        '''
        Serve the main person page.
        Will use the object's person id to get a person's information.

        @param req: apache request object
        @type req: apache request object
        @param form: POST/GET variables of the request
        @type form: dict

        @return: a full page formatted in HTML
        @return: str
        '''
        argd = wash_urlargd(form, {'ln': (str, CFG_SITE_LANG),
                                   'recid': (int, -1),
                                   'recompute': (int, 0),
                                   'verbose': (int, 0)})

        ln = argd['ln']
        verbose = argd['verbose']
        url_args = list()
        if ln != CFG_SITE_LANG:
            url_args.append('ln=%s' % ln)
        if verbose:
            url_args.append('verbose=%s' % verbose)
        url_tail = ''
        if url_args:
            url_tail = '&%s' % '&'.join(url_args)

        if CFG_WEBAUTHORPROFILE_USE_BIBAUTHORID:
            if self.person_id < 0:
                return redirect_to_url(req, '%s/author/search?q=%s%s' %
                                            (CFG_SITE_URL, self.original_search_parameter, url_tail))
        else:
            self.person_id = self.original_search_parameter

        req.content_type = 'text/html'
        if form.has_key('jsondata'):
            req.content_type = 'application/json'
            self.create_authorpage_websearch(req, form, self.person_id, ln)
            return

        req.send_http_header()
        metaheaderadd = '<script type="text/javascript" src="%s/js/webauthorprofile.js"> </script>' % (CFG_SITE_URL)
        metaheaderadd += '<script type="text/javascript" src="%s/js/jquery-lightbox/js/jquery.lightbox-0.5.js"></script>' % (CFG_SITE_URL)
        metaheaderadd += '<link rel="stylesheet" type="text/css" href="%s/js/jquery-lightbox/css/jquery.lightbox-0.5.css" media="screen" />' % (CFG_SITE_URL)
        metaheaderadd += '''
        <style>
        .hidden {
            display: none;
        }
        </style>
        '''
        title_message = 'Author Publication Profile Page'
        req.write(pageheaderonly(req=req,
                                 metaheaderadd=metaheaderadd,
                                 title=title_message,
                                 language=ln))
        req.write(websearch_templates.tmpl_search_pagestart(ln=ln))

        expire_cache = False
        if argd['recompute']:
            expire_cache = True
        self.create_authorpage_websearch(req, form, self.person_id, ln, expire_cache)

        return page_end(req, 'hb', ln)

    def __call__(self, req, form):
        '''
        Serves the main person page.
        Will use the object's person id to get a person's information.

        @param req: apache request object
        @type req: apache request object
        @param form: POST/GET variables of the request
        @type form: dict

        @return: a full page formatted in HTML
        @rtype: str
        '''
        if not CFG_WEBAUTHORPROFILE_USE_BIBAUTHORID:
            return self.index(req, form)

        argd = wash_urlargd(form, {'ln': (str, CFG_SITE_LANG),
                                   'recid': (int, -1),
                                   'verbose': (int, 0)})

        ln = argd['ln']
        verbose = argd['verbose']
        url_args = list()
        if ln != CFG_SITE_LANG:
            url_args.append('ln=%s' % ln)
        if verbose:
            url_args.append('verbose=%s' % verbose)
        url_tail = ''
        if url_args:
            url_tail = '?%s' % '&'.join(url_args)

        if self.cid:
            return redirect_to_url(req, '%s/author/%s/%s' % (CFG_SITE_URL, self.cid, url_tail))

        # author may have only author identifier and not a canonical id
        if self.person_id > -1:
            return redirect_to_url(req, '%s/author/%s/%s' % (CFG_SITE_URL, self.person_id, url_tail))

        recid = argd['recid']

        if recid > -1:
            sorted_authors = search_person_ids_by_name(self.original_search_parameter)
            authors_with_recid = list()

            for author, _ in sorted_authors:
                papers_of_author = get_papers_by_person_id(author, -1)
                papers_of_author = [int(paper[0]) for paper in papers_of_author]

                if recid not in papers_of_author:
                    continue

                authors_with_recid.append(int(author))

            if len(authors_with_recid) == 1:
                self.person_id = authors_with_recid[0]
                self.cid = get_person_redirect_link(self.person_id)
                redirect_to_url(req, '%s/author/%s/%s' % (CFG_SITE_URL, self.cid, url_tail))

        url_tail = ''
        if url_args:
            url_tail = '&%s' % '&'.join(url_args)
        return redirect_to_url(req, '%s/person/search?q=%s%s' %
                                    (CFG_SITE_URL, self.original_search_parameter, url_tail))

    def create_authorpage_websearch(self, req, form, person_id, ln='en', expire_cache=False):

        if CFG_WEBAUTHORPROFILE_USE_BIBAUTHORID:
            if person_id < 0:
                return ("Critical Error. PersonID should never be less than 0!")

        last_updated_list = []
        lu = last_updated_list.append

        pubs, pubsStatus, last_updated = get_pubs(person_id)
        if not pubs:
            pubs = []
        lu(last_updated)

        selfpubs, selfpubsStatus, last_updated = get_self_pubs(person_id)
        if not selfpubs:
            selfpubs = []
        lu(last_updated)

        namesdict, namesdictStatus, last_updated = get_person_names_dicts(person_id)
        if not namesdict:
            namesdict = {}

        try:
            authorname = namesdict['longest']
            db_names_dict = namesdict['db_names_dict']
        except (IndexError, KeyError):
            authorname = 'None'
            db_names_dict = {}
        lu(last_updated)

        #author_aff_pubs, author_aff_pubsStatus = (None, None)
        author_aff_pubs, author_aff_pubsStatus, last_updated = get_institute_pubs(person_id)
        if not author_aff_pubs:
            author_aff_pubs = {}
        lu(last_updated)

        coauthors, coauthorsStatus, last_updated = get_coauthors(person_id)
        if not coauthors:
            coauthors = {}
        lu(last_updated)

        summarize_records, summarize_recordsStatus, last_updated = get_summarize_records(person_id, 'hcs', ln)
        if not summarize_records:
            summarize_records = 'None'
        lu(last_updated)

        pubs_per_year, pubs_per_yearStatus, last_updated = get_pubs_per_year(person_id)
        if not pubs_per_year:
            pubs_per_year = {}
        lu(last_updated)

        totaldownloads, totaldownloadsStatus, last_updated = get_total_downloads(person_id)
        if not totaldownloads:
            totaldownloads = 0
        lu(last_updated)

        kwtuples, kwtuplesStatus, last_updated = get_kwtuples(person_id)
        if kwtuples:
            pass
            # kwtuples = kwtuples[0:MAX_KEYWORD_LIST]
        else:
            kwtuples = []
        lu(last_updated)

        fieldtuples, fieldtuplesStatus, last_updated = get_fieldtuples(person_id)
        if fieldtuples:
            pass
            # fieldtuples = fieldtuples[0:MAX_FIELDCODE_LIST]
        else:
            fieldtuples = []
        lu(last_updated)

        collab, collabStatus, last_updated = get_collabtuples(person_id)
        lu(last_updated)

        person_link, person_linkStatus, last_updated = get_veryfy_my_pubs_list_link(person_id)
        if not person_link or not person_linkStatus:
            bibauthorid_data = {"is_baid": True, "pid":person_id, "cid": None}
            person_link = str(person_id)
        else:
            bibauthorid_data = {"is_baid": True, "pid":person_id, "cid": person_link}
        lu(last_updated)

        hepdict, hepdictStatus, last_updated = get_hepnames_data(person_id)
        lu(last_updated)


        recompute_allowed = True

        oldest_cache_date = min(last_updated_list)
        delay = datetime.now() - oldest_cache_date
        if delay > RECOMPUTE_ALLOWED_DELAY:
            if expire_cache:
                expire_all_cache_for_person(person_id)
                return self.create_authorpage_websearch(req, form, person_id, ln, expire_cache=False)
        else:
            recompute_allowed = False

        # req.write("\nPAGE CONTENT START\n")
        # req.write(str(time.time()))
        # eval = [not_empty(x) or y for x, y in
        beval = [y for _, y in
                                               [(authorname, namesdictStatus),
                                               (totaldownloads, totaldownloadsStatus),
                                               (author_aff_pubs, author_aff_pubsStatus),
                                               (kwtuples, kwtuplesStatus),
                                               (fieldtuples, fieldtuplesStatus),
                                               (coauthors, coauthorsStatus),
                                               (db_names_dict, namesdictStatus),
                                               (person_link, person_linkStatus),
                                               (summarize_records, summarize_recordsStatus),
                                               (pubs, pubsStatus),
                                               (pubs_per_year, pubs_per_yearStatus),
                                               (hepdict, hepdictStatus),
                                               (selfpubs, selfpubsStatus),
                                               (collab, collabStatus)]]
        # not_complete = False in eval
        # req.write(str(eval))


        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            # loop to check which boxes need content
            json_response['boxes_info'].update({'name_variants': {'status':beval[0], 'html_content': webauthorprofile_templates.tmpl_author_name_variants_box(db_names_dict, bibauthorid_data, ln, add_box=False, loading=not beval[0])}})
            json_response['boxes_info'].update({'combined_papers': {'status':beval[12], 'html_content': webauthorprofile_templates.tmpl_papers_with_self_papers_box(pubs, selfpubs, bibauthorid_data, totaldownloads, ln, add_box=False, loading=not beval[12])}})
            json_response['boxes_info'].update({'keywords': {'status':beval[3], 'html_content': webauthorprofile_templates.tmpl_keyword_box(kwtuples, bibauthorid_data, ln, add_box=False, loading=not beval[3])}})
            json_response['boxes_info'].update({'fieldcodes': {'status':beval[4], 'html_content': webauthorprofile_templates.tmpl_fieldcode_box(fieldtuples, bibauthorid_data, ln, add_box=False, loading=not beval[4])}})
            json_response['boxes_info'].update({'affiliations': {'status':beval[2], 'html_content': webauthorprofile_templates.tmpl_affiliations_box(author_aff_pubs, ln, add_box=False, loading=not beval[2])}})
            json_response['boxes_info'].update({'coauthors': {'status':beval[5], 'html_content': webauthorprofile_templates.tmpl_coauthor_box(bibauthorid_data, coauthors, ln, add_box=False, loading=not beval[5])}})
            json_response['boxes_info'].update({'numpaperstitle': {'status':beval[9], 'html_content': webauthorprofile_templates.tmpl_numpaperstitle(bibauthorid_data, pubs)}})
            json_response['boxes_info'].update({'authornametitle': {'status':beval[6], 'html_content': webauthorprofile_templates.tmpl_authornametitle(db_names_dict)}})
            json_response['boxes_info'].update({'citations': {'status':beval[8], 'html_content': summarize_records}})
            json_response['boxes_info'].update({'pubs_graph': {'status':beval[10], 'html_content': webauthorprofile_templates.tmpl_graph_box(pubs_per_year, authorname, ln, add_box=False, loading=not beval[10])}})
            json_response['boxes_info'].update({'hepdata': {'status':beval[11], 'html_content':webauthorprofile_templates.tmpl_hepnames(hepdict, ln, add_box=False, loading=not beval[11])}})
            json_response['boxes_info'].update({'collaborations': {'status':beval[13], 'html_content': webauthorprofile_templates.tmpl_collab_box(collab, bibauthorid_data, ln, add_box=False, loading=not beval[13])}})

            req.content_type = 'application/json'
            req.write(json.dumps(json_response))
        else:
            gboxstatus = self.person_id
            if False not in beval:
                gboxstatus = 'noAjax'
            req.write('<script type="text/javascript">var gBOX_STATUS = "%s" </script>' % (gboxstatus))
            req.write(webauthorprofile_templates.tmpl_author_page(pubs, \
                                            selfpubs, authorname, totaldownloads, \
                                            author_aff_pubs, kwtuples, \
                                            fieldtuples, coauthors, db_names_dict, \
                                            person_link, bibauthorid_data, \
                                            summarize_records, pubs_per_year, \
                                            hepdict, collab, ln, beval, \
                                            oldest_cache_date, recompute_allowed))
