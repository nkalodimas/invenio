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
    is_valid_bibref, get_person_id_from_paper, get_person_id_from_canonical_id, \
    search_person_ids_by_name, get_papers_by_person_id, get_person_redirect_link, \
    author_has_papers

from invenio.webauthorprofile_corefunctions import get_pubs, get_person_names_dicts, \
    get_institute_pubs, get_pubs_per_year, get_coauthors, get_summarize_records, \
    get_total_downloads, get_kwtuples, get_fieldtuples, get_veryfy_my_pubs_list_link, \
    get_hepnames_data, get_self_pubs, get_collabtuples, get_info_from_orcid, \
    expire_all_cache_for_person

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
    '''
    Handles webauthorpages /author/profile/
    '''
    _exports = ['',
                'create_authorpage_affiliations',
                'create_authorpage_authors_pubs',
                'create_authorpage_citations',
                'create_authorpage_coauthors',
                'create_authorpage_collaborations',
                'create_authorpage_combined_papers',
                'create_authorpage_fieldcodes',
                'create_authorpage_hepdata',
                'create_authorpage_keywords',
                'create_authorpage_name_variants',
                'create_authorpage_orcid_info',
                'create_authorpage_pubs',
                'create_authorpage_pubs_graph']

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
            not identifier or
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

    def _lookup(self, component, path):
        '''
        This handler parses dynamic URLs:
            - /author/profile/1332 shows the page of author with id: 1332
            - /author/profile/100:5522,1431 shows the page of the author
              identified by the bibrefrec: '100:5522,1431'
        '''
        if not component in self._exports:
            return WebAuthorPages(component), path

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
            return redirect_to_url(req, '%s/author/profile/%s/%s' % (CFG_SITE_URL, self.cid, url_tail))

        # author may have only author identifier and not a canonical id
        if self.person_id > -1:
            return redirect_to_url(req, '%s/author/profile/%s/%s' % (CFG_SITE_URL, self.person_id, url_tail))

        recid = argd['recid']

        if recid > -1:
            sorted_authors = search_person_ids_by_name(self.original_search_parameter)
            authors_with_recid = list()

            for author, _ in sorted_authors:
                papers_of_author = get_papers_by_person_id(author, -1)
                papers_of_author = [paper[0] for paper in papers_of_author]

                if recid not in papers_of_author:
                    continue

                authors_with_recid.append(int(author))

            if len(authors_with_recid) == 1:
                self.person_id = authors_with_recid[0]
                self.cid = get_person_redirect_link(self.person_id)
                redirect_to_url(req, '%s/author/profile/%s/%s' % (CFG_SITE_URL, self.cid, url_tail))

        url_tail = ''
        if url_args:
            url_tail = '&%s' % '&'.join(url_args)
        return redirect_to_url(req, '%s/author/claim/search?q=%s%s' %
                                    (CFG_SITE_URL, self.original_search_parameter, url_tail))

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
                return redirect_to_url(req, '%s/author/claim/search?q=%s%s' %
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

    def create_authorpage_name_variants(self,  req, form): # , person_id, expire_cache
        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            if json_data.has_key('personId'):
                person_id = json_data['personId']
                namesdict, namesdictStatus, last_updated = get_person_names_dicts(person_id)
                if not namesdict:
                    namesdict = {}

                try:
                    authorname = namesdict['longest']
                    db_names_dict = namesdict['db_names_dict']
                except (IndexError, KeyError):
                    authorname = 'None'
                    db_names_dict = {}

                person_link, person_linkStatus, last_updated = get_veryfy_my_pubs_list_link(person_id)
                if not person_link or not person_linkStatus:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": None}
                    person_link = str(person_id)
                else:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": person_link}

                json_response['boxes_info'].update({'name_variants': {'status': namesdictStatus, 'html_content': webauthorprofile_templates.tmpl_author_name_variants_box(db_names_dict, bibauthorid_data, ln='en', add_box=False, loading=not db_names_dict)}})
                req.content_type = 'application/json'
                req.write(json.dumps(json_response))


    def create_authorpage_combined_papers(self,  req, form):
        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            if json_data.has_key('personId'):
                person_id = json_data['personId']
                pubs, pubsStatus, last_updated = get_pubs(person_id)
                if not pubs:
                    pubs = []

                selfpubs, selfpubsStatus, last_updated = get_self_pubs(person_id)
                if not selfpubs:
                    selfpubs = []

                totaldownloads, totaldownloadsStatus, last_updated = get_total_downloads(person_id)
                if not totaldownloads:
                    totaldownloads = 0

                person_link, person_linkStatus, last_updated = get_veryfy_my_pubs_list_link(person_id)
                if not person_link or not person_linkStatus:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": None}
                    person_link = str(person_id)
                else:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": person_link}
                json_response['boxes_info'].update({'combined_papers': {'status': selfpubsStatus, 'html_content': webauthorprofile_templates.tmpl_papers_with_self_papers_box(pubs, selfpubs, bibauthorid_data, totaldownloads, ln='en', add_box=False, loading=not selfpubsStatus)}})
                req.content_type = 'application/json'
                req.write(json.dumps(json_response))

    def create_authorpage_keywords(self,  req, form):
        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            if json_data.has_key('personId'):
                person_id = json_data['personId']
                kwtuples, kwtuplesStatus, last_updated = get_kwtuples(person_id)
                if kwtuples:
                    pass
                    # kwtuples = kwtuples[0:MAX_KEYWORD_LIST]
                else:
                    kwtuples = []

                person_link, person_linkStatus, last_updated = get_veryfy_my_pubs_list_link(person_id)
                if not person_link or not person_linkStatus:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": None}
                    person_link = str(person_id)
                else:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": person_link}

                json_response['boxes_info'].update({'keywords': {'status': kwtuplesStatus, 'html_content': webauthorprofile_templates.tmpl_keyword_box(kwtuples, bibauthorid_data, ln='en', add_box=False, loading=not kwtuplesStatus)}})
                req.content_type = 'application/json'
                req.write(json.dumps(json_response))

    def create_authorpage_fieldcodes(self,  req, form):
        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            if json_data.has_key('personId'):
                person_id = json_data['personId']

                person_link, person_linkStatus, last_updated = get_veryfy_my_pubs_list_link(person_id)
                if not person_link or not person_linkStatus:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": None}
                    person_link = str(person_id)
                else:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": person_link}

                fieldtuples, fieldtuplesStatus, last_updated = get_fieldtuples(person_id)
                if fieldtuples:
                    pass
                    # fieldtuples = fieldtuples[0:MAX_FIELDCODE_LIST]
                else:
                    fieldtuples = []

                json_response['boxes_info'].update({'fieldcodes': {'status': fieldtuplesStatus, 'html_content': webauthorprofile_templates.tmpl_fieldcode_box(fieldtuples, bibauthorid_data, ln='en', add_box=False, loading=not fieldtuplesStatus)}})
                req.content_type = 'application/json'
                req.write(json.dumps(json_response))

    def create_authorpage_affiliations(self,  req, form):
        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            if json_data.has_key('personId'):
                person_id = json_data['personId']
                #author_aff_pubs, author_aff_pubsStatus = (None, None)
                author_aff_pubs, author_aff_pubsStatus, last_updated = get_institute_pubs(person_id)
                if not author_aff_pubs:
                    author_aff_pubs = {}

                json_response['boxes_info'].update({'affiliations': {'status': author_aff_pubsStatus, 'html_content': webauthorprofile_templates.tmpl_affiliations_box(author_aff_pubs, ln='en', add_box=False, loading=not author_aff_pubsStatus)}})
                req.content_type = 'application/json'
                req.write(json.dumps(json_response))

    def create_authorpage_coauthors(self,  req, form):
        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            if json_data.has_key('personId'):
                person_id = json_data['personId']
                coauthors, coauthorsStatus, last_updated = get_coauthors(person_id)
                if not coauthors:
                    coauthors = {}

                person_link, person_linkStatus, last_updated = get_veryfy_my_pubs_list_link(person_id)
                if not person_link or not person_linkStatus:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": None}
                    person_link = str(person_id)
                else:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": person_link}

                json_response['boxes_info'].update({'coauthors': {'status': coauthorsStatus, 'html_content': webauthorprofile_templates.tmpl_coauthor_box(bibauthorid_data, coauthors, ln='en', add_box=False, loading=not coauthorsStatus)}})
                req.content_type = 'application/json'
                req.write(json.dumps(json_response))

    def create_authorpage_pubs(self,  req, form):
        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            if json_data.has_key('personId'):
                person_id = json_data['personId']
                pubs, pubsStatus, last_updated = get_pubs(person_id)

                if not pubs:
                    pubs = []

                person_link, person_linkStatus, last_updated = get_veryfy_my_pubs_list_link(person_id)
                if not person_link or not person_linkStatus:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": None}
                    person_link = str(person_id)
                else:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": person_link}

                json_response['boxes_info'].update({'numpaperstitle': {'status': pubsStatus, 'html_content': webauthorprofile_templates.tmpl_numpaperstitle(bibauthorid_data, pubs)}})
                req.content_type = 'application/json'
                req.write(json.dumps(json_response))

    def create_authorpage_authors_pubs(self,  req, form):
        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            if json_data.has_key('personId'):
                person_id = json_data['personId']
                namesdict, namesdictStatus, last_updated = get_person_names_dicts(person_id)
                if not namesdict:
                    namesdict = {}

                try:
                    authorname = namesdict['longest']
                    db_names_dict = namesdict['db_names_dict']
                except (IndexError, KeyError):
                    authorname = 'None'
                    db_names_dict = {}

                person_link, person_linkStatus, last_updated = get_veryfy_my_pubs_list_link(person_id)
                if not person_link or not person_linkStatus:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": None}
                    person_link = str(person_id)
                else:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": person_link}

                pubs, pubsStatus, last_updated = get_pubs(person_id)

                if not pubs:
                    pubs = []

                json_response['boxes_info'].update({'authornametitle': {'status': (namesdictStatus and namesdictStatus and pubsStatus), 'html_content': webauthorprofile_templates.tmpl_authornametitle(authorname, bibauthorid_data, pubs, person_link, ln='en', loading=not (namesdictStatus and namesdictStatus and pubsStatus))}})
                req.content_type = 'application/json'
                req.write(json.dumps(json_response))

    def create_authorpage_citations(self,  req, form):
        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            if json_data.has_key('personId'):
                person_id = json_data['personId']
                summarize_records, summarize_recordsStatus, last_updated = get_summarize_records(person_id)
                if not summarize_records:
                    summarize_records = 'None'

                pubs, pubsStatus, last_updated = get_pubs(person_id)

                if not pubs:
                    pubs = []

                json_response['boxes_info'].update({'citations': {'status': (summarize_recordsStatus and pubsStatus), 'html_content': webauthorprofile_templates.tmpl_citations_box(summarize_records, pubs, ln='en', add_box=False, loading=not (summarize_recordsStatus and pubsStatus))}})
                req.content_type = 'application/json'
                req.write(json.dumps(json_response))

    def create_authorpage_pubs_graph(self,  req, form):
        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            if json_data.has_key('personId'):
                person_id = json_data['personId']
                pubs_per_year, pubs_per_yearStatus, last_updated = get_pubs_per_year(person_id)
                if not pubs_per_year:
                    pubs_per_year = {}

                json_response['boxes_info'].update({'pubs_graph': {'status': pubs_per_yearStatus, 'html_content': webauthorprofile_templates.tmpl_graph_box(pubs_per_year, ln='en', add_box=False, loading=not pubs_per_yearStatus)}})
                req.content_type = 'application/json'
                req.write(json.dumps(json_response))

    def create_authorpage_hepdata(self,  req, form):
        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            if json_data.has_key('personId'):
                person_id = json_data['personId']
                hepdict, hepdictStatus, last_updated = get_hepnames_data(person_id)

                json_response['boxes_info'].update({'hepdata': {'status': hepdictStatus, 'html_content': webauthorprofile_templates.tmpl_hepnames(hepdict, ln='en', add_box=False, loading=not hepdictStatus)}})
                req.content_type = 'application/json'
                req.write(json.dumps(json_response))

    def create_authorpage_collaborations(self,  req, form):
        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            if json_data.has_key('personId'):
                person_id = json_data['personId']
                collab, collabStatus, last_updated = get_collabtuples(person_id)

                person_link, person_linkStatus, last_updated = get_veryfy_my_pubs_list_link(person_id)
                if not person_link or not person_linkStatus:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": None}
                    person_link = str(person_id)
                else:
                    bibauthorid_data = {"is_baid": True, "pid": person_id, "cid": person_link}


                json_response['boxes_info'].update({'collaborations': {'status': collabStatus, 'html_content': webauthorprofile_templates.tmpl_collab_box(collab, bibauthorid_data, ln='en', add_box=False, loading=not collabStatus)}})
                req.content_type = 'application/json'
                req.write(json.dumps(json_response))

    def create_authorpage_orcid_info(self,  req, form):
        if form.has_key('jsondata'):
            json_response = {'boxes_info': {}}
            json_data = json.loads(str(form['jsondata']))
            json_data = json_unicode_to_utf8(json_data)
            if json_data.has_key('personId'):
                person_id = json_data['personId']
                orcid_info, orcid_infoStatus, last_updated = get_info_from_orcid(person_id)
                if not orcid_info:
                    orcid_info = {}

                json_response['boxes_info'].update({'orcid_info': {'status': orcid_infoStatus, 'html_content': webauthorprofile_templates.tmpl_orcid_info_box(orcid_info, ln='en', add_box=False, loading=not orcid_infoStatus)}})
                req.content_type = 'application/json'
                req.write(json.dumps(json_response))

    # def create_authorpage(self,  req):

    #     pubs, pubsStatus, last_updated = get_pubs(person_id)
    #     if not pubs:
    #         pubs = []
    #     status = pubsStatus

    #     selfpubs, selfpubsStatus, last_updated = get_self_pubs(person_id)
    #     if not selfpubs:
    #         selfpubs = []
    #     status = status and selfpubsStatus

    #     namesdict, namesdictStatus, last_updated = get_person_names_dicts(person_id)
    #     if not namesdict:
    #         namesdict = {}
    #     status = status and namesdictStatus

    #     try:
    #         authorname = namesdict['longest']
    #         db_names_dict = namesdict['db_names_dict']
    #     except (IndexError, KeyError):
    #         authorname = 'None'
    #         db_names_dict = {}

    #     #author_aff_pubs, author_aff_pubsStatus = (None, None)
    #     author_aff_pubs, author_aff_pubsStatus, last_updated = get_institute_pubs(person_id)
    #     if not author_aff_pubs:
    #         author_aff_pubs = {}
    #     status = status and author_aff_pubsStatus

    #     coauthors, coauthorsStatus, last_updated = get_coauthors(person_id)
    #     if not coauthors:
    #         coauthors = {}
    #     status = status and coauthorsStatus

    #     summarize_records, summarize_recordsStatus, last_updated = get_summarize_records(person_id)
    #     if not summarize_records:
    #         summarize_records = 'None'
    #     status = status and summarize_recordsStatus

    #     pubs_per_year, pubs_per_yearStatus, last_updated = get_pubs_per_year(person_id)
    #     if not pubs_per_year:
    #         pubs_per_year = {}
    #     status = status and pubs_per_yearStatus

    #     totaldownloads, totaldownloadsStatus, last_updated = get_total_downloads(person_id)
    #     if not totaldownloads:
    #         totaldownloads = 0
    #     status = status and totaldownloadsStatus

    #     kwtuples, kwtuplesStatus, last_updated = get_kwtuples(person_id)
    #     if kwtuples:
    #         pass
    #         # kwtuples = kwtuples[0:MAX_KEYWORD_LIST]
    #     else:
    #         kwtuples = []
    #     status = status and kwtuplesStatus

    #     fieldtuples, fieldtuplesStatus, last_updated = get_fieldtuples(person_id)
    #     if fieldtuples:
    #         pass
    #         # fieldtuples = fieldtuples[0:MAX_FIELDCODE_LIST]
    #     else:
    #         fieldtuples = []
    #     status = status and fieldtuplesStatus

    #     collab, collabStatus, last_updated = get_collabtuples(person_id)
    #     status = status and collabStatus

    #     person_link, person_linkStatus, last_updated = get_veryfy_my_pubs_list_link(person_id)
    #     if not person_link or not person_linkStatus:
    #         bibauthorid_data = {"is_baid": True, "pid":person_id, "cid": None}
    #         person_link = str(person_id)
    #     else:
    #         bibauthorid_data = {"is_baid": True, "pid":person_id, "cid": person_link}
    #     status = status and person_linkStatus

    #     hepdict, hepdictStatus, last_updated = get_hepnames_data(person_id)
    #     status = status and hepdictStatus

    #     orcid_info, orcid_infoStatus, last_updated = get_info_from_orcid(person_id)
    #     if not orcid_info:
    #         orcid_info = {}
    #     status = status and orcid_infoStatus

    #     gboxstatus = self.person_id
    #     if status:
    #         gboxstatus = 'noAjax'
    #     req.write('<script type="text/javascript">var gBOX_STATUS = "%s" </script>' % (gboxstatus))
    #     req.write(webauthorprofile_templates.tmpl_author_page(pubs, \
    #                                     selfpubs, authorname, totaldownloads, \
    #                                     author_aff_pubs, kwtuples, \
    #                                     fieldtuples, coauthors, db_names_dict, \
    #                                     person_link, bibauthorid_data, \
    #                                     summarize_records, pubs_per_year, \
    #                                     hepdict, collab, orcid_info, ln, beval, \
    #                                     oldest_cache_date, recompute_allowed))


    # def new_create_authorpage_websearch(self, req, form, person_id, ln='en', expire_cache=False):

    #     if CFG_WEBAUTHORPROFILE_USE_BIBAUTHORID:
    #         if person_id < 0:
    #             return ("Critical Error. PersonID should never be less than 0!")

    #     webauthorprofile_templates.new_tmpl_author_name_variants_box()
    #     webauthorprofile_templates.new_tmpl_papers_with_self_papers_box()
    #     webauthorprofile_templates.new_tmpl_keyword_box()
    #     webauthorprofile_templates.new_tmpl_fieldcode_box()
    #     webauthorprofile_templates.new_tmpl_affiliations_box()
    #     webauthorprofile_templates.new_tmpl_coauthor_box()
    #     webauthorprofile_templates.new_tmpl_numpaperstitle()
    #     webauthorprofile_templates.new_tmpl_authornametitle()
    #     webauthorprofile_templates.new_tmpl_citations_box()
    #     webauthorprofile_templates.new_tmpl_graph_box()
    #     webauthorprofile_templates.new_tmpl_hepnames()
    #     webauthorprofile_templates.new_tmpl_collab_box()
    #     webauthorprofile_templates.new_tmpl_orcid_info_box()

    #     self.create_authorpage_name_variants(self,  req, form, person_id, expire_cache)

    #     self.create_authorpage_combined_papers(self,  req, form, person_id, expire_cache)

    #     self.create_authorpage_keywords(self,  req, form, person_id, expire_cache)

    #     self.create_authorpage_fieldcodes(self,  req, form, person_id, expire_cache)

    #     self.create_authorpage_affiliations(self,  req, form, person_id, expire_cache)

    #     self.create_authorpage_coauthors(self,  req, form, person_id, expire_cache)

    #     self.create_authorpage_pubs(self,  req, form, person_id, expire_cache)

    #     self.create_authorpage_authors_pubs(self,  req, form, person_id, expire_cache)

    #     self.create_authorpage_citations(self,  req, form, person_id, expire_cache)

    #     self.create_authorpage_pubs_graph(self,  req, form, person_id, expire_cache)

    #     self.create_authorpage_hepdata(self,  req, form, person_id, expire_cache)

    #     self.create_authorpage_collaborations(self,  req, form, person_id, expire_cache)

    #     self.create_authorpage_orcid_info(self,  req, form, person_id, expire_cache)


    def create_authorpage_websearch(self, req, form, person_id, ln='en', expire_cache=False):
        if CFG_WEBAUTHORPROFILE_USE_BIBAUTHORID:
            if person_id < 0:
                return ("Critical Error. PersonID should never be less than 0!")

        # last_updated_list = []
        # lu = last_updated_list.append

        # pubs, pubsStatus, last_updated = get_pubs(person_id)
        # if not pubs:
        #     pubs = []
        # lu(last_updated)

        # selfpubs, selfpubsStatus, last_updated = get_self_pubs(person_id)
        # if not selfpubs:
        #     selfpubs = []
        # lu(last_updated)

        # namesdict, namesdictStatus, last_updated = get_person_names_dicts(person_id)
        # if not namesdict:
        #     namesdict = {}

        # try:
        #     authorname = namesdict['longest']
        #     db_names_dict = namesdict['db_names_dict']
        # except (IndexError, KeyError):
        #     authorname = 'None'
        #     db_names_dict = {}
        # lu(last_updated)

        # #author_aff_pubs, author_aff_pubsStatus = (None, None)
        # author_aff_pubs, author_aff_pubsStatus, last_updated = get_institute_pubs(person_id)
        # if not author_aff_pubs:
        #     author_aff_pubs = {}
        # lu(last_updated)

        # coauthors, coauthorsStatus, last_updated = get_coauthors(person_id)
        # if not coauthors:
        #     coauthors = {}
        # lu(last_updated)

        # summarize_records, summarize_recordsStatus, last_updated = get_summarize_records(person_id)
        # if not summarize_records:
        #     summarize_records = 'None'
        # lu(last_updated)

        # pubs_per_year, pubs_per_yearStatus, last_updated = get_pubs_per_year(person_id)
        # if not pubs_per_year:
        #     pubs_per_year = {}
        # lu(last_updated)

        # totaldownloads, totaldownloadsStatus, last_updated = get_total_downloads(person_id)
        # if not totaldownloads:
        #     totaldownloads = 0
        # lu(last_updated)

        # kwtuples, kwtuplesStatus, last_updated = get_kwtuples(person_id)
        # if kwtuples:
        #     pass
        #     # kwtuples = kwtuples[0:MAX_KEYWORD_LIST]
        # else:
        #     kwtuples = []
        # lu(last_updated)

        # fieldtuples, fieldtuplesStatus, last_updated = get_fieldtuples(person_id)
        # if fieldtuples:
        #     pass
        #     # fieldtuples = fieldtuples[0:MAX_FIELDCODE_LIST]
        # else:
        #     fieldtuples = []
        # lu(last_updated)

        # collab, collabStatus, last_updated = get_collabtuples(person_id)
        # lu(last_updated)

        # person_link, person_linkStatus, last_updated = get_veryfy_my_pubs_list_link(person_id)
        # if not person_link or not person_linkStatus:
        #     bibauthorid_data = {"is_baid": True, "pid":person_id, "cid": None}
        #     person_link = str(person_id)
        # else:
        #     bibauthorid_data = {"is_baid": True, "pid":person_id, "cid": person_link}
        # lu(last_updated)

        # hepdict, hepdictStatus, last_updated = get_hepnames_data(person_id)
        # lu(last_updated)

        # orcid_info, orcid_infoStatus, last_updated = get_info_from_orcid(person_id)
        # if not orcid_info:
        #     orcid_info = {}
        # lu(last_updated)


        # recompute_allowed = True

        # oldest_cache_date = min(last_updated_list)
        # delay = datetime.now() - oldest_cache_date
        # if delay > RECOMPUTE_ALLOWED_DELAY:
        #     if expire_cache:
        #         expire_all_cache_for_person(person_id)
        #         return self.create_authorpage_websearch(req, form, person_id, ln, expire_cache=False)
        # else:
        #     recompute_allowed = False

        # req.write("\nPAGE CONTENT START\n")
        # req.write(str(time.time()))
        # eval = [not_empty(x) or y for x, y in
        # beval = [y for _, y in
        #                                        [(authorname, namesdictStatus),
        #                                        (totaldownloads, totaldownloadsStatus),
        #                                        (author_aff_pubs, author_aff_pubsStatus),
        #                                        (kwtuples, kwtuplesStatus),
        #                                        (fieldtuples, fieldtuplesStatus),
        #                                        (coauthors, coauthorsStatus),
        #                                        (db_names_dict, namesdictStatus),
        #                                        (person_link, person_linkStatus),
        #                                        (summarize_records, summarize_recordsStatus),
        #                                        (pubs, pubsStatus),
        #                                        (pubs_per_year, pubs_per_yearStatus),
        #                                        (hepdict, hepdictStatus),
        #                                        (selfpubs, selfpubsStatus),
        #                                        (collab, collabStatus),
        #                                        (orcid_info, orcid_infoStatus)]]
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
            json_response['boxes_info'].update({'authornametitle': {'status':(beval[0] and beval[7] and beval[9]), 'html_content': webauthorprofile_templates.tmpl_authornametitle(authorname, bibauthorid_data, pubs, person_link, ln, loading=not (beval[0] and beval[7] and beval[9]))}})
            json_response['boxes_info'].update({'citations': {'status':(beval[8] and beval[9]), 'html_content': webauthorprofile_templates.tmpl_citations_box(summarize_records, pubs, ln, add_box=False, loading=not (beval[8] and beval[9]))}})
            json_response['boxes_info'].update({'pubs_graph': {'status':beval[10], 'html_content': webauthorprofile_templates.tmpl_graph_box(pubs_per_year, ln, add_box=False, loading=not beval[10])}})
            json_response['boxes_info'].update({'hepdata': {'status':beval[11], 'html_content':webauthorprofile_templates.tmpl_hepnames(hepdict, ln, add_box=False, loading=not beval[11])}})
            json_response['boxes_info'].update({'collaborations': {'status':beval[13], 'html_content': webauthorprofile_templates.tmpl_collab_box(collab, bibauthorid_data, ln, add_box=False, loading=not beval[13])}})
            json_response['boxes_info'].update({'orcid_info': {'status':beval[14], 'html_content': webauthorprofile_templates.tmpl_orcid_info_box(orcid_info, ln, add_box=False, loading=not beval[14])}})


            req.content_type = 'application/json'
            req.write(json.dumps(json_response))
        else:
            gboxstatus = self.person_id
            gpid = self.person_id
            gNumOfWorkers = 3 # todo read it from conf file
            gReqTimeout = 3000
            gPageTimeout = 12000
            oldest_cache_date = min([5,7])
            req.write('<script type="text/javascript">var gBOX_STATUS = "%s";var gPID = "%s"; var gNumOfWorkers= "%s"; var gReqTimeout= "%s"; var gPageTimeout= "%s";</script>'
                % (gboxstatus, gpid, gNumOfWorkers, gReqTimeout, gPageTimeout))
            req.write(webauthorprofile_templates.tmpl_author_page(ln, gpid, oldest_cache_date, True))


    def create_authorpage_websearch_old(self, req, form, person_id, ln='en', expire_cache=False):
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

        summarize_records, summarize_recordsStatus, last_updated = get_summarize_records(person_id)
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

        orcid_info, orcid_infoStatus, last_updated = get_info_from_orcid(person_id)
        if not orcid_info:
            orcid_info = {}
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
                                               (collab, collabStatus),
                                               (orcid_info, orcid_infoStatus)]]
        # not_complete = False in eval
        # req.write(str(eval))

        if form.has_key('jsondata'):
            print 'debug: json part'
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
            json_response['boxes_info'].update({'authornametitle': {'status':(beval[0] and beval[7] and beval[9]), 'html_content': webauthorprofile_templates.tmpl_authornametitle(authorname, bibauthorid_data, pubs, person_link, ln, loading=not (beval[0] and beval[7] and beval[9]))}})
            json_response['boxes_info'].update({'citations': {'status':(beval[8] and beval[9]), 'html_content': webauthorprofile_templates.tmpl_citations_box(summarize_records, pubs, ln, add_box=False, loading=not (beval[8] and beval[9]))}})
            json_response['boxes_info'].update({'pubs_graph': {'status':beval[10], 'html_content': webauthorprofile_templates.tmpl_graph_box(pubs_per_year, ln, add_box=False, loading=not beval[10])}})
            json_response['boxes_info'].update({'hepdata': {'status':beval[11], 'html_content':webauthorprofile_templates.tmpl_hepnames(hepdict, ln, add_box=False, loading=not beval[11])}})
            json_response['boxes_info'].update({'collaborations': {'status':beval[13], 'html_content': webauthorprofile_templates.tmpl_collab_box(collab, bibauthorid_data, ln, add_box=False, loading=not beval[13])}})
            json_response['boxes_info'].update({'orcid_info': {'status':beval[14], 'html_content': webauthorprofile_templates.tmpl_orcid_info_box(orcid_info, ln, add_box=False, loading=not beval[14])}})


            req.content_type = 'application/json'
            req.write(json.dumps(json_response))
        else:
            gboxstatus = self.person_id
            gpid = self.person_id
            if False not in beval:
                gboxstatus = 'noAjax'
            req.write('<script type="text/javascript">var gBOX_STATUS = "%s";var gPID = "%s"; </script>' % (gboxstatus,gpid))
            req.write(webauthorprofile_templates.tmpl_author_page(None, \
                                            None, None, None, \
                                            None, None, \
                                            None, None, None, \
                                            None, None, \
                                            None, None, \
                                            None, None, None, ln, None, \
                                            None, None))
