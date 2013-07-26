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
from invenio.bibauthorid_webapi import get_canonical_id_from_person_id

""" Bibauthorid Web Interface Logic and URL handler. """

# pylint: disable=W0105
# pylint: disable=C0301
# pylint: disable=W0613

from cgi import escape

from pprint import pformat
from operator import itemgetter
import re
import pprint

try:
    from invenio.jsonutils import json, json_unicode_to_utf8, CFG_JSON_AVAILABLE
except:
    CFG_JSON_AVAILABLE = False
    json = None

from invenio.config import CFG_BIBAUTHORID_ENABLED_REMOTE_LOGIN_SYSTEMS,\
    CFG_SITE_URL
from invenio.bibauthorid_config import AID_ENABLED, CLAIMPAPER_ADMIN_ROLE, CLAIMPAPER_USER_ROLE, \
                            PERSON_SEARCH_RESULTS_SHOW_PAPERS_PERSON_LIMIT, \
                            BIBAUTHORID_UI_SKIP_ARXIV_STUB_PAGE, VALID_EXPORT_FILTERS, PERSONS_PER_PAGE, \
                            MAX_NUM_SHOW_PAPERS

from invenio.config import CFG_SITE_LANG, CFG_SITE_URL, CFG_SITE_NAME, CFG_INSPIRE_SITE  # , CFG_SITE_SECURE_URL

from invenio.bibauthorid_name_utils import most_relevant_name
from invenio.webauthorprofile_webinterface import WebAuthorPages
from invenio.webpage import page, pageheaderonly, pagefooteronly
from invenio.messages import gettext_set_language  # , wash_language
from invenio.template import load
from invenio.webinterface_handler import wash_urlargd, WebInterfaceDirectory
from invenio.session import get_session
from invenio.urlutils import redirect_to_url, get_canonical_and_alternates_urls
from invenio.webuser import getUid, page_not_authorized, collect_user_info, set_user_preferences, \
                            email_valid_p, emailUnique, get_email_from_username, get_uid_from_email, \
                            isUserSuperAdmin
from invenio.access_control_admin import acc_find_user_role_actions, acc_get_user_roles, acc_get_role_id
from invenio.search_engine import perform_request_search
from invenio.search_engine_utils import get_fieldvalues

from invenio.bibauthorid_config import CREATE_NEW_PERSON
import invenio.bibauthorid_webapi as webapi
from invenio.bibauthorid_backinterface import update_external_ids_of_authors
from invenio.bibauthorid_dbinterface import defaultdict

TEMPLATE = load('bibauthorid')

class WebInterfaceBibAuthorIDClaimPages(WebInterfaceDirectory):
    '''
    Handles /author/claim pages and AJAX requests.

    Supplies the methods:
        /author/claim/<string>
        /author/claim/action
        /author/claim/claimstub
        /author/claim/export
        /author/claim/generate_autoclaim_data
        /author/claim/merge_profiles_ajax
        /author/claim/search_box_ajax
        /author/claim/tickets_admin
        /author/claim/you -> /author/claim/<string>

        /author/claim/search
    '''
    _exports = ['',
                'action',
                # 'choose_profile',
                'claimstub',
                'export',
                'generate_autoclaim_data',
                # 'help',
                # 'manage_profile',
                # 'merge_profiles',
                'merge_profiles_ajax',
                # 'search',
                'search_box_ajax',
                'tickets_admin',
                'you']

    def _lookup(self, component, path):
        '''
        This handler parses dynamic URLs:
            - /author/profile/1332 shows the page of author with id: 1332
            - /author/profile/100:5522,1431 shows the page of the author
              identified by the bibrefrec: '100:5522,1431'
        '''
        if not component in self._exports:
            return WebInterfaceBibAuthorIDClaimPages(component), path

    def __init__(self, identifier=None):
        '''
        Constructor of the web interface.

        @param identifier: identifier of an author. Can be one of:
            - an author id: e.g. "14"
            - a canonical id: e.g. "J.R.Ellis.1"
            - a bibrefrec: e.g. "100:1442,155"
        @type identifier: str
        '''
        self.person_id = -1   # -1 is a non valid author identifier

        if identifier is None or not isinstance(identifier, str):
            return

        # check if it's a canonical id: e.g. "J.R.Ellis.1"
        pid = int(webapi.get_person_id_from_canonical_id(identifier))
        if pid >= 0:
            self.person_id = pid
            return

        # check if it's an author id: e.g. "14"
        try:
            pid = int(identifier)
            if webapi.author_has_papers(pid):
                self.person_id = pid
                return
        except ValueError:
            pass

        # check if it's a bibrefrec: e.g. "100:1442,155"
        if webapi.is_valid_bibref(identifier):
            pid = int(webapi.get_person_id_from_paper(identifier))
            if pid >= 0:
                self.person_id = pid
                return

    def __call__(self, req, form):
        '''
        Serve the main person page.
        Will use the object's person id to get a person's information.

        @param req: apache request object
        @type req: apache request object
        @param form: POST/GET variables of the request
        @type form: dict

        @return: a full page formatted in HTML
        @rtype: str
        '''
        self._session_bareinit(req)
        argd = wash_urlargd(form, {'ln': (str, CFG_SITE_LANG),
                                   'open_claim': (str, None),
                                   'ticketid': (int, -1),
                                   'verbose': (int, 0)})
        ln = argd['ln']
        req.argd = argd   # needed for perform_req_search
        session = get_session(req)
        ulevel = self.__get_user_role(req)
        uid = getUid(req)

        if self.person_id < 0:
            return redirect_to_url(req, '%s/author/search' % (CFG_SITE_URL))

        if isUserSuperAdmin({'uid': uid}):
            ulevel = 'admin'

        no_access = self._page_access_permission_wall(req, [self.person_id])
        if no_access:
            return no_access

        try:
            pinfo = session['personinfo']
        except KeyError:
            pinfo = dict()
            session['personinfo'] = pinfo

        if 'claim_in_process' not in pinfo:
            pinfo['claim_in_process'] = False

        if argd['open_claim'] is not None:
            pinfo['claim_in_process'] = True

        uinfo = collect_user_info(req)
        uinfo['precached_viewclaimlink'] = pinfo['claim_in_process']
        set_user_preferences(uid, uinfo)

        pinfo['ln'] = ln
        pinfo['ulevel'] = ulevel

        if self.person_id != -1:
            pinfo['claimpaper_admin_last_viewed_pid'] = self.person_id

        if not "ticket" in pinfo:
            pinfo["ticket"] = list()

        rt_ticket_id = argd['ticketid']
        if rt_ticket_id != -1:
            pinfo["admin_requested_ticket_id"] = rt_ticket_id

        session.dirty = True


        content = self._generate_optional_menu(ulevel, req, form)
        content += self._generate_ticket_box(ulevel, req)
        content += self._generate_person_info_box(ulevel, ln)
        content += self._generate_tabs(ulevel, req)
        content += self._generate_footer(ulevel)
        title = self._generate_title(ulevel)
        metaheaderadd = self._scripts() + '\n <meta name="robots" content="nofollow" />'
        body = TEMPLATE.tmpl_person_detail_layout(content)
        webapi.clean_ticket(req)
        
        webapi.history_log_visit(req, 'claim', pid=self.person_id)
        return page(title=title,
                    metaheaderadd=metaheaderadd,
                    body=body,
                    req=req,
                    language=ln)


    def _page_access_permission_wall(self, req, req_pid=None, req_level=None):
        '''
        Display an error page if user not authorized to use the interface.

        @param req: Apache Request Object for session management
        @type req: Apache Request Object
        @param req_pid: Requested person id
        @type req_pid: int
        @param req_level: Request level required for the page
        @type req_level: string
        '''
        session = get_session(req)
        uid = getUid(req)
        pinfo = session["personinfo"]
        uinfo = collect_user_info(req)

        if 'ln' in pinfo:
            ln = pinfo["ln"]
        else:
            ln = CFG_SITE_LANG

        _ = gettext_set_language(ln)
        is_authorized = True
        pids_to_check = []

        if not AID_ENABLED:
            return page_not_authorized(req, text=_("Fatal: Author ID capabilities are disabled on this system."))

        if req_level and 'ulevel' in pinfo and pinfo["ulevel"] != req_level:
            return page_not_authorized(req, text=_("Fatal: You are not allowed to access this functionality."))

        if req_pid and not isinstance(req_pid, list):
            pids_to_check = [req_pid]
        elif req_pid and isinstance(req_pid, list):
            pids_to_check = req_pid

        if (not (uinfo['precached_usepaperclaim']
                  or uinfo['precached_usepaperattribution'])
            and 'ulevel' in pinfo
            and not pinfo["ulevel"] == "admin"):
            is_authorized = False

        if is_authorized and not webapi.user_can_view_CMP(uid):
            is_authorized = False
        if is_authorized and 'ticket' in pinfo:
            for tic in pinfo["ticket"]:
                if 'pid' in tic:
                    pids_to_check.append(tic['pid'])

        if pids_to_check and is_authorized:
            user_pid = webapi.get_pid_from_uid(uid)

            if not uinfo['precached_usepaperattribution']:
                if (not user_pid in pids_to_check
                    and 'ulevel' in pinfo
                    and not pinfo["ulevel"] == "admin"):
                    is_authorized = False

            elif (user_pid in pids_to_check
                  and 'ulevel' in pinfo
                  and not pinfo["ulevel"] == "admin"):
                for tic in list(pinfo["ticket"]):
                    if not tic["pid"] == user_pid:
                        pinfo['ticket'].remove(tic)

        if not is_authorized:
            return page_not_authorized(req, text=_("Fatal: You are not allowed to access this functionality."))
        else:
            return ""


    def _session_bareinit(self, req):
        '''
        Initializes session personinfo entry if none exists
        @param req: Apache Request Object
        @type req: Apache Request Object
        '''
        session = get_session(req)
        uid = getUid(req)
        ulevel = self.__get_user_role(req)

        if isUserSuperAdmin({'uid': uid}):
            ulevel = 'admin'

        if "personinfo" not in session:
            session["personinfo"] = dict()
        pinfo = session["personinfo"]

        if 'ulevel' not in pinfo:
            pinfo['ulevel'] = ulevel
        if 'login_info_message' not in pinfo:
            pinfo["login_info_message"] =None
        if 'merge_info_message' not in pinfo:
            pinfo["merge_info_message"] = None
        if "claimpaper_admin_last_viewed_pid" not in pinfo:
            pinfo["claimpaper_admin_last_viewed_pid"] = -2
        if 'ln' not in pinfo:
            pinfo["ln"] = 'en'
        if 'ticket' not in pinfo:
            pinfo["ticket"] = []
        if 'merge_primary_profile' not in pinfo:
            pinfo["merge_primary_profile"] = None
        if 'merge_profiles' not in pinfo:
            pinfo["merge_profiles"] = []
        session.dirty = True
        if not 'autoclaim' in pinfo:
            # first variable shows if we want to review the failed ones in the profile management page while the other
            # shows if we are creating and try to claim tickets that come from external systems
            # the third shows if we want to checkout the failed
            pinfo['autoclaim'] = dict()
            pinfo['autoclaim']['review_failed']= False 
            pinfo['autoclaim']['begin_autoclaim'] = False
            pinfo['autoclaim']['checkout'] =  True


    def _generate_title(self, ulevel):
        '''
        Generates the title for the specified user permission level.

        @param ulevel: user permission level
        @type ulevel: str

        @return: title
        @rtype: str
        '''
        def generate_title_guest():
            title = 'Attribute papers'
            if self.person_id:
                title = 'Attribute papers for: ' + str(webapi.get_person_redirect_link(self.person_id))
            return title

        def generate_title_user():
            title = 'Attribute papers'
            if self.person_id:
                title = 'Attribute papers (user interface) for: ' + str(webapi.get_person_redirect_link(self.person_id))
            return title

        def generate_title_admin():
            title = 'Attribute papers'
            if self.person_id:
                title = 'Attribute papers (administrator interface) for: ' + str(webapi.get_person_redirect_link(self.person_id))
            return title


        generate_title = {'guest': generate_title_guest,
                          'user': generate_title_user,
                          'admin': generate_title_admin}

        return generate_title[ulevel]()


    def _generate_optional_menu(self, ulevel, req, form):
        '''
        Generates the menu for the specified user permission level.

        @param ulevel: user permission level
        @type ulevel: str
        @param req: apache request object
        @type req: apache request object
        @param form: POST/GET variables of the request
        @type form: dict

        @return: menu
        @rtype: str
        '''
        def generate_optional_menu_guest(req, form):
            argd = wash_urlargd(form, {'ln': (str, CFG_SITE_LANG),
                                       'verbose': (int, 0)})
            menu = TEMPLATE.tmpl_person_menu()

            if "verbose" in argd and argd["verbose"] > 0:
                session = get_session(req)
                pinfo = session['personinfo']
                menu += "\n<pre>" + pformat(pinfo) + "</pre>\n"

            return menu

        def generate_optional_menu_user(req, form):
            argd = wash_urlargd(form, {'ln': (str, CFG_SITE_LANG),
                                       'verbose': (int, 0)})
            menu = TEMPLATE.tmpl_person_menu()

            if "verbose" in argd and argd["verbose"] > 0:
                session = get_session(req)
                pinfo = session['personinfo']
                menu += "\n<pre>" + pformat(pinfo) + "</pre>\n"

            return menu

        def generate_optional_menu_admin(req, form):
            argd = wash_urlargd(form, {'ln': (str, CFG_SITE_LANG),
                                       'verbose': (int, 0)})
            menu = TEMPLATE.tmpl_person_menu_admin(self.person_id)

            if "verbose" in argd and argd["verbose"] > 0:
                session = get_session(req)
                pinfo = session['personinfo']
                menu += "\n<pre>" + pformat(pinfo) + "</pre>\n"

            return menu


        generate_optional_menu = {'guest': generate_optional_menu_guest,
                                  'user': generate_optional_menu_user,
                                  'admin': generate_optional_menu_admin}

        return generate_optional_menu[ulevel](req, form)


    def _generate_ticket_box(self, ulevel, req):
        '''
        Generates the semi-permanent info box for the specified user permission
        level.

        @param ulevel: user permission level
        @type ulevel: str
        @param req: apache request object
        @type req: apache request object

        @return: info box
        @rtype: str
        '''
        def generate_ticket_box_guest(req):
            session = get_session(req)
            pinfo = session['personinfo']
            ticket = pinfo['ticket']
            results = list()
            pendingt = list()
            for t in ticket:
                if 'execution_result' in t:
                    for res in t['execution_result']:
                        results.append(res)
                else:
                    pendingt.append(t)

            box = ""
            if pendingt:
                box += TEMPLATE.tmpl_ticket_box('in_process', 'transaction', len(pendingt))

            if results:
                failed = [messages for status, messages in results if not status]
                if failed:
                    box += TEMPLATE.tmpl_transaction_box('failure', failed)

                successfull = [messages for status, messages in results if status]
                if successfull:
                    box += TEMPLATE.tmpl_transaction_box('success', successfull)

            return box

        def generate_ticket_box_user(req):
            return generate_ticket_box_guest(req)

        def generate_ticket_box_admin(req):
            return generate_ticket_box_guest(req)


        generate_ticket_box = {'guest': generate_ticket_box_guest,
                               'user': generate_ticket_box_user,
                               'admin': generate_ticket_box_admin}

        return generate_ticket_box[ulevel](req)


    def _generate_person_info_box(self, ulevel, ln):
        '''
        Generates the name info box for the specified user permission level.

        @param ulevel: user permission level
        @type ulevel: str
        @param ln: page display language
        @type ln: str

        @return: name info box
        @rtype: str
        '''
        def generate_person_info_box_guest(ln):
            names = webapi.get_person_names_from_id(self.person_id)
            box = TEMPLATE.tmpl_admin_person_info_box(ln, person_id=self.person_id,
                                                      names=names)
            return box

        def generate_person_info_box_user(ln):
            return generate_person_info_box_guest(ln)

        def generate_person_info_box_admin(ln):
            return generate_person_info_box_guest(ln)


        generate_person_info_box = {'guest': generate_person_info_box_guest,
                                    'user': generate_person_info_box_user,
                                    'admin': generate_person_info_box_admin}

        return generate_person_info_box[ulevel](ln)


    def _generate_tabs(self, ulevel, req):
        '''
        Generates the tabs content for the specified user permission level.

        @param ulevel: user permission level
        @type ulevel: str
        @param req: apache request object
        @type req: apache request object

        @return: tabs content
        @rtype: str
        '''
        from invenio.bibauthorid_templates import verbiage_dict as tmpl_verbiage_dict
        from invenio.bibauthorid_templates import buttons_verbiage_dict as tmpl_buttons_verbiage_dict

        def generate_tabs_guest(req):
            links = list()   # ['delete', 'commit','del_entry','commit_entry']
            tabs = ['records', 'repealed', 'review']

            return generate_tabs_admin(req, show_tabs=tabs, ticket_links=links,
                                       open_tickets=list(),
                                       verbiage_dict=tmpl_verbiage_dict['guest'],
                                       buttons_verbiage_dict=tmpl_buttons_verbiage_dict['guest'],
                                       show_reset_button=False)

        def generate_tabs_user(req):
            links = ['delete', 'del_entry']
            tabs = ['records', 'repealed', 'review', 'tickets']

            session = get_session(req)
            pinfo = session['personinfo']
            uid = getUid(req)
            user_is_owner = 'not_owner'
            if pinfo["claimpaper_admin_last_viewed_pid"] == webapi.get_pid_from_uid(uid):
                user_is_owner = 'owner'

            open_tickets = webapi.get_person_request_ticket(self.person_id)
            tickets = list()
            for t in open_tickets:
                owns = False
                for row in t[0]:
                    if row[0] == 'uid-ip' and row[1].split('||')[0] == str(uid):
                        owns = True
                if owns:
                    tickets.append(t)

            return generate_tabs_admin(req, show_tabs=tabs, ticket_links=links,
                                       open_tickets=tickets,
                                       verbiage_dict=tmpl_verbiage_dict['user'][user_is_owner],
                                       buttons_verbiage_dict=tmpl_buttons_verbiage_dict['user'][user_is_owner])

        def generate_tabs_admin(req, show_tabs=['records', 'repealed', 'review', 'comments', 'tickets', 'data'],
                                ticket_links=['delete', 'commit', 'del_entry', 'commit_entry'], open_tickets=None,
                                verbiage_dict=None, buttons_verbiage_dict=None, show_reset_button=True):
            session = get_session(req)
            personinfo = dict()

            try:
                personinfo = session["personinfo"]
            except KeyError:
                return ""

            if 'ln' in personinfo:
                ln = personinfo["ln"]
            else:
                ln = CFG_SITE_LANG

            all_papers = webapi.get_papers_by_person_id(self.person_id, ext_out=True)
            records = [{'recid': paper[0],
                        'bibref': paper[1],
                        'flag': paper[2],
                        'authorname': paper[3],
                        'authoraffiliation': paper[4],
                        'paperdate': paper[5],
                        'rt_status': paper[6],
                        'paperexperiment': paper[7]} for paper in all_papers]
            rejected_papers = [row for row in records if row['flag'] < -1]
            rest_of_papers = [row for row in records if row['flag'] >= -1]
            review_needed = webapi.get_review_needing_records(self.person_id)

            if len(review_needed) < 1:
                if 'review' in show_tabs:
                    show_tabs.remove('review')

            if open_tickets == None:
                open_tickets = webapi.get_person_request_ticket(self.person_id)
            else:
                if len(open_tickets) < 1 and 'tickets' in show_tabs:
                    show_tabs.remove('tickets')

            rt_tickets = None
            if "admin_requested_ticket_id" in personinfo:
                rt_tickets = personinfo["admin_requested_ticket_id"]

            if verbiage_dict is None:
                verbiage_dict = translate_dict_values(tmpl_verbiage_dict['admin'], ln)
            if buttons_verbiage_dict is None:
                buttons_verbiage_dict = translate_dict_values(tmpl_buttons_verbiage_dict['admin'], ln)

            # send data to the template function
            tabs = TEMPLATE.tmpl_admin_tabs(ln, person_id=self.person_id,
                                            rejected_papers=rejected_papers,
                                            rest_of_papers=rest_of_papers,
                                            review_needed=review_needed,
                                            rt_tickets=rt_tickets,
                                            open_rt_tickets=open_tickets,
                                            show_tabs=show_tabs,
                                            ticket_links=ticket_links,
                                            verbiage_dict=verbiage_dict,
                                            buttons_verbiage_dict=buttons_verbiage_dict,
                                            show_reset_button=show_reset_button)

            return tabs

        def translate_dict_values(dictionary, ln):
            def translate_str_values(dictionary, f=lambda x: x):
                translated_dict = dict()
                for key, value in dictionary.iteritems():
                    if isinstance(value, str):
                        translated_dict[key] = f(value)
                    elif isinstance(value, dict):
                        translated_dict[key] = translate_str_values(value, f)
                    else:
                        raise TypeError("Value should be either string or dictionary.")
                return translated_dict

            return translate_str_values(dictionary, f=gettext_set_language(ln))


        generate_tabs = {'guest': generate_tabs_guest,
                         'user': generate_tabs_user,
                         'admin': generate_tabs_admin}

        return generate_tabs[ulevel](req)


    def _generate_footer(self, ulevel):
        '''
        Generates the footer for the specified user permission level.

        @param ulevel: user permission level
        @type ulevel: str

        @return: footer
        @rtype: str
        '''
        def generate_footer_guest():
            return TEMPLATE.tmpl_invenio_search_box()

        def generate_footer_user():
            return generate_footer_guest()

        def generate_footer_admin():
            return generate_footer_guest()


        generate_footer = {'guest': generate_footer_guest,
                           'user': generate_footer_user,
                           'admin': generate_footer_admin}

        return generate_footer[ulevel]()


    def _ticket_dispatch(self, ulevel, req, autoclaim_show_review = False, autoclaim = False):
        '''
        Checks the ticket manipulation permissions for the specified user
        permission level.

        @param ulevel: user permission level
        @type ulevel: str
        @param req: apache request object
        @type req: apache request object
        @return: footer
        @rtype: str
        '''
        def ticket_dispatch_guest(req, autoclaim_show_review = False, autoclaim = False):

            page_info = webapi.manage_tickets(req, autoclaim_show_review, autoclaim)

            if page_info['type'] == 'Submit Attribution':

                body = TEMPLATE.tmpl_bibref_check(page_info['body_params'][0],
                                              page_info['body_params'][1])
                body = TEMPLATE.tmpl_person_detail_layout(body)

                metaheaderadd = self._scripts(kill_browser_cache=True)

                title = _(page_info['title'])

                return page(title=title,
                    metaheaderadd=metaheaderadd,
                    body=body,
                    req=req,
                    language=ln)
            elif page_info['type'] == 'review actions':
                body = TEMPLATE.tmpl_ticket_final_review(req, page_info['body_params'][0],
                                                         page_info['body_params'][1],
                                                         page_info['body_params'][2],
                                                         page_info['body_params'][3], autoclaim)
                body = TEMPLATE.tmpl_person_detail_layout(body)
                metaheaderadd = self._scripts(kill_browser_cache=True)
                title = _(page_info['title'])

                # body = body + '<pre>' + pformat(pinfo) + '</pre>'
                return page(title=title,
                    metaheaderadd=metaheaderadd,
                    body=body,
                    req=req,
                    language=ln)
            else:
                if autoclaim or autoclaim_show_review:
                    # restoring the user opened tickets and leave autoclaim mode
                    webapi.restore_users_open_tickets(req)

                return self._ticket_dispatch_end(req)

        def ticket_dispatch_user(req, autoclaim_show_review = False, autoclaim = False):
            return ticket_dispatch_guest(req, autoclaim)

        def ticket_dispatch_admin(req, autoclaim_show_review = False, autoclaim = False):
            return ticket_dispatch_guest(req, autoclaim)

        ticket_dispatch = {'guest': ticket_dispatch_guest,
                           'user': ticket_dispatch_user,
                           'admin': ticket_dispatch_admin}
        session = get_session(req)
        pinfo = session["personinfo"]

        if 'ln' in pinfo:
            ln = pinfo["ln"]
        else:
            ln = CFG_SITE_LANG

        pinfo['autoclaim']['review_failed'] = autoclaim_show_review
        pinfo['autoclaim']['begin_autoclaim'] = autoclaim
        session.dirty = True

        if autoclaim_show_review and not autoclaim:
            return self._error_page(req, ln,
                            "Fatal: cannot show autoclaim review without autoclaiming.")
        _ = gettext_set_language(ln)

        return ticket_dispatch[ulevel](req, autoclaim_show_review, autoclaim)

    def _ticket_dispatch_end(self, req):
        '''
        The ticket dispatch is finished, redirect to the original page of
        origin or to the last_viewed_pid
        '''
        session = get_session(req)
        pinfo = session["personinfo"]
        self._session_bareinit(req)
        if 'claim_in_process' in pinfo:
            pinfo['claim_in_process'] = False

        if "merge_ticket" in pinfo and pinfo['merge_ticket']:
            pinfo['merge_ticket'] = []

        uinfo = collect_user_info(req)
        uinfo['precached_viewclaimlink'] = True
        uid = getUid(req)
        set_user_preferences(uid, uinfo)

        if "referer" in pinfo and pinfo["referer"]:
            referer = pinfo["referer"]
            del(pinfo["referer"])
            session.dirty = True
            return redirect_to_url(req, referer)

        # if we are coming fromt he autoclaim box we should not redirect and just return to the caller function
        if 'autoclaim' in pinfo and pinfo['autoclaim']['review_failed'] == False and pinfo['autoclaim']['begin_autoclaim'] == True:
            pinfo['autoclaim']['review_failed'] = False
            pinfo['autoclaim']['begin_autoclaim'] = False
            session.dirty = True
        else:
            redirect_page = webapi.history_get_last_visited_url(req, limit_to_page=['manage_profile', 'claim'])

            if not redirect_page:
                redirect_page = webapi.get_fallback_redirect_link(req)
            if 'autoclaim' in pinfo and pinfo['autoclaim']['review_failed'] == True and pinfo['autoclaim']['checkout'] == True:
                redirect_page = '%s/author/claim/action?checkout=True'  % (CFG_SITE_URL,)
                pinfo['autoclaim']['checkout'] = False
                session.dirty = True
            elif not 'manage_profile' in redirect_page:
                pinfo['autoclaim']['review_failed'] = False
                pinfo['autoclaim']['begin_autoclaim'] == False
                pinfo['autoclaim']['checkout'] = True
                session.dirty = True
                redirect_page = '%s/author/claim/%s?open_claim=True'  % (CFG_SITE_URL, webapi.get_person_redirect_link(pinfo["claimpaper_admin_last_viewed_pid"]))
            else:
                pinfo['autoclaim']['review_failed'] = False
                pinfo['autoclaim']['begin_autoclaim'] == False
                pinfo['autoclaim']['checkout'] = True
                session.dirty = True
            return redirect_to_url(req, redirect_page)

#            redirect_link = diary('get_redirect_link', caller='_ticket_dispatch_end', parameters=[('open_claim','True')])
#            return redirect_to_url(req, redirect_link)


    def __get_user_role(self, req):
        '''
        Determines whether a user is guest, user or admin
        '''
        minrole = 'guest'
        role = 'guest'

        if not req:
            return minrole

        uid = getUid(req)

        if not isinstance(uid, int):
            return minrole

        admin_role_id = acc_get_role_id(CLAIMPAPER_ADMIN_ROLE)
        user_role_id = acc_get_role_id(CLAIMPAPER_USER_ROLE)

        user_roles = acc_get_user_roles(uid)

        if admin_role_id in user_roles:
            role = 'admin'
        elif user_role_id in user_roles:
            role = 'user'

        if role == 'guest' and webapi.is_external_user(uid):
            role = 'user'

        return role

    # need review if should be deleted
    def __user_is_authorized(self, req, action):
        '''
        Determines if a given user is authorized to perform a specified action

        @param req: Apache Request Object
        @type req: Apache Request Object
        @param action: the action the user wants to perform
        @type action: string

        @return: True if user is allowed to perform the action, False if not
        @rtype: boolean
        '''
        if not req:
            return False

        if not action:
            return False
        else:
            action = escape(action)

        uid = getUid(req)

        if not isinstance(uid, int):
            return False

        if uid == 0:
            return False

        allowance = [i[1] for i in acc_find_user_role_actions({'uid': uid})
                     if i[1] == action]

        if allowance:
            return True

        return False


    def _scripts(self, kill_browser_cache=False):
        '''
        Returns html code to be included in the meta header of the html page.
        The actual code is stored in the template.

        @return: html formatted Javascript and CSS inclusions for the <head>
        @rtype: string
        '''
        return TEMPLATE.tmpl_meta_includes(kill_browser_cache)


    def _check_user_fields(self, req, form):
        argd = wash_urlargd(
            form,
            {'ln': (str, CFG_SITE_LANG),
             'user_first_name': (str, None),
             'user_last_name': (str, None),
             'user_email': (str, None),
             'user_comments': (str, None)})
        session = get_session(req)
        pinfo = session["personinfo"]
        ulevel = pinfo["ulevel"]
        skip_checkout_faulty_fields = False

        if ulevel in ['user', 'admin']:
            skip_checkout_faulty_fields = True

        if not ("user_first_name_sys" in pinfo and pinfo["user_first_name_sys"]):
            if "user_first_name" in argd and argd['user_first_name']:
                if not argd["user_first_name"] and not skip_checkout_faulty_fields:
                    pinfo["checkout_faulty_fields"].append("user_first_name")
                else:
                    pinfo["user_first_name"] = escape(argd["user_first_name"])

        if not ("user_last_name_sys" in pinfo and pinfo["user_last_name_sys"]):
            if "user_last_name" in argd and argd['user_last_name']:
                if not argd["user_last_name"] and not skip_checkout_faulty_fields:
                    pinfo["checkout_faulty_fields"].append("user_last_name")
                else:
                    pinfo["user_last_name"] = escape(argd["user_last_name"])

        if not ("user_email_sys" in pinfo and pinfo["user_email_sys"]):
            if "user_email" in argd and argd['user_email']:
                if not email_valid_p(argd["user_email"]):
                    pinfo["checkout_faulty_fields"].append("user_email")
                else:
                    pinfo["user_email"] = escape(argd["user_email"])

                if (ulevel == "guest"
                    and emailUnique(argd["user_email"]) > 0):
                    pinfo["checkout_faulty_fields"].append("user_email_taken")
            else:
                pinfo["checkout_faulty_fields"].append("user_email")

        if "user_comments" in argd:
            if argd["user_comments"]:
                pinfo["user_ticket_comments"] = escape(argd["user_comments"])
            else:
                pinfo["user_ticket_comments"] = ""

        session.dirty = True


    def action(self, req, form):
        '''
        Initial step in processing of requests: ticket generation/update.
        Also acts as action dispatcher for interface mass action requests.

        Valid mass actions are:
        - add_external_id: add an external identifier to an author
        - add_missing_external_ids: add missing external identifiers of an author
        - bibref_check_submit:
        - cancel: clean the session (erase tickets and so on)
        - cancel_rt_ticket:
        - cancel_search_ticket:
        - cancel_stage:
        - checkout:
        - checkout_continue_claiming:
        - checkout_remove_transaction:
        - checkout_submit:
        - claim: claim papers for an author
        - commit_rt_ticket:
        - confirm: confirm assignments to an author
        - delete_external_ids: delete external identifiers of an author
        - repeal: repeal assignments from an author
        - reset: reset assignments of an author
        - set_canonical_name: set/swap the canonical name of an author
        - to_other_person: assign a document from an author to another author

        @param req: apache request object
        @type req: apache request object
        @param form: parameters sent via GET or POST request
        @type form: dict

        @return: a full page formatted in HTML
        @return: str
        '''
        self._session_bareinit(req)
        session = get_session(req)
        pinfo = session["personinfo"]
        argd = wash_urlargd(form,
                            {'autoclaim_show_review':(str, None),
                             'canonical_name': (str, None),
                             'existing_ext_ids': (list, None),
                             'ext_id': (str, None),
                             'ext_system': (str, None),
                             'ln': (str, CFG_SITE_LANG),
                             'pid': (int, None),
                             'primary_profile':(str, None),
                             'search_param': (str, None),
                             'rt_action': (str, None),
                             'rt_id': (int, None),
                             'selection': (list, None),

                             # permitted actions
                             'add_external_id': (str, None),
                             'add_missing_external_ids': (str, None),
                             'associate_profile': (str, None),
                             'bibref_check_submit': (str, None),
                             'cancel': (str, None),
                             'cancel_merging': (str, None),
                             'cancel_rt_ticket': (str, None),
                             'cancel_search_ticket': (str, None),
                             'cancel_stage': (str, None),
                             'checkout': (str, None),
                             'checkout_continue_claiming': (str, None),
                             'checkout_remove_transaction': (str, None),
                             'checkout_submit': (str, None),
                             'claim': (str, None),
                             'commit_rt_ticket': (str, None),
                             'confirm': (str, None),
                             'delete_external_ids': (str, None),
                             'merge': (str, None),
                             'repeal': (str, None),
                             'reset': (str, None),
                             'send_message': (str, None),
                             'set_canonical_name': (str, None),
                             'to_other_person': (str, None)})

        ulevel = pinfo["ulevel"]
        ticket = pinfo["ticket"]
        uid = getUid(req)
        ln = argd['ln']
        action = None

        permitted_actions = ['add_external_id',
                             'add_missing_external_ids',
                             'associate_profile',
                             'bibref_check_submit',
                             'cancel',
                             'cancel_merging',
                             'cancel_rt_ticket',
                             'cancel_search_ticket',
                             'cancel_stage',
                             'checkout',
                             'checkout_continue_claiming',
                             'checkout_remove_transaction',
                             'checkout_submit',
                             'claim',
                             'commit_rt_ticket',
                             'confirm',
                             'delete_external_ids',
                             'merge',
                             'repeal',
                             'reset',
                             'send_message',
                             'set_canonical_name',
                             'to_other_person']

        for act in permitted_actions:
            # one action (the most) is enabled in the form
            if argd[act] is not None:
                action = act

        no_access = self._page_access_permission_wall(req, None)
        if no_access and action not in ["claim"]:
            return no_access

        # incomplete papers (incomplete paper info or other problems) trigger action function without user's interference
        # in order to fix those problems and claim papers or remove them from the ticket
        if (action is None
             and "bibref_check_required" in pinfo
             and pinfo["bibref_check_required"]):

            if "bibref_check_reviewed_bibrefs" in pinfo:
                del(pinfo["bibref_check_reviewed_bibrefs"])
                session.dirty = True

            return self._ticket_dispatch(ulevel, req, pinfo['autoclaim']['review_failed'], pinfo['autoclaim']['begin_autoclaim'])

        def add_external_id():
            if argd['pid'] > -1:
                pid = argd['pid']
            else:
                return self._error_page(req, ln,
                            "Fatal: cannot add external id to unknown person")

            if argd['ext_system'] is not None:
                ext_sys = argd['ext_system']
            else:
                return self._error_page(req, ln,
                            "Fatal: cannot add an external id without specifying the system")

            if argd['ext_id'] is not None:
                ext_id = argd['ext_id']
            else:
                return self._error_page(req, ln,
                            "Fatal: cannot add a custom external id without a suggestion")

            userinfo = "%s||%s" % (uid, req.remote_ip)
            webapi.add_person_external_id(pid, ext_sys, ext_id, userinfo)

            return redirect_to_url(req, "%s/author/manage_profile/%s" % (CFG_SITE_URL, webapi.get_person_redirect_link(pid)))

        def add_missing_external_ids():
            if argd['pid'] > -1:
                pid = argd['pid']
            else:
                return self._error_page(req, ln,
                            "Fatal: cannot recompute external ids for an unknown person")

            update_external_ids_of_authors([pid], overwrite=False)

            return redirect_to_url(req, "%s/author/manage_profile/%s" % (CFG_SITE_URL, webapi.get_person_redirect_link(pid)))

        def associate_profile():
            ### TO DOOOO
            pid_in_cookie = 10
            print repr(argd)
            if 'pid' in argd:
                try:
                    pid = int(argd['pid'])
                except ValueError:
                    return self._error_page(req, ln,
                            "Fatal: cannot associate profile without a person id.")
            else:
                return self._error_page(req, ln,
                        "Fatal: cannot associate profile without a person id.")


            uid = getUid(req)

            pid, profile_claimed = webapi.claim_profile(uid, pid)

            redirect_pid = pid

            if profile_claimed:
                pinfo["login_info_message"] = "confirm_success"
                session.dirty = True
                redirect_to_url(req, '%s/author/manage_profile/%s' % (CFG_SITE_URL, redirect_pid))
            else:
                param=''
                if 'search_param' in argd and argd['search_param']:
                    param = '&search_param=' + argd['search_param']
                redirect_to_url(req, '%s/author/choose_profile?failed=%s%s' % (CFG_SITE_URL, True, param))

        def bibref_check_submit():
            pinfo["bibref_check_reviewed_bibrefs"] = list()
            add_rev = pinfo["bibref_check_reviewed_bibrefs"].append

            if ("bibrefs_auto_assigned" in pinfo
                 or "bibrefs_to_confirm" in pinfo):
                person_reviews = list()

                if ("bibrefs_auto_assigned" in pinfo
                     and pinfo["bibrefs_auto_assigned"]):
                    person_reviews.append(pinfo["bibrefs_auto_assigned"])

                if ("bibrefs_to_confirm" in pinfo
                     and pinfo["bibrefs_to_confirm"]):
                    person_reviews.append(pinfo["bibrefs_to_confirm"])

                for ref_review in person_reviews:
                    for person_id in ref_review:
                        for bibrec in ref_review[person_id]["bibrecs"]:
                            rec_grp = "bibrecgroup%s" % bibrec
                            elements = list()

                            if rec_grp in form:
                                if isinstance(form[rec_grp], str):
                                    elements.append(form[rec_grp])
                                elif isinstance(form[rec_grp], list):
                                    elements += form[rec_grp]
                                else:
                                    continue

                                for element in elements:
                                    test = element.split("||")

                                    if test and len(test) > 1 and test[1]:
                                        tref = test[1] + "," + str(bibrec)
                                        tpid = webapi.wash_integer_id(test[0])

                                        if (webapi.is_valid_bibref(tref)
                                             and tpid > -1):
                                            add_rev(element + "," + str(bibrec))
            session.dirty = True

            return self._ticket_dispatch(ulevel, req, pinfo['autoclaim']['review_failed'], pinfo['autoclaim']['begin_autoclaim'])

        def cancel():
            self.__session_cleanup(req)

            return self._ticket_dispatch_end(req)

        def cancel_merging():
            self._session_bareinit(req)
            session = get_session(req)
            pinfo = session['personinfo']
            pinfo["merge_primary_profile"] = None
            pinfo["merge_profiles"] = []
            session.dirty = True
            redirect_page = webapi.get_marked_visit_link(req)
            webapi.reset_marked_visit_link(req)
            if not redirect_page:
                redirect_page = webapi.history_get_last_visited_url(req, limit_to_page=['manage_profile'])

            if not redirect_page:
                redirect_page = webapi.get_fallback_redirect_link(req)
            return redirect_to_url(req, redirect_page)

        def cancel_rt_ticket():
            if argd['selection'] is not None:
                bibrefs = argd['selection']
            else:
                return self._error_page(req, ln,
                            "Fatal: cannot cancel unknown ticket")

            if argd['pid'] > -1:
                pid = argd['pid']
            else:
                return self._error_page(req, ln,
                            "Fatal: cannot cancel unknown ticket")

            if argd['rt_id'] is not None and argd['rt_action'] is not None:
                rt_id = argd['rt_id']
                rt_action = argd['rt_action']

                for bibref in bibrefs:
                    self._cancel_transaction_from_rt_ticket(rt_id, pid, rt_action, bibref)

                    return redirect_to_url(req, "%s/author/claim/%s" % (CFG_SITE_URL, webapi.get_person_redirect_link(pid)))

            return self._cancel_rt_ticket(req, bibrefs[0], pid)

        def cancel_search_ticket():
            if 'search_ticket' in pinfo:
                del(pinfo['search_ticket'])
            session.dirty = True

#            check with sam
            if "claimpaper_admin_last_viewed_pid" in pinfo:
                pid = pinfo["claimpaper_admin_last_viewed_pid"]

                return redirect_to_url(req, "%s/author/claim/%s" % (CFG_SITE_URL, webapi.get_person_redirect_link(pid)))

#            redirect_link = diary('get_redirect_link', caller = 'cancel_search_ticket')
#            return redirect_to_url(req, redirect_link)

            return self.search(req, form)

        def cancel_stage():
            if 'bibref_check_required' in pinfo:
                del(pinfo['bibref_check_required'])

            if 'bibrefs_auto_assigned' in pinfo:
                del(pinfo['bibrefs_auto_assigned'])

            if 'bibrefs_to_confirm' in pinfo:
                del(pinfo['bibrefs_to_confirm'])

            for tt in [row for row in ticket if 'incomplete' in row]:
                ticket.remove(tt)

            session.dirty = True

            return self._ticket_dispatch_end(req)

        def checkout():
            return self._ticket_dispatch(ulevel, req, pinfo['autoclaim']['review_failed'], pinfo['autoclaim']['begin_autoclaim'])
            # return self._ticket_final_review(req)

        def checkout_continue_claiming():
            pinfo["checkout_faulty_fields"] = list()
            self._check_user_fields(req, form)

            return self._ticket_dispatch_end(req)

        def checkout_remove_transaction():
            bibref = argd['checkout_remove_transaction']

            if webapi.is_valid_bibref(bibref):
                for rmt in [row for row in ticket if row["bibref"] == bibref]:
                    ticket.remove(rmt)

            pinfo["checkout_confirmed"] = False
            session.dirty = True
            return self._ticket_dispatch(ulevel, req,pinfo['autoclaim']['review_failed'], pinfo['autoclaim']['begin_autoclaim'])
            # return self._ticket_final_review(req)

        def checkout_submit():
            pinfo["checkout_faulty_fields"] = list()
            self._check_user_fields(req, form)

            if not ticket:
                pinfo["checkout_faulty_fields"].append("tickets")

            pinfo["checkout_confirmed"] = True
            if pinfo["checkout_faulty_fields"]:
                pinfo["checkout_confirmed"] = False

            session.dirty = True

            return self._ticket_dispatch(ulevel, req, pinfo['autoclaim']['review_failed'], pinfo['autoclaim']['begin_autoclaim'])
            # return self._ticket_final_review(req)

        def claim():
            if argd['selection'] is not None:
                bibrefs = argd['selection']
            else:
                return self._error_page(req, ln,
                            "Fatal: cannot create ticket without any bibrefrec")

            if action == 'claim':
                return self._ticket_open_claim(req, bibrefs, ln)
            elif action == 'to_other_person':
                return self._ticket_open_assign_to_other_person(req, bibrefs, form)

        def commit_rt_ticket():
            if argd['selection'] is not None:
                bibref = argd['selection']
            else:
                return self._error_page(req, ln,
                            "Fatal: cannot cancel unknown ticket")

            if argd['pid'] > -1:
                pid = argd['pid']
            else:
                return self._error_page(req, ln,
                            "Fatal: cannot cancel unknown ticket")

            return self._commit_rt_ticket(req, bibref[0], pid)

        def confirm_repeal_reset():
            if 'pid' in argd and argd['pid']:
                pid = argd['pid']
            else:
                return self._error_page(req, ln,
                                        "Fatal: cannot create ticket without a person id!")
            bibrefs = None
            autoclaim_show_review = False
            #assert False, ('%s %s') % ('autoclaim_show_review' in argd, argd['autoclaim_show_review'])
            autoclaim = False
            if ('selection' in argd and argd['selection'] and len(argd['selection']) > 0):
                bibrefs = argd['selection']
            elif 'autoclaim_show_review' in argd and argd['autoclaim_show_review']:
                autoclaim_show_review = True
                autoclaim = True
            else:
                if pid == CREATE_NEW_PERSON:
                    return self._error_page(req, ln,
                                        "Fatal: Please select a paper to assign to the new person first!")
                else:
                    return self._error_page(req, ln,
                                        "Fatal: cannot create ticket without any paper selected!")
            if 'rt_id' in argd and argd['rt_id']:
                rt_id = argd['rt_id']

                for bibref in bibrefs:
                    self._cancel_transaction_from_rt_ticket(rt_id, pid, action, bibref)

            if bibrefs:
                webapi.add_tickets(req, pid, bibrefs, action)

            if 'search_ticket' in pinfo:
                del(pinfo['search_ticket'])

#            # speak with sam
#            # start ticket processing chain
#            pinfo["claimpaper_admin_last_viewed_pid"] = pid

            pinfo['autoclaim']['review_failed'] = autoclaim_show_review
            pinfo['autoclaim']['begin_autoclaim'] = autoclaim
            session.dirty = True
            
            if autoclaim_show_review :
                webapi.store_users_open_tickets(req)
                webapi.restore_incomplete_autoclaim_tickets(req)
            return self._ticket_dispatch(ulevel, req, autoclaim_show_review, autoclaim)
            # return self.perform(req, form)

        def delete_external_ids():
            if argd['pid'] > -1:
                pid = argd['pid']
            else:
                return self._error_page(req, ln,
                            "Fatal: cannot delete external ids from an unknown person")

            if argd['existing_ext_ids'] is not None:
                existing_ext_ids = argd['existing_ext_ids']
            else:
                return self._error_page(req, ln,
                            "Fatal: you must select at least one external id in order to delete it")

            userinfo = "%s||%s" % (uid, req.remote_ip)
            webapi.delete_person_external_ids(pid, existing_ext_ids, userinfo)

            return redirect_to_url(req, "%s/author/manage_profile/%s" % (CFG_SITE_URL, webapi.get_person_redirect_link(pid)))

        def none_action():
            return self._error_page(req, ln,
                        "Fatal: cannot create ticket if no action selected.")

        def merge():
            self._session_bareinit(req)
            session = get_session(req)
            pinfo = session['personinfo']

            if 'primary_profile' in argd and argd['primary_profile']:
                primary_profile = argd['primary_profile']
            else:
                return self._error_page(req, ln,
                                        "Fatal: cannot create ticket without a person id!")
            profiles_to_merge = None

            if ('selection' in argd and argd['selection'] and len(argd['selection']) > 0):
                profiles_to_merge = argd['selection']
            else:
                return self._error_page(req, ln,
                                    "Fatal: cannot create ticket without any profiles selected!")

            primary_profile = webapi.get_person_id_from_canonical_id(primary_profile)
            profiles_to_merge = [webapi.get_person_id_from_canonical_id(profile) for profile in profiles_to_merge]

            uid = getUid(req)
            user_pid = webapi.get_pid_from_uid(uid)
            is_admin = False

            if "ulevel" in pinfo and pinfo["ulevel"] and pinfo['ulevel'] == 'admin':
                is_admin = True
            
            can_perform_merge = False
            if uid > 0:
                can_perform_merge = webapi.is_merge_allowed([primary_profile] + profiles_to_merge, user_pid, is_admin)

            if not is_admin and not can_perform_merge:
                name = ''
                if "user_last_name" in pinfo:
                    name = pinfo["user_last_name"]

                if "user_first_name" in pinfo:
                    name += pinfo["user_first_name"]

                email = ''
                if "user_email" in pinfo:
                    email = pinfo["user_email"]

                selection_string = "&selection=".join(argd['selection'])
                userinfo = {'uid-ip': "userid: %s (from %s)" % (uid, req.remote_ip),
                            'name': name,
                            'email': email,
                            'merge link': '%s/author/merge_profiles?primary_profile=%s&selection=%s' %(CFG_SITE_URL, argd['primary_profile'], selection_string)}
                webapi.create_request_message(userinfo, subj = 'Merge profiles request')
                pinfo["merge_primary_profile"] = None
                pinfo["merge_profiles"] = []
                redirect_page = webapi.get_marked_visit_link(req)
                webapi.reset_marked_visit_link(req)
                # TO DO show message send error
                if not redirect_page:
                    redirect_page = webapi.history_get_last_visited_url(req, limit_to_page=['manage_profile'])
    
                if not redirect_page:
                    redirect_page = webapi.get_fallback_redirect_link(req)

                pinfo["merge_info_message"] = "confirm_ticket"
                
            elif is_admin and not can_perform_merge:
                pinfo["merge_info_message"] = "confirm_failure"
                redirect_page = '%s/author/merge_profiles?primary_profile=%s&selection=%s' % (CFG_SITE_URL, argd['primary_profile'], '&selection'.join(argd['selection']))
            else:
                pinfo["merge_info_message"] = "confirm_success"
                webapi.merge_profiles(primary_profile, profiles_to_merge)
                pinfo["merge_primary_profile"] = None
                pinfo["merge_profiles"] = []
                webapi.reset_marked_visit_link(req)
                redirect_page = '%s/author/manage_profile/%s' % (CFG_SITE_URL, webapi.get_canonical_id_from_person_id(primary_profile))

            session.dirty = True
            return redirect_to_url(req, redirect_page)

        def send_message():
            self._session_bareinit(req)
            session = get_session(req)
            pinfo = session['personinfo']
            #pp = pprint.PrettyPrinter(indent=4)
            #session_dump = pp.pprint(pinfo)
            session_dump = str(pinfo)
            name = ''
            name_changed = False
            name_given = ''
            email = ''
            email_changed = False
            email_given = ''
            comment = ''
            last_page_visited = ''

            if "user_last_name" in pinfo:
                name = pinfo["user_last_name"]

            if "user_first_name" in pinfo:
                name += pinfo["user_first_name"]
            name = name.rstrip()

            if "user_email" in pinfo:
                email = pinfo["user_email"]
            email = email.rstrip()

            if 'Name' in form:
                if not name:
                    name = form['Name']
                elif name != form['Name']:
                    name_given = form['Name']
                    name_changed = True
                name = name.rstrip()

            if 'E-mail'in form:
                if not email:
                    email = form['E-mail']
                elif name != form['E-mail']:
                    email_given = form['E-mail']
                    email_changed = True
                email = email.rstrip()

            if 'Comment' in form:
                comment = form['Comment']
                comment = comment.rstrip()


            if not name or not comment or not email:
                redirect_to_url(req, '%s/author/help?incomplete_params=%s' % (CFG_SITE_URL, True))
            if 'last_page_visited' in form:
                last_page_visited = form['last_page_visited']

            uid = getUid(req)
            userinfo = {'uid-ip': "userid: %s (from %s)" % (uid, req.remote_ip),
                        'name': name,
                        'email': email,
                        'comment': comment,
                        'last_page_visited': last_page_visited,
                        'session_dump': session_dump,
                        'name_given': name_given,
                        'email_given': email_given,
                        'name_changed': name_changed,
                        'email_changed': email_changed}

            webapi.create_request_message(userinfo)

        def set_canonical_name():
            if argd['pid'] > -1:
                pid = argd['pid']
            else:
                return self._error_page(req, ln,
                            "Fatal: cannot set canonical name to unknown person")

            if argd['canonical_name'] is not None:
                cname = argd['canonical_name']
            else:
                return self._error_page(req, ln,
                            "Fatal: cannot set a custom canonical name without a suggestion")

            userinfo = "%s||%s" % (uid, req.remote_ip)
            if webapi.is_valid_canonical_id(cname):
                webapi.swap_person_canonical_name(pid, cname, userinfo)
            else:
                webapi.update_person_canonical_name(pid, cname, userinfo)

            return redirect_to_url(req, "%s/author/claim/%s%s" % (CFG_SITE_URL, webapi.get_person_redirect_link(pid), '#tabData'))

        action_functions = {'add_external_id': add_external_id,
                            'add_missing_external_ids': add_missing_external_ids,
                            'associate_profile': associate_profile,
                            'bibref_check_submit': bibref_check_submit,
                            'cancel': cancel,
                            'cancel_merging': cancel_merging,
                            'cancel_rt_ticket': cancel_rt_ticket,
                            'cancel_search_ticket': cancel_search_ticket,
                            'cancel_stage': cancel_stage,
                            'checkout': checkout,
                            'checkout_continue_claiming': checkout_continue_claiming,
                            'checkout_remove_transaction': checkout_remove_transaction,
                            'checkout_submit': checkout_submit,
                            'claim': claim,
                            'commit_rt_ticket': commit_rt_ticket,
                            'confirm': confirm_repeal_reset,
                            'delete_external_ids': delete_external_ids,
                            'merge': merge,
                            'repeal': confirm_repeal_reset,
                            'reset': confirm_repeal_reset,
                            'send_message': send_message,
                            'set_canonical_name': set_canonical_name,
                            'to_other_person': claim,
                            None: none_action}

        return action_functions[action]()


    def _ticket_open_claim(self, req, bibrefs, ln):
        '''
        Generate page to let user choose how to proceed

        @param req: Apache Request Object
        @type req: Apache Request Object
        @param bibrefs: list of record IDs to perform an action on
        @type bibrefs: list of int
        @param ln: language to display the page in
        @type ln: string
        '''
        session = get_session(req)
        uid = getUid(req)
        uinfo = collect_user_info(req)
        pinfo = session["personinfo"]

        if 'ln' in pinfo:
            ln = pinfo["ln"]
        else:
            ln = CFG_SITE_LANG

        _ = gettext_set_language(ln)
        no_access = self._page_access_permission_wall(req)
        session.dirty = True
        pid = -1
        search_enabled = True

        if not no_access and uinfo["precached_usepaperclaim"]:
            tpid = webapi.get_pid_from_uid(uid)

            if tpid > -1:
                pid = tpid

        last_viewed_pid = False
        if (not no_access
            and "claimpaper_admin_last_viewed_pid" in pinfo
            and pinfo["claimpaper_admin_last_viewed_pid"]):
            names = webapi.get_person_names_from_id(pinfo["claimpaper_admin_last_viewed_pid"])
            names = sorted([i for i in names], key=lambda k: k[1], reverse=True)
            if len(names) > 0:
                if len(names[0]) > 0:
                    last_viewed_pid = [pinfo["claimpaper_admin_last_viewed_pid"], names[0][0]]

        if no_access:
            search_enabled = False

        pinfo["referer"] = uinfo["referer"]
        session.dirty = True
        body = TEMPLATE.tmpl_open_claim(bibrefs, pid, last_viewed_pid,
                                        search_enabled=search_enabled)
        body = TEMPLATE.tmpl_person_detail_layout(body)
        title = _('Claim this paper')
        metaheaderadd = self._scripts(kill_browser_cache=True)

        return page(title=title,
            metaheaderadd=metaheaderadd,
            body=body,
            req=req,
            language=ln)


    def _ticket_open_assign_to_other_person(self, req, bibrefs, form):
        '''
        Initializes search to find a person to attach the selected records to

        @param req: Apache request object
        @type req: Apache request object
        @param bibrefs: list of record IDs to consider
        @type bibrefs: list of int
        @param form: GET/POST request parameters
        @type form: dict
        '''
        session = get_session(req)
        pinfo = session["personinfo"]
        pinfo["search_ticket"] = dict()
        search_ticket = pinfo["search_ticket"]
        search_ticket['action'] = 'confirm'
        search_ticket['bibrefs'] = bibrefs
        session.dirty = True
        return self.search(req, form)


    def _cancel_rt_ticket(self, req, tid, pid):
        '''
        deletes an RT ticket
        '''
        webapi.delete_request_ticket(pid, tid)
        return redirect_to_url(req, "%s/author/claim/%s" %
                               (CFG_SITE_URL, webapi.get_person_redirect_link(str(pid))))


    def _cancel_transaction_from_rt_ticket(self, tid, pid, action, bibref):
        '''
        deletes a transaction from an rt ticket
        '''
        webapi.delete_transaction_from_request_ticket(pid, tid, action, bibref)


    def _commit_rt_ticket(self, req, bibref, pid):
        '''
        Commit of an rt ticket: creates a real ticket and commits.
        '''
        session = get_session(req)
        pinfo = session["personinfo"]
        ulevel = pinfo["ulevel"]
        ticket = pinfo["ticket"]

        open_rt_tickets = webapi.get_person_request_ticket(pid)
        tic = [a for a in open_rt_tickets if str(a[1]) == str(bibref)]
        if len(tic) > 0:
            tic = tic[0][0]
        # create temporary ticket
        tempticket = []
        for t in tic:
            if t[0] in ['confirm', 'repeal']:
                tempticket.append({'pid': pid, 'bibref': t[1], 'action': t[0]})

        # check if ticket targets (bibref for pid) are already in ticket
        for t in tempticket:
            for e in list(ticket):
                if e['pid'] == t['pid'] and e['bibref'] == t['bibref']:
                    ticket.remove(e)
            ticket.append(t)
        session.dirty = True
        # start ticket processing chain
        webapi.delete_request_ticket(pid, bibref)

        return self._ticket_dispatch(ulevel, req, pinfo['autoclaim']['review_failed'], pinfo['autoclaim']['begin_autoclaim'])


    def _error_page(self, req, ln=CFG_SITE_LANG, message=None, intro=True):
        '''
        Create a page that contains a message explaining the error.

        @param req: Apache Request Object
        @type req: Apache Request Object
        @param ln: language
        @type ln: string
        @param message: message to be displayed
        @type message: string
        '''
        body = []

        _ = gettext_set_language(ln)

        if not message:
            message = "No further explanation available. Sorry."

        if intro:
            body.append(_("<p>We're sorry. An error occurred while "
                        "handling your request. Please find more information "
                        "below:</p>"))
        body.append("<p><strong>%s</strong></p>" % message)

        return page(title=_("Notice"),
                body="\n".join(body),
                description="%s - Internal Error" % CFG_SITE_NAME,
                keywords="%s, Internal Error" % CFG_SITE_NAME,
                language=ln,
                req=req)


    def __session_cleanup(self, req):
        '''
        Cleans the session from all bibauthorid specific settings and
        with that cancels any transaction currently in progress.

        @param req: Apache Request Object
        @type req: Apache Request Object
        '''
        session = get_session(req)
        try:
            pinfo = session["personinfo"]
        except KeyError:
            return

        if "ticket" in pinfo:
            pinfo['ticket'] = []
        if "search_ticket" in pinfo:
            pinfo['search_ticket'] = dict()

        # clear up bibref checker if it's done.
        if ("bibref_check_required" in pinfo
            and not pinfo["bibref_check_required"]):
            if 'bibrefs_to_confirm' in pinfo:
                del(pinfo['bibrefs_to_confirm'])

            if "bibrefs_auto_assigned" in pinfo:
                del(pinfo["bibrefs_auto_assigned"])

            del(pinfo["bibref_check_required"])

        if "checkout_confirmed" in pinfo:
            del(pinfo["checkout_confirmed"])

        if "checkout_faulty_fields" in pinfo:
            del(pinfo["checkout_faulty_fields"])

        # pinfo['ulevel'] = ulevel
        # pinfo["claimpaper_admin_last_viewed_pid"] = -1
        pinfo["admin_requested_ticket_id"] = -1
        session.dirty = True

    def _generate_search_ticket_box(self, req):
        '''
        Generate the search ticket to remember a pending search for Person
        entities in an attribution process

        @param req: Apache request object
        @type req: Apache request object
        '''
        session = get_session(req)
        pinfo = session["personinfo"]
        search_ticket = None

        if 'search_ticket' in pinfo:
            search_ticket = pinfo['search_ticket']
        if not search_ticket:
            return ''
        else:
            return TEMPLATE.tmpl_search_ticket_box('person_search', 'assign_papers', search_ticket['bibrefs'])

    def search_box(self, query, shown_element_functions):
        pid_list = self._perform_search(query)
        search_results = []
        for pid in pid_list:
            result = defaultdict(list)
            result['pid'] = pid
            result['canonical_id'] = webapi.get_canonical_id_from_person_id(pid)
            result['name_variants'] = webapi.get_person_names_from_id(pid)
            result['external_ids'] = webapi.get_external_ids_from_person_id(pid)
            if 'show_status' in shown_element_functions:
                result['status'] = webapi.is_profile_available(pid)
            search_results.append(result)

        body = TEMPLATE.tmpl_author_search(query, search_results, shown_element_functions)

        body = TEMPLATE.tmpl_person_detail_layout(body)

        return body

    def search(self, req, form):
        '''
        Function used for searching a person based on a name with which the
        function is queried.

        @param req: Apache Request Object
        @type form: dict

        @return: a full page formatted in HTML
        @return: string
        '''
        self._session_bareinit(req)
        session = get_session(req)
        no_access = self._page_access_permission_wall(req)
        shown_element_functions = dict()
        shown_element_functions['show_search_bar'] = TEMPLATE.tmpl_general_search_bar()

        if no_access:
            return no_access

        pinfo = session["personinfo"]
        search_ticket = None
        bibrefs = []

        if 'search_ticket' in pinfo:
            search_ticket = pinfo['search_ticket']
            for r in search_ticket['bibrefs']:
                bibrefs.append(r)

        if search_ticket and "ulevel" in pinfo:
            if pinfo["ulevel"] == "admin":
                shown_element_functions['new_person_gen'] = TEMPLATE.tmpl_assigning_search_new_person_generator(bibrefs)

        body = ''

        if search_ticket:
            shown_element_functions['button_gen'] = TEMPLATE.tmpl_assigning_search_button_generator(bibrefs)
            body = body + self._generate_search_ticket_box(req)

        argd = wash_urlargd(
            form,
            {'ln': (str, CFG_SITE_LANG),
             'verbose': (int, 0),
             'q': (str, None)})

        ln = argd['ln']
        # ln = wash_language(argd['ln'])
        query = None
        title = "Person Search"

        if 'q' in argd:
            if argd['q']:
                query = escape(argd['q'])

        body = body + self.search_box(query, shown_element_functions)
        
        parameter = None
        if query:
            parameter = '?search_param=%s' + query
        webapi.history_log_visit(req, 'search', params = parameter)
        return page(title=title,
                    metaheaderadd=self._scripts(kill_browser_cache=True),
                    body=body,
                    req=req,
                    language=ln)

    def merge_profiles(self, req, form):
        argd = wash_urlargd(
            form,
            {'ln': (str, CFG_SITE_LANG),
             'search_param': (str, ''),
             'primary_profile': (str, None),
             'selection': (list, [])})

        ln = argd['ln']
        # ln = wash_language(argd['ln'])
        search_param = argd['search_param']
        primary_profile = argd['primary_profile']

        self._session_bareinit(req)
        session = get_session(req)
        no_access = self._page_access_permission_wall(req)
        shown_element_functions = dict()

        _ = gettext_set_language(ln)
        title = "Merge Profiles"

        if no_access:
            return no_access

        pinfo = session["personinfo"]
        profiles_to_merge = []

        if not primary_profile:
            return page_not_authorized(req, text=_("This page in not accessible directly."))
        else:
            if pinfo["merge_primary_profile"]:
                primary_profile = pinfo["merge_primary_profile"]
                profiles_to_merge = pinfo["merge_profiles"]
            else:
                # convert pid if exist to canonical ids
                try:
                    primary_profile = int(primary_profile)
                    primary_profile = webapi.get_canonical_id_from_person_id(primary_profile)
                except ValueError:
                    pass
                pinfo["merge_primary_profile"] = primary_profile
                # collect profiles to be merged in primary profile
                profiles = argd['selection']

                # convert pid if exist to canonical ids
                for profile in profiles:
                    try:
                        profile_id = int(profile)
                        profiles_to_merge.remove(profile)
                        profile = webapi.get_canonical_id_from_person_id(profile_id)
                        profiles_to_merge.append(profile)
                    except ValueError:
                        # if canonical id is not valid then skip it
                        if webapi.get_person_id_from_canonical_id(profile) != -1:
                            profiles_to_merge.append(profile)
                pinfo["merge_profiles"] = profiles_to_merge
                session.dirty = True

        webapi.set_marked_visit_link(req, 'manage_profile', pid = webapi.get_person_id_from_canonical_id(primary_profile))
        #shown_element_functions['button_gen'] = TEMPLATE.tmpl_merge_profiles_button_generator(profiles)
        body = ''

        if pinfo["merge_info_message"]:
            message = [pinfo["merge_info_message"]]
            body += TEMPLATE.tmpl_merge_transaction_box('failure', message)
            pinfo["merge_info_message"] = None
            session.dirty = True
        body = body + TEMPLATE.tmpl_merge_ticket_box('person_search', 'merge_profiles', primary_profile, profiles_to_merge)

        # this is a function generating search's bar link and if it should be activated or not
        shown_element_functions['show_search_bar'] = TEMPLATE.tmpl_merge_profiles_search_bar(primary_profile)

        shown_element_functions['button_gen'] = TEMPLATE.merge_profiles_button_generator()
        # show if profile is bound to a user or not
        shown_element_functions['show_status'] = 'True'
        body  = body + self.search_box(search_param, shown_element_functions)
        
        
        req.write('<script type="text/javascript">var gMergeProfile = "%s";var gMergeList = %s </script>' % (primary_profile, profiles_to_merge))

        return page(title=title,
                    metaheaderadd=self._scripts(kill_browser_cache=True),
                    body=body,
                    req=req,
                    language=ln)

    def _perform_search(self, search_param):
        pid_canditates_list = []
        nquery = None
        if search_param:
            if search_param.count(":"):
                try:
                    left, right = search_param.split(":")
                    try:
                        nsearch_param = str(right)
                    except (ValueError, TypeError):
                        try:
                            nsearch_param = str(left)
                        except (ValueError, TypeError):
                            nsearch_param = search_param
                except ValueError:
                    nsearch_param = search_param
            else:
                nsearch_param = search_param

            sorted_results = webapi.search_person_ids_by_name(nsearch_param)

            for result in sorted_results:
                pid_canditates_list.append(result[0])
        return pid_canditates_list

    def merge_profiles_ajax(self, req, form):
        '''
        Function used for handling Ajax requests used in order to add/remove profiles
        in/from the merging profiles list, which is saved in the session.

        @param req: Apache Request Object
        @type req: Apache Request Object
        @param form: Parameters sent via Ajax request
        @type form: dict

        @return: json data
        '''
        # Abort if the simplejson module isn't available
        if not CFG_JSON_AVAILABLE:
            print "Json not configurable"

        # If it is an Ajax request, extract any JSON data.
        ajax_request = False
        # REcent papers request
        if form.has_key('jsondata'):
            json_data = json.loads(str(form['jsondata']))
            # Deunicode all strings (Invenio doesn't have unicode
            # support).
            json_data = json_unicode_to_utf8(json_data)
            ajax_request = True
            json_response = {'resultCode': 0}

        # Handle request.
        if ajax_request:
            req_type = json_data['requestType']
            if req_type == 'addProfile':
                if json_data.has_key('profile'):
                    profile = json_data['profile']
                    if webapi.get_person_id_from_canonical_id(profile) != -1:
                        self._session_bareinit(req)
                        session = get_session(req)
                        profiles_to_merge = session["personinfo"]["merge_profiles"]
                        if profile not in profiles_to_merge:
                            profiles_to_merge.append(profile)
                            session.dirty = True
                            # TODO check access rights and get profile from db
                            json_response.update({'resultCode': 1})
                            json_response.update({'addedPofile': profile})
                        else:
                            json_response.update({'result': 'Error: Profile does not exist'})
                    else:
                        json_response.update({'result': 'Error: Profile was already in the list'})
                else:
                    json_response.update({'result': 'Error: Missing profile'})
            elif req_type == 'removeProfile':
                if json_data.has_key('profile'):
                    profile = json_data['profile']
                    if webapi.get_person_id_from_canonical_id(profile) != -1:
                        self._session_bareinit(req)
                        session = get_session(req)
                        profiles_to_merge = session["personinfo"]["merge_profiles"]
                        if profile in profiles_to_merge:
                            profiles_to_merge.remove(profile)
                            session.dirty = True
                            # TODO check access rights and get profile from db
                            json_response.update({'resultCode': 1})
                            json_response.update({'removedProfile': profile})
                        else:
                            json_response.update({'result': 'Error: Profile was missing already from the list'})
                    else:
                        json_response.update({'result': 'Error: Profile does not exist'})
                else:
                    json_response.update({'result': 'Error: Missing profile'})
            elif req_type == 'setPrimaryProfile':
                if json_data.has_key('profile'):
                    profile = json_data['profile']
                    if webapi.get_person_id_from_canonical_id(profile) != -1:
                        self._session_bareinit(req)
                        session = get_session(req)
                        profiles_to_merge = session["personinfo"]["merge_profiles"]
                        if profile in profiles_to_merge:
                            profiles_to_merge.remove(profile)
                        primary_profile = session["personinfo"]["merge_primary_profile"]
                        if primary_profile not in profiles_to_merge:
                            profiles_to_merge.append(primary_profile)
                        session["personinfo"]["merge_primary_profile"] = profile
                        session.dirty = True
                        json_response.update({'resultCode': 1})
                        json_response.update({'primaryProfile': profile})
                    else:
                        json_response.update({'result': 'Error: Profile was already in the list'})
                else:
                    json_response.update({'result': 'Error: Missing profile'})
            else:
                json_response.update({'result': 'Error: Wrong request type'})
            return json.dumps(json_response)

    def search_box_ajax(self, req, form):
        '''
        Function used for handling Ajax requests used in the search box.

        @param req: Apache Request Object
        @type req: Apache Request Object
        @param form: Parameters sent via Ajax request
        @type form: dict

        @return: json data
        '''
        # Abort if the simplejson module isn't available
        if not CFG_JSON_AVAILABLE:
            print "Json not configurable"

        # If it is an Ajax request, extract any JSON data.
        ajax_request = False
        # REcent papers request
        if form.has_key('jsondata'):
            json_data = json.loads(str(form['jsondata']))
            # Deunicode all strings (Invenio doesn't have unicode
            # support).
            json_data = json_unicode_to_utf8(json_data)
            ajax_request = True
            json_response = {'resultCode': 0}

        # Handle request.
        if ajax_request:
            req_type = json_data['requestType']
            if req_type == 'getPapers':
                if json_data.has_key('personId'):
                    pId = json_data['personId']
                    papers = sorted([[p[0]] for p in webapi.get_papers_by_person_id(int(pId), -1)],

                                          key=itemgetter(0))
                    papers_html = TEMPLATE.tmpl_gen_papers(papers[0:MAX_NUM_SHOW_PAPERS])
                    json_response.update({'result': "\n".join(papers_html)})
                    json_response.update({'totalPapers': len(papers)})
                    json_response.update({'resultCode': 1})
                    json_response.update({'pid': str(pId)})
                else:
                    json_response.update({'result': 'Error: Missing person id'})
            elif req_type == 'getNames':
                if json_data.has_key('personId'):
                    pId = json_data['personId']
                    names = webapi.get_person_names_from_id(int(pId))
                    names_html = TEMPLATE.tmpl_gen_names(names)
                    json_response.update({'result': "\n".join(names_html)})
                    json_response.update({'resultCode': 1})
                    json_response.update({'pid': str(pId)})
            elif req_type =='getIDs':
                if json_data.has_key('personId'):
                    pId = json_data['personId']
                    ids = webapi.get_external_ids_from_person_id(int(pId))
                    ids_html = TEMPLATE.tmpl_gen_ext_ids(ids)
                    json_response.update({'result': "\n".join(ids_html)})
                    json_response.update({'resultCode': 1})
                    json_response.update({'pid': str(pId)})
            elif req_type == 'isProfileClaimed':
                if json_data.has_key('personId'):
                    pId = json_data['personId']
                    isClaimed = webapi.get_uid_from_personid(pId)
                    if isClaimed != -1:
                        json_response.update({'resultCode': 1})
                    json_response.update({'pid': str(pId)})
            else:
                json_response.update({'result': 'Error: Wrong request type'})
            return json.dumps(json_response)


    def claimstub(self, req, form):
        '''
        Generate stub page before claiming process

        @param req: Apache request object
        @type req: Apache request object
        @param form: GET/POST request params
        @type form: dict
        '''
        argd = wash_urlargd(
            form,
            {'ln': (str, CFG_SITE_LANG),
             'person': (str, '')})

        ln = argd['ln']
        # ln = wash_language(argd['ln'])
        _ = gettext_set_language(ln)

        person = '-1'
        if 'person' in argd and argd['person']:
            person = argd['person']

        session = get_session(req)
        try:
            pinfo = session["personinfo"]
            if pinfo['ulevel'] == 'admin':
                return redirect_to_url(req, '%s/author/claim/%s?open_claim=True' % (CFG_SITE_URL, person))
        except KeyError:
            pass

        if BIBAUTHORID_UI_SKIP_ARXIV_STUB_PAGE:
            return redirect_to_url(req, '%s/author/claim/%s?open_claim=True' % (CFG_SITE_URL, person))

        body = TEMPLATE.tmpl_claim_stub(person)

        pstr = 'Person ID missing or invalid'
        if person != '-1':
            pstr = person
        title = _('You are going to claim papers for: %s' % pstr)

        return page(title=title,
                    metaheaderadd=self._scripts(kill_browser_cache=True),
                    body=body,
                    req=req,
                    language=ln)


    def choose_profile(self, req, form):
        '''
        Generate SSO landing/choose_profile page

        @param req: Apache request object
        @type req: Apache request object
        @param form: GET/POST request params
        @type form: dict
        '''
        argd = wash_urlargd(
            form,
            {'ln': (str, CFG_SITE_LANG),
             'search_param': (str, None),
             'failed': (str, None)})
        ln = argd['ln']
        search_param = argd['search_param']
        failed = True
        if not argd['failed']:
            failed = False

        _ = gettext_set_language(ln)

        if not CFG_INSPIRE_SITE:
            return page_not_authorized(req, text=_("This page in not accessible directly."))

        ################REMEMBEEERRR##################
        pid_in_cookie = 9

        # login_status checks if the user is logged in and returns a dictionary contain if he is logged in
        # his uid and the external systems that he is logged in through.
        # the dictionary of the following form: {'logged_in': True, 'uid': 2, 'remote_logged_in_systems':['Arxiv', ...]}
        login_info = webapi.login_status(req)

        if 'arXiv' not in login_info['remote_logged_in_systems']:
            return page_not_authorized(req, text=_("This page in not accessible directly."))

        pid = webapi.get_user_pid(login_info['uid'])
        body = TEMPLATE.tmpl_choose_profile(failed)
        if pid != -1:
            redirect_pid = pid
            if pid_in_cookie:
                redirect_pid = pid_in_cookie
            redirect_to_url(req, '%s/author/manage_profile/%s' % (CFG_SITE_URL, str(redirect_pid)))
        else:
            # get name strings and email addresses from SSO/Oauth logins: {'system':{'name':[variant1,...,variantn], 'email':'blabla@bla.bla', 'pants_size':20}}
            remote_login_systems_info = webapi.get_remote_login_systems_info(req, login_info['remote_logged_in_systems'])
            # get union of recids that are associated to the ids from all the external systems: set(inspire_recids_list)
            recids = webapi.get_remote_login_systems_recids(req, login_info['remote_logged_in_systems'])
            # this is the profile with the biggest intersection of papers  so it's more probable that this is the profile the user seeks
            probable_pid = webapi.match_profile(req, recids, remote_login_systems_info)
            probable_pid = 30

            if not search_param and probable_pid > -1 and probable_pid == pid_in_cookie:
                # try to assign the user to the profile he chose. If for some reason the profile is not available we assign him to an empty profile
                redirect_pid, profile_claimed = webapi.claim_profile(login_info['uid'], probable_pid)
                if profile_claimed:
                    redirect_to_url(req, '%s/author/claim/action?associate_profile=True&redirect_pid=%s' % (CFG_SITE_URL, str(redirect_pid)))

            probable_profile_suggestion_info = None
            last_viewed_profile_suggestion_info = None

            if pid_in_cookie > -1 and webapi.is_profile_available(pid_in_cookie):
                # get information about the most probable profile and show it to the user
                last_viewed_profile_suggestion_info = webapi.get_profile_suggestion_info(req, pid_in_cookie)

            if probable_pid > -1 and webapi.is_profile_available(probable_pid):
                # get information about the most probable profile and show it to the user
                probable_profile_suggestion_info = webapi.get_profile_suggestion_info(req, probable_pid)

            if not search_param:
                # we prefil the search with most relevant among the names that we get from external systems
                name_variants = webapi.get_name_variants_list_from_remote_systems_names(remote_login_systems_info)
                search_param = most_relevant_name(name_variants)

            body = body + TEMPLATE.tmpl_welcome_probable_profile_suggestion(probable_profile_suggestion_info, last_viewed_profile_suggestion_info, search_param)

            shown_element_functions = dict()
            shown_element_functions['button_gen'] = TEMPLATE.tmpl_choose_profile_search_button_generator()
            shown_element_functions['new_person_gen'] = TEMPLATE.tmpl_choose_profile_search_new_person_generator()
            shown_element_functions['show_search_bar'] = TEMPLATE.tmpl_choose_profile_search_bar()
            # show if profile is bound to a user or not
            shown_element_functions['show_status'] = 'True'
            # show search results to the user
            body = body + self.search_box(search_param, shown_element_functions)

            title = _('Choose profile')
            return page(title=title,
                        metaheaderadd=self._scripts(kill_browser_cache=True),
                        body=body,
                        req=req,
                        language=ln)

    def manage_profile(self, req, form):
        '''
            Generate SSO landing/author managment page

            @param req: Apache request object
            @type req: Apache request object
            @param form: GET/POST request params
            @type form: dict
        '''

        self._session_bareinit(req)
        session = get_session(req)
        pinfo = session["personinfo"]
        ulevel = None

        if "ulevel" in pinfo:
            ulevel = pinfo['ulevel']

        argd = wash_urlargd(
            form,
            {'ln': (str, CFG_SITE_LANG),
             'pid': (str, None)})

        ln = argd['ln']
        # ln = wash_language(argd['ln'])
        _ = gettext_set_language(ln)

        if not CFG_INSPIRE_SITE or argd['pid'] == None:
            return page_not_authorized(req, text=_("This page in not accessible directly."))

        try:
            person_id = int(argd['pid'])
        except ValueError:
            person_id = webapi.get_person_id_from_canonical_id(argd['pid'])

        if person_id < 0:
            return page_not_authorized(req, text=_("This page in not accessible directly."))            

        # login_status checks if the user is logged in and returns a dictionary contain if he is logged in
        # his uid and the external systems that he is logged in through.
        # the dictionary of the following form: {'logged_in': True, 'uid': 2, 'remote_logged_in_systems':['Arxiv', ...]}

        webapi.history_log_visit(req, 'manage_profile', pid=person_id)
        login_info = webapi.login_status(req)
        title_message = _('Profile Managment')

        # start continuous writing to the browser...
        req.content_type = "text/html"
        req.send_http_header()
        ssl_param = 0

        if req.is_https():
            ssl_param = 1

        req.write(pageheaderonly(req=req, title=title_message, uid=login_info["uid"],
                               language=ln, secure_page_p=ssl_param, metaheaderadd=self._scripts(kill_browser_cache=True)))

        req.write(TEMPLATE.tmpl_welcome_start())

        user_pid = webapi.get_user_pid(login_info['uid'])
        person_data = webapi.get_person_info_by_pid(person_id)
        arxiv_data = self._arxiv_box(login_info, person_id, user_pid)
        orcid_data = self._orcid_box(arxiv_data['login'], person_id, user_pid, ulevel)
        claim_paper_data = self._claim_paper_box(person_id)
        support_data = self._support_box()
        ext_ids_data = self._external_ids_box(person_id, user_pid, ulevel)
        autoclaim_data = self._autoclaim_papers_box(req, person_id, user_pid, login_info['remote_logged_in_systems'])
        merge_data = self._merge_box(person_id)
        # if False not in beval:
        gboxstatus = 'noAjax'
        req.write('<script type="text/javascript">var gPID = "%s"; </script>' % (person_id))
        req.write(TEMPLATE.tmpl_profile_managment(ln, person_data, arxiv_data, orcid_data, claim_paper_data, ext_ids_data, autoclaim_data, support_data, merge_data))
        req.write(pagefooteronly(req=req,language=ln))

    def _arxiv_box(self, login_info, person_id, user_pid):
        arxiv_data = dict()
        arxiv_data['login'] = False
        arxiv_data['view_own_profile'] = False
        arxiv_data['logout_link'] = "mpla.com"
        arxiv_data['logout_text'] = "Logout"
        arxiv_data['login_link'] = "mpla.com"
        arxiv_data['login_text'] = "Login into Inspire through arXiv.org"

        if login_info['logged_in'] and 'arXiv' in login_info['remote_logged_in_systems'] and user_pid != -1:
            arxiv_data['login'] = True
            arxiv_data['user_pid'] = webapi.get_user_pid(login_info['uid'])

            # check if the profile you are logged in is the same with the profile you are
            if user_pid == person_id:
                arxiv_data['view_own_profile'] = True
            else:
                arxiv_data['own_profile_link'] =  "%s/author/manage_profile/%s" % (CFG_SITE_URL, user_pid)
                arxiv_data['own_profile_text'] = "Manage your profile"
        return arxiv_data


    def _orcid_box(self, arxiv_logged_in, person_id, user_pid, ulevel):
        orcid_data = dict()
        orcid_data['arxiv_login'] = arxiv_logged_in
        orcid_data['orcids'] = None
        orcid_data['add_link'] = "mpla.com"
        orcid_data['add_text'] = "Connect an ORCID iD to this profile"
        orcid_data['suggest_link'] = "mpla.com"
        orcid_data['suggest_text'] = "Suggest an ORCID iD for this profile"
        orcid_data['add_power'] = False
        orcid_data['own_profile'] = False
        if person_id == user_pid:
            orcid_data['own_profile'] = True
        if ulevel == "admin":
            orcid_data['add_power'] = True

        orcids = webapi.get_orcids_by_pid(person_id)

        if orcids:
            orcid_data['orcids'] = orcids

        return orcid_data


    def generate_autoclaim_data(self, req, form):
        # Abort if the simplejson module isn't available
        if not CFG_JSON_AVAILABLE:
            print "Json not configurable"

        # If it is an Ajax request, extract any JSON data.
        ajax_request = False
        if form.has_key('jsondata'):
            json_data = json.loads(str(form['jsondata']))
            # Deunicode all strings (Invenio doesn't have unicode
            # support).
            json_data = json_unicode_to_utf8(json_data)
            ajax_request = True
            json_response = {'resultCode': '0'}

        # Handle request.
        if ajax_request:
            if json_data.has_key('personId'):
                person_id = json_data['personId']
                print "debug"
                session = get_session(req)
                pinfo = session["personinfo"]
                ulevel = pinfo["ulevel"]

                autoclaim_data = dict()
                autoclaim_data['hidden'] = False

                login_info = webapi.login_status(req)
                remote_logged_in_systems = login_info['remote_logged_in_systems']
                recids_to_autoclaim = webapi.get_remote_login_systems_recids(req, remote_logged_in_systems)
                autoclaim_data['num_of_claims'] = len(recids_to_autoclaim)
                # get all the ids that arrived from the external systems
                cached_ids_association = webapi.get_cached_id_association(req)

                # external ids and recids should hava a 1 to 1 relation so the dicionary can be inverted and search by recid as a key
                inverted_association = dict((value,key) for key, value in cached_ids_association.items())

                autoclaim_data["link"] = "%s/author/claim/action?confirm=True&pid=%s&autoclaim_show_review=True" % (CFG_SITE_URL, person_id)
                autoclaim_data['text'] = "Review autoclaiming"

                recids_to_autoclaim = [69,70]
                if recids_to_autoclaim:
                    webapi.auto_claim_papers(req, person_id, recids_to_autoclaim)
                    self._ticket_dispatch(ulevel, req, False, True)
                unsuccessfull_recids = webapi.get_stored_incomplete_autoclaim_tickets(req)
                unsuccessfull_recids = [69,70]
                autoclaim_data["num_of_unsuccessfull_recids"] = len(unsuccessfull_recids)
                inverted_association = {69:'arXiv:0901.4101', 70:'arXiv:0901.4102'}
                autoclaim_data['recids_to_external_ids'] = inverted_association
                autoclaim_data['unsuccessfull_recids'] = []

                for recid in unsuccessfull_recids:
                    autoclaim_data['unsuccessfull_recids'].append(recid)

                successfull_recids = list(set(recids_to_autoclaim) - set(unsuccessfull_recids))
                autoclaim_data["num_of_successfull_recids"] = len(successfull_recids)

                for recid in successfull_recids:
                    autoclaim_data['successfull_recids'][recid] = inverted_association[recid]

                data_html = TEMPLATE.tmpl_autoclaim_box(autoclaim_data, ln='en', add_box=False, loading=False)

                json_response.update({'result': data_html})
                json_response.update({'resultCode': '1'})
                json_response.update({'pid': str(person_id)})
            else:
                json_response.update({'result': 'Error: Missing person id'})

        return json.dumps(json_response)

    def _autoclaim_papers_box(self, req, person_id, user_pid, remote_logged_in_systems):
        autoclaim_data = dict()
        autoclaim_data['hidden'] = True
        recids_to_autoclaim = []

        if person_id == user_pid or True:
            recids_to_autoclaim = webapi.get_remote_login_systems_recids(req, remote_logged_in_systems)
            if recids_to_autoclaim or True:
                autoclaim_data['hidden'] = False
                autoclaim_data['num_of_claims'] = len(recids_to_autoclaim)

        # this should be hidden if empty
        # if there are papers that could not be autoclaimed
            # show them and give the chance to the user to claim them by himself
        return autoclaim_data

    def _claim_paper_box(self, person_id):
        #show a link to the publications inside the box
        #remember to add link to /author/claim to return here
        claim_paper_data = dict()
        claim_paper_data['link'] = "%s/author/claim/%s?open_claim=True" % (CFG_SITE_URL, str(webapi.get_canonical_id_from_person_id(person_id)))
        claim_paper_data['text'] = "Verify my publication list"
        return claim_paper_data

    def _support_box(self):
        support_data = dict()
        support_data['help_link'] = "%s/author/help" % (CFG_SITE_URL)
        support_data['help_text'] = "Get help!"
        # report a problem page
        # get help page
        return support_data

    def _merge_box(self, person_id):
        merge_data = dict()
        search_param = webapi.get_canonical_id_from_person_id(person_id)
        name_variants = [element[0] for element in webapi.get_person_names_from_id(person_id)]
        relevant_name = most_relevant_name(name_variants)

        if relevant_name:
            search_param = relevant_name.split(",")[0]

        merge_data['merge_link'] = "%s/author/merge_profiles?search_param=%s&primary_profile=%s" % (CFG_SITE_URL, search_param,
                                                                                                webapi.get_canonical_id_from_person_id(person_id))
        merge_data['merge_text'] = "Merge profiles"
        # report a problem page
        # get help page
        return merge_data

    def _external_ids_box(self, person_id, user_pid, ulevel):
        external_ids_data = dict()
        external_ids_data['ext_ids'] = webapi.get_external_ids_from_person_id(person_id)
        external_ids_data['person_id'] = person_id

        # if the user has permission to add/remove ids, in other words if the profile is his or he is admin
        if person_id == user_pid or ulevel == "admin":
            external_ids_data['add_text'] = 'add external id'
            external_ids_data['add_parameter'] = 'add_external_id'
            external_ids_data['remove_text'] = 'delete selected ids'
            external_ids_data['remove_parameter'] = 'delete_external_ids'
            external_ids_data['add_missing_text'] = 'add missing ids'
            external_ids_data['add_missing_parameter'] = 'add_missing_external_ids'
        else:
            external_ids_data['add_text'] = 'suggest external id to add'
            external_ids_data['add_parameter'] = 'suggest_external_id_to_add'
            external_ids_data['remove_text'] = 'suggest selected ids to delete'
            external_ids_data['remove_parameter'] = 'suggest_external_ids_to_delete'
            external_ids_data['add_missing_text'] = 'suggest missing ids'
            external_ids_data['add_missing_parameter'] = 'suggest_missing_external_ids'
        return external_ids_data

    def tickets_admin(self, req, form):
        '''
        Generate SSO landing/welcome page

        @param req: Apache request object
        @type req: Apache request object
        @param form: GET/POST request params
        @type form: dict
        '''
        self._session_bareinit(req)
        no_access = self._page_access_permission_wall(req, req_level='admin')
        if no_access:
            return no_access

        tickets = webapi.get_persons_with_open_tickets_list()
        tickets = list(tickets)

        for t in list(tickets):
            tickets.remove(t)
            tickets.append([webapi.get_most_frequent_name_from_pid(int(t[0])),
                         webapi.get_person_redirect_link(t[0]), t[0], t[1]])

        body = TEMPLATE.tmpl_tickets_admin(tickets)
        body = TEMPLATE.tmpl_person_detail_layout(body)

        title = 'Open RT tickets'

        return page(title=title,
                    metaheaderadd=self._scripts(),
                    body=body,
                    req=req)

    def help(self,req, form):
        argd = wash_urlargd(
            form,
            {'ln': (str, CFG_SITE_LANG),
             'incomplete_params': (str, None)})

        ln = argd['ln']
        # ln = wash_language(argd['ln'])
        _ = gettext_set_language(ln)

        incomplete_params = argd['incomplete_params']

        if not CFG_INSPIRE_SITE:
            return page_not_authorized(req, text=_("This page in not accessible directly."))

        self._session_bareinit(req)
        session = get_session(req)
        pinfo = session['personinfo']

        name_to_prefill = ''
        if "user_last_name" in pinfo:
            name_to_prefill = pinfo["user_last_name"]

        if "user_first_name" in pinfo:
            name_to_prefill += pinfo["user_first_name"]

        email_to_prefill = ''
        if "user_email" in pinfo:
            email_to_prefill = pinfo["user_email"]

        last_page_visited = webapi.history_get_last_visited_url(req)
        body = TEMPLATE.tmpl_message_form(last_page_visited, name_to_prefill, email_to_prefill, incomplete_params)

        title = ''#_('Help!')
        return page(title=title,
                    metaheaderadd=self._scripts(kill_browser_cache=True),
                    body=body,
                    req=req,
                    language=ln)

    def export(self, req, form):
        '''
        Generate JSONized export of Person data

        @param req: Apache request object
        @type req: Apache request object
        @param form: GET/POST request params
        @type form: dict
        '''
        argd = wash_urlargd(
            form,
            {'ln': (str, CFG_SITE_LANG),
             'request': (str, None),
             'userid': (str, None)})

        if not CFG_JSON_AVAILABLE:
            return "500_json_not_found__install_package"

        # session = get_session(req)
        request = None
        userid = None

        if "userid" in argd and argd['userid']:
            userid = argd['userid']
        else:
            return "404_user_not_found"

        if "request" in argd and argd['request']:
            request = argd["request"]

        # find user from ID
        user_email = get_email_from_username(userid)

        if user_email == userid:
            return "404_user_not_found"

        uid = get_uid_from_email(user_email)
        uinfo = collect_user_info(uid)
        # find person by uid
        pid = webapi.get_pid_from_uid(uid)
        # find papers py pid that are confirmed through a human.
        papers = webapi.get_papers_by_person_id(pid, 2)
        # filter by request param, e.g. arxiv
        if not request:
            return "404__no_filter_selected"

        if not request in VALID_EXPORT_FILTERS:
            return "500_filter_invalid"

        if request == "arxiv":
            query = "(recid:"
            query += " OR recid:".join(papers)
            query += ") AND 037:arxiv"
            db_docs = perform_request_search(p=query, rg=0)
            nickmail = ""
            nickname = ""
            db_arxiv_ids = []

            try:
                nickname = uinfo["nickname"]
            except KeyError:
                pass

            if not nickname:
                try:
                    nickmail = uinfo["email"]
                except KeyError:
                    nickmail = user_email

                nickname = nickmail

            db_arxiv_ids = get_fieldvalues(db_docs, "037__a")
            construct = {"nickname": nickname,
                         "claims": ";".join(db_arxiv_ids)}

            jsondmp = json.dumps(construct)

            signature = webapi.sign_assertion("arXiv", jsondmp)
            construct["digest"] = signature

            return json.dumps(construct)


    index = __call__
    me = manage_profile
    you = manage_profile


class WebInterfaceBibAuthorIDManageProfilePages(WebInterfaceDirectory):
    _exports = ['']

    def _lookup(self, component, path):
        '''
        This handler parses dynamic URLs:
            - /author/profile/1332 shows the page of author with id: 1332
            - /author/profile/100:5522,1431 shows the page of the author
              identified by the bibrefrec: '100:5522,1431'
        '''
        if not component in self._exports:
            return WebInterfaceBibAuthorIDManageProfilePages(component), path

    def __init__(self, identifier=None):
        '''
        Constructor of the web interface.

        @param identifier: identifier of an author. Can be one of:
            - an author id: e.g. "14"
            - a canonical id: e.g. "J.R.Ellis.1"
            - a bibrefrec: e.g. "100:1442,155"
        @type identifier: str
        '''
        self.person_id = -1   # -1 is a non valid author identifier

        if identifier is None or not isinstance(identifier, str):
            return

        # check if it's a canonical id: e.g. "J.R.Ellis.1"
        pid = int(webapi.get_person_id_from_canonical_id(identifier))
        if pid >= 0:
            self.person_id = pid
            return

        # check if it's an author id: e.g. "14"
        try:
            pid = int(identifier)
            if webapi.author_has_papers(pid):
                self.person_id = pid
                return
        except ValueError:
            pass

        # check if it's a bibrefrec: e.g. "100:1442,155"
        if webapi.is_valid_bibref(identifier):
            pid = int(webapi.get_person_id_from_paper(identifier))
            if pid >= 0:
                self.person_id = pid
                return

    def __call__(self, req, form):
        '''
            Generate SSO landing/author managment page

            @param req: Apache request object
            @type req: Apache request object
            @param form: GET/POST request params
            @type form: dict
        '''
        temp = WebInterfaceBibAuthorIDClaimPages()
        temp._session_bareinit(req)
        session = get_session(req)
        pinfo = session["personinfo"]
        ulevel = None

        if "ulevel" in pinfo:
            ulevel = pinfo['ulevel']

        argd = wash_urlargd(
            form,
            {'ln': (str, CFG_SITE_LANG),
             'pid': (str, None)})

        ln = argd['ln']
        # ln = wash_language(argd['ln'])
        _ = gettext_set_language(ln)

        if not CFG_INSPIRE_SITE or self.person_id == None:
            return page_not_authorized(req, text=_("This page in not accessible directly."))

        try:
            person_id = int(self.person_id)
        except ValueError:
            person_id = webapi.get_person_id_from_canonical_id(self.person_id)

        if person_id < 0:
            return page_not_authorized(req, text=_("This page in not accessible directly.")) 

        # login_status checks if the user is logged in and returns a dictionary contain if he is logged in
        # his uid and the external systems that he is logged in through.
        # the dictionary of the following form: {'logged_in': True, 'uid': 2, 'remote_logged_in_systems':['Arxiv', ...]}

        webapi.history_log_visit(req, 'manage_profile', pid=person_id)
        login_info = webapi.login_status(req)
        title_message = _('Profile Managment')

        # start continuous writing to the browser...
        req.content_type = "text/html"
        req.send_http_header()
        ssl_param = 0

        if req.is_https():
            ssl_param = 1

        req.write(pageheaderonly(req=req, title=title_message, uid=login_info["uid"],
                               language=ln, secure_page_p=ssl_param, metaheaderadd=temp._scripts(kill_browser_cache=True)))

        req.write(TEMPLATE.tmpl_welcome_start())

        if pinfo["merge_info_message"]:
            message = [pinfo["merge_info_message"]]
            req.write(TEMPLATE.tmpl_merge_transaction_box('success', message))
            pinfo["merge_info_message"] = None
            session.dirty = True

        if pinfo["login_info_message"]:
            message = [pinfo["login_info_message"]]
            req.write(TEMPLATE.tmpl_login_transaction_box('success', message))
            pinfo["login_info_message"] = None
            session.dirty = True

        user_pid = webapi.get_user_pid(login_info['uid'])
        person_data = webapi.get_person_info_by_pid(person_id)
        arxiv_data = temp._arxiv_box(login_info, person_id, user_pid)
        orcid_data = temp._orcid_box(arxiv_data['login'], person_id, user_pid, ulevel)
        claim_paper_data = temp._claim_paper_box(person_id)
        support_data = temp._support_box()
        ext_ids_data = temp._external_ids_box(person_id, user_pid, ulevel)
        autoclaim_data = temp._autoclaim_papers_box(req, person_id, user_pid, login_info['remote_logged_in_systems'])
        merge_data = temp._merge_box(person_id)
        # if False not in beval:
        gboxstatus = 'noAjax'
        req.write('<script type="text/javascript">var gPID = "%s"; </script>' % (person_id))
        req.write(TEMPLATE.tmpl_profile_managment(ln, person_data, arxiv_data, orcid_data, claim_paper_data, ext_ids_data, autoclaim_data, support_data, merge_data))
        req.write(pagefooteronly(req=req,language=ln))
        webapi.history_log_visit(req, 'manage_profile', pid=person_id)
    index = __call__


class WebInterfaceAuthor(WebInterfaceDirectory):
    '''
    Handles /author/* pages.

    Supplies the methods:
        /author/choose_profile
        /author/claim/
        /author/help
        /author/manage_profile
        /author/merge_profiles
        /author/profile/
        /author/search
    '''
    _exports = ['choose_profile',
                'claim',
                'help',
                'manage_profile',
                'merge_profiles',
                'profile',
                'search']

    claim = WebInterfaceBibAuthorIDClaimPages()
    profile = WebAuthorPages()
    choose_profile = claim.choose_profile
    help = claim.help
    manage_profile = WebInterfaceBibAuthorIDManageProfilePages()
    merge_profiles = claim.merge_profiles
    search = claim.search

# pylint: enable=C0301
# pylint: enable=W0613
