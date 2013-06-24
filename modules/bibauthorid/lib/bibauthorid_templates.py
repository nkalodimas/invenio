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

"""Bibauthorid HTML templates"""

# pylint: disable=W0105
# pylint: disable=C0301


# from cgi import escape
# from urllib import quote
#
import invenio.bibauthorid_config as bconfig
from invenio.config import CFG_SITE_LANG
from invenio.config import CFG_SITE_URL
from invenio.config import CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL
from invenio.bibformat import format_record
from invenio.session import get_session
from invenio.search_engine_utils import get_fieldvalues
from invenio.bibauthorid_config import PERSONID_EXTERNAL_IDENTIFIER_MAP, CREATE_NEW_PERSON
from invenio.bibauthorid_webapi import get_person_redirect_link, get_canonical_id_from_person_id, get_person_names_from_id
from invenio.bibauthorid_webapi import get_external_ids_of_author
from invenio.bibauthorid_frontinterface import get_uid_of_author
from invenio.bibauthorid_frontinterface import get_bibrefrec_name_string
from invenio.bibauthorid_frontinterface import get_canonical_name_of_author
from invenio.messages import gettext_set_language, wash_language
from invenio.webuser import get_email
from invenio.htmlutils import escape_html
# from invenio.textutils import encode_for_xml

class Template:
    """Templating functions used by aid"""

    def __init__(self, language=CFG_SITE_LANG):
        """Set defaults for all aid template output"""

        self.language = language
        self._ = gettext_set_language(wash_language(language))


    def tmpl_person_detail_layout(self, content):
        '''
        writes HTML content into the person css container

        @param content: HTML content
        @type content: string

        @return: HTML code
        @rtype: string
        '''
        html = []
        h = html.append
        h('<div id="aid_person">')
        h(content)
        h('</div>')

        return "\n".join(html)


    def tmpl_transaction_box(self, teaser_key, messages, show_close_btn=True):
        '''
        Creates a notification box based on the jQuery UI style

        @param teaser_key: key to a dict which returns the teaser
        @type teaser_key: string
        @param messages: list of keys to a dict which return the message to display in the box
        @type messages: list of strings
        @param show_close_btn: display close button [x]
        @type show_close_btn: boolean

        @return: HTML code
        @rtype: string
        '''
        transaction_teaser_dict = { 'success': 'Success!',
                                    'failure': 'Failure!' }
        transaction_message_dict = { 'confirm_success': '%s transaction%s successfully executed.',
                                     'confirm_failure': '%s transaction%s failed. The system may have been updating during your operation. Please try again or contact %s to obtain help.',
                                     'reject_success': '%s transaction%s successfully executed.',
                                     'reject_failure': '%s transaction%s failed. The system may have been updating during your operation. Please try again or contact %s to obtain help.',
                                     'reset_success': '%s transaction%s successfully executed.',
                                     'reset_failure': '%s transaction%s failed. The system may have been updating during your operation. Please try again or contact %s to obtain help.' }

        teaser = self._(transaction_teaser_dict[teaser_key])

        html = []
        h = html.append
        for key in transaction_message_dict.keys():
            same_kind = [mes for mes in messages if mes == key]
            trans_no = len(same_kind)
            if trans_no == 0:
                continue
            elif trans_no == 1:
                args = [trans_no, '']
            else:
                args = [trans_no, 's']

            color = ''
            if teaser_key == 'failure':
                color = 'background: #FC2626;'
                args.append(CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL)

            message = self._(transaction_message_dict[key] % tuple(args))

            h('<div id="aid_notification_' + key + '" class="ui-widget ui-alert">')
            h('  <div style="%s margin-top: 20px; padding: 0pt 0.7em;" class="ui-state-highlight ui-corner-all">' % (color))
            h('    <p><span style="float: left; margin-right: 0.3em;" class="ui-icon ui-icon-info"></span>')
            h('    <strong>%s</strong> %s' % (teaser, message))

            if show_close_btn:
                h('    <span style="float:right; margin-right: 0.3em;"><a rel="nofollow" href="#" class="aid_close-notify" style="border-style: none;">X</a></span></p>')

            h(' </div>')
            h('</div>')

        return "\n".join(html)

    def tmpl_notification_box(self, teaser_key, message_key, bibrefs, show_close_btn=True):
        '''
        Creates a notification box based on the jQuery UI style

        @param teaser_key: key to a dict which returns the teaser
        @type teaser_key: string
        @param message_key: key to a dict which returns the message to display in the box
        @type message_key: string
        @param bibrefs: bibrefs which are about to be assigned
        @type bibrefs: list of strings
        @param show_close_btn: display close button [x]
        @type show_close_btn: boolean

        @return: HTML code
        @rtype: string
        '''
        notification_teaser_dict = {'info': 'Info!' }
        notification_message_dict = {'attribute_papers': 'You are about to attribute the following paper%s:' }

        teaser = self._(notification_teaser_dict[teaser_key])
        arg = ''
        if len(bibrefs) > 1:
            arg = 's'
        message = self._(notification_message_dict[message_key] % (arg))

        html = []
        h = html.append

        h('<div id="aid_notification_' + teaser_key + '" class="ui-widget ui-alert">')
        h('  <div style="margin-top: 20px; padding: 0pt 0.7em;" class="ui-state-highlight ui-corner-all">')
        h('    <p><span style="float: left; margin-right: 0.3em;" class="ui-icon ui-icon-info"></span>')
        h('    <strong>%s</strong> %s' % (teaser, message))
        h("<ul>")
        for paper in bibrefs:
            if ',' in paper:
                pbibrec = paper.split(',')[1]
            else:
                pbibrec = paper
            h("<li>%s</li>" % (format_record(int(pbibrec), "ha")))
        h("</ul>")

        if show_close_btn:
            h('    <span style="float:right; margin-right: 0.3em;"><a rel="nofollow" href="#" class="aid_close-notify">X</a></span></p>')

        h(' </div>')
        h('</div>')

        return "\n".join(html)


    def tmpl_error_box(self, teaser_key, message_key, show_close_btn=True):
        '''
        Creates an error box based on the jQuery UI style

        @param teaser_key: key to a dict which returns the teaser
        @type teaser_key: string
        @param message_key: key to a dict which returns the message to display in the box
        @type message_key: string
        @param show_close_btn: display close button [x]
        @type show_close_btn: boolean

        @return: HTML code
        @rtype: string
        '''
        error_teaser_dict = {'sorry': 'Sorry.',
                             'error': 'Error:' }
        error_message_dict = {'check_entries': 'Please check your entries.',
                              'provide_transaction': 'Please provide at least one transaction.' }

        teaser = self._(error_teaser_dict[teaser_key])
        message = self._(error_message_dict[message_key])

        html = []
        h = html.append

        h('<div id="aid_notification_' + teaser_key + '" class="ui-widget ui-alert">')
        h('  <div style="background: #FC2626; margin-top: 20px; padding: 0pt 0.7em; color:#000000;" class="ui-state-error ui-corner-all">')
        h('    <p><span style="float: left; margin-right: 0.3em;" class="ui-icon ui-icon-alert"></span>')
        h('    <strong>%s</strong> %s' % (teaser, message))

        if show_close_btn:
            h('    <span style="float:right; margin-right: 0.3em;"> ')
            h('<a rel="nofollow" href="#" style="color: #000000; border: 1px #000000 solid;" class="aid_close-notify">X</a></span>')

        h('</p> </div>')
        h('</div>')

        return "\n".join(html)


    def tmpl_ticket_box(self, teaser_key, message_key, trans_no, show_close_btn=True):
        '''
        Creates a semi-permanent box informing about ticket
        status notifications

        @param teaser_key: key to a dict which returns the teaser
        @type teaser_key: string
        @param message_key: key to a dict which returns the message to display in the box
        @type message_key: string
        @param trans_no: number of transactions in progress
        @type trans_no: integer
        @param show_close_btn: display close button [x]
        @type show_close_btn: boolean

        @return: HTML code
        @rtype: string
        '''
        ticket_teaser_dict = {'in_process': 'Claim in process!' }
        ticket_message_dict = {'transaction': 'There %s %s transaction%s in progress.' }

        teaser = self._(ticket_teaser_dict[teaser_key])

        if trans_no == 1:
            args = ['is', trans_no, '']
        else:
            args = ['are', trans_no, 's']

        message = self._(ticket_message_dict[message_key] % tuple(args))

        html = []
        h = html.append
        h('<div id="aid_notification_' + teaser_key + '" class="ui-widget ui-alert">')
        h('  <div style="margin-top: 20px; padding: 0pt 0.7em;" class="ui-state-highlight ui-corner-all">')
        h('    <p><span style="float: left; margin-right: 0.3em;" class="ui-icon ui-icon-info"></span>')
        h('    <strong>%s</strong> %s ' % (teaser, message))
        h('<a rel="nofollow" id="checkout" href="action?checkout=True">' + self._('Click here to review the transactions.') + '</a>')
        h('<br>')

        if show_close_btn:
            h('    <span style="float:right; margin-right: 0.3em;"><a rel="nofollow" href="#" class="aid_close-notify">X</a></span></p>')

        h(' </div>')
        h('</div>')

        return "\n".join(html)

    def tmpl_search_ticket_box(self, teaser_key, message_key, bibrefs, show_close_btn=False):
        '''
        Creates a box informing about a claim in progress for
        the search.

        @param teaser_key: key to a dict which returns the teaser
        @type teaser_key: string
        @param message_key: key to a dict which returns the message to display in the box
        @type message_key: string
        @param bibrefs: bibrefs which are about to be assigned
        @type bibrefs: list of strings
        @param show_close_btn: display close button [x]
        @type show_close_btn: boolean

        @return: HTML code
        @rtype: string
        '''
        error_teaser_dict = {'person_search': 'Person search for assignment in progress!' }
        error_message_dict = {'assign_papers': 'You are searching for a person to assign the following paper%s:' }

        teaser = self._(error_teaser_dict[teaser_key])
        arg = ''
        if len(bibrefs) > 1:
            arg = 's'
        message = self._(error_message_dict[message_key] % (arg))

        html = []
        h = html.append
        h('<div id="aid_notification_' + teaser_key + '" class="ui-widget ui-alert">')
        h('  <div style="margin-top: 20px; padding: 0pt 0.7em;" class="ui-state-highlight ui-corner-all">')
        h('    <p><span style="float: left; margin-right: 0.3em;" class="ui-icon ui-icon-info"></span>')
        h('    <strong>%s</strong> %s ' % (teaser, message))
        h("<ul>")
        for paper in bibrefs:
            if ',' in paper:
                pbibrec = paper.split(',')[1]
            else:
                pbibrec = paper
            h("<li>%s</li>"
                   % (format_record(int(pbibrec), "ha")))
        h("</ul>")
        h('<a rel="nofollow" id="checkout" href="action?cancel_search_ticket=True">' + self._('Quit searching.') + '</a>')

        if show_close_btn:
            h('    <span style="float:right; margin-right: 0.3em;"><a rel="nofollow" href="#" class="aid_close-notify">X</a></span></p>')

        h(' </div>')
        h('</div>')
        h('<p>&nbsp;</p>')

        return "\n".join(html)


    def tmpl_merge_ticket_box(self, teaser_key, message_key, primary_profile, profiles, merge_power):

        message = self._('Person search for profile merging in progress!')
        if not merge_power:
            message += '(You have no rights to actualy merge profiles. However you can submit profiles for merging)'

        error_teaser_dict = {'person_search': message }
        error_message_dict = {'merge_profiles': 'You are about to merge the following profile%s:' }

        teaser = self._(error_teaser_dict[teaser_key])
        arg = ''
        if len(profiles) >= 1:
            arg = 's'
        message = self._(error_message_dict[message_key] % (arg))

        html = []
        h = html.append
        h('<div id="aid_notification_' + teaser_key + '" class="ui-widget ui-alert">')
        h('  <div style="margin-top: 20px; padding: 0pt 0.7em;" class="ui-state-highlight ui-corner-all">')
        h('    <p><span style="float: left; margin-right: 0.3em;" class="ui-icon ui-icon-info"></span>')
        h('    <strong>%s</strong> </br>%s ' % (teaser, message))
        h("<ul>")

        h("<li><a href='%s'target='_blank'>%s</a> <strong>(primary profile)</strong></li>"
          % (primary_profile, primary_profile))
        for profile in profiles:
            h("<li><a href='%s'target='_blank'>%s</a></li>"
                   % (profile, profile))
        h("</ul>")
        h('<a rel="nofollow" id="checkout" href="manage_profile?pid=%s">' % (str(primary_profile),) + self._('Stop merging.') + '</a>' )
        if len(profiles):
            if merge_power:
                h('<a rel="nofollow" id="merge" href="merge_profiles?search_pid=%s">' % (str(primary_profile),) + self._('Merge profiles.') + '</a>' )
            else:
                h('<a rel="nofollow" id="checkout" href="manage_profile?search_pid=%s">' % (str(primary_profile),) + self._('Submit for merging') + '</a>' )

        h(' </div>')
        h('</div>')
        h('<p>&nbsp;</p>')

        return "\n".join(html)


    def tmpl_meta_includes(self, kill_browser_cache=False):
        '''
        Generates HTML code for the header section of the document
        META tags to kill browser caching
        Javascript includes
        CSS definitions

        @param kill_browser_cache: Do we want to kill the browser cache?
        @type kill_browser_cache: boolean
        '''

        js_path = "%s/js" % CFG_SITE_URL
        imgcss_path = "%s/img" % CFG_SITE_URL

        result = []
        # Add browser cache killer, hence some notifications are not displayed
        # out of the session.
        if kill_browser_cache:
            result = [
                '<META HTTP-EQUIV="Pragma" CONTENT="no-cache">',
                '<META HTTP-EQUIV="Cache-Control" CONTENT="no-cache">',
                '<META HTTP-EQUIV="Pragma-directive" CONTENT="no-cache">',
                '<META HTTP-EQUIV="Cache-Directive" CONTENT="no-cache">',
                '<META HTTP-EQUIV="Expires" CONTENT="0">']

        scripts = ["jquery-ui.min.js",
                   "jquery.form.js",
                   "jquery.dataTables.min.js",
                   "bibauthorid.js"]

        result.append('<link rel="stylesheet" type="text/css" href='
                      '"%s/jquery-ui/themes/smoothness/jquery-ui.css" />'
                      % (imgcss_path))
        result.append('<link rel="stylesheet" type="text/css" href='
                      '"%s/datatables_jquery-ui.css" />'
                      % (imgcss_path))
        result.append('<link rel="stylesheet" type="text/css" href='
                      '"%s/bibauthorid.css" />'
                      % (imgcss_path))

        for script in scripts:
            result.append('<script type="text/javascript" src="%s/%s">'
                      '</script>' % (js_path, script))

        return "\n".join(result)


    def tmpl_author_confirmed(self, bibref, pid, verbiage_dict={'alt_confirm':'Confirmed.',
                                                                       'confirm_text':'This record assignment has been confirmed.',
                                                                       'alt_forget':'Forget decision!',
                                                                       'forget_text':'Forget assignment decision',
                                                                       'alt_repeal':'Repeal!',
                                                                       'repeal_text':'Repeal record assignment',
                                                                       'to_other_text':'Assign to another person',
                                                                       'alt_to_other':'To other person!'
                                                                       },
                              show_reset_button=True):
        '''
        Generate play per-paper links for the table for the
        status "confirmed"

        @param bibref: construct of unique ID for this author on this paper
        @type bibref: string
        @param pid: the Person ID
        @type pid: int
        @param verbiage_dict: language for the link descriptions
        @type verbiage_dict: dict
        '''

        stri = ('<!--2!--><span id="aid_status_details"> '
                '<img src="%(url)s/img/aid_check.png" alt="%(alt_confirm)s" />'
                '%(confirm_text)s <br>')
        if show_reset_button:
            stri = stri + (
                '<a rel="nofollow" id="aid_reset_gr" class="aid_grey" href="%(url)s/author/claim/action?reset=True&selection=%(ref)s&pid=%(pid)s">'
                '<img src="%(url)s/img/aid_reset_gray.png" alt="%(alt_forget)s" style="margin-left:22px;" />'
                '%(forget_text)s</a><br>')
        stri = stri + (
                '<a rel="nofollow" id="aid_repeal" class="aid_grey" href="%(url)s/author/claim/action?repeal=True&selection=%(ref)s&pid=%(pid)s">'
                '<img src="%(url)s/img/aid_reject_gray.png" alt="%(alt_repeal)s" style="margin-left:22px;"/>'
                '%(repeal_text)s</a><br>'
                '<a rel="nofollow" id="aid_to_other" class="aid_grey" href="%(url)s/author/claim/action?to_other_person=True&selection=%(ref)s">'
                '<img src="%(url)s/img/aid_to_other_gray.png" alt="%(alt_to_other)s" style="margin-left:22px;"/>'
                '%(to_other_text)s</a> </span>')
        return (stri
                % ({'url': CFG_SITE_URL, 'ref': bibref, 'pid': pid,
                    'alt_confirm':verbiage_dict['alt_confirm'],
                    'confirm_text':verbiage_dict['confirm_text'],
                    'alt_forget':verbiage_dict['alt_forget'],
                    'forget_text':verbiage_dict['forget_text'],
                    'alt_repeal':verbiage_dict['alt_repeal'],
                    'repeal_text':verbiage_dict['repeal_text'],
                    'to_other_text':verbiage_dict['to_other_text'],
                    'alt_to_other':verbiage_dict['alt_to_other']}))


    def tmpl_author_repealed(self, bibref, pid, verbiage_dict={'alt_confirm':'Confirm!',
                                                                       'confirm_text':'Confirm record assignment.',
                                                                       'alt_forget':'Forget decision!',
                                                                       'forget_text':'Forget assignment decision',
                                                                       'alt_repeal':'Rejected!',
                                                                       'repeal_text':'Repeal this record assignment.',
                                                                       'to_other_text':'Assign to another person',
                                                                       'alt_to_other':'To other person!'
                                                                       }):
        '''
        Generate play per-paper links for the table for the
        status "repealed"

        @param bibref: construct of unique ID for this author on this paper
        @type bibref: string
        @param pid: the Person ID
        @type pid: int
        @param verbiage_dict: language for the link descriptions
        @type verbiage_dict: dict
        '''
        stri = ('<!---2!--><span id="aid_status_details"> '
                '<img src="%(url)s/img/aid_reject.png" alt="%(alt_repeal)s" />'
                '%(repeal_text)s <br>'
                '<a rel="nofollow" id="aid_confirm" class="aid_grey" href="%(url)s/author/claim/action?confirm=True&selection=%(ref)s&pid=%(pid)s">'
                '<img src="%(url)s/img/aid_check_gray.png" alt="%(alt_confirm)s" style="margin-left: 22px;" />'
                '%(confirm_text)s</a><br>'
                '<a rel="nofollow" id="aid_to_other" class="aid_grey" href="%(url)s/author/claim/action?to_other_person=True&selection=%(ref)s">'
                '<img src="%(url)s/img/aid_to_other_gray.png" alt="%(alt_to_other)s" style="margin-left:22px;"/>'
                '%(to_other_text)s</a> </span>')

        return (stri
                % ({'url': CFG_SITE_URL, 'ref': bibref, 'pid': pid,
                    'alt_confirm':verbiage_dict['alt_confirm'],
                    'confirm_text':verbiage_dict['confirm_text'],
                    'alt_forget':verbiage_dict['alt_forget'],
                    'forget_text':verbiage_dict['forget_text'],
                    'alt_repeal':verbiage_dict['alt_repeal'],
                    'repeal_text':verbiage_dict['repeal_text'],
                    'to_other_text':verbiage_dict['to_other_text'],
                    'alt_to_other':verbiage_dict['alt_to_other']}))


    def tmpl_author_undecided(self, bibref, pid, verbiage_dict={'alt_confirm':'Confirm!',
                                                                       'confirm_text':'Confirm record assignment.',
                                                                       'alt_repeal':'Rejected!',
                                                                       'repeal_text':'This record has been repealed.',
                                                                       'to_other_text':'Assign to another person',
                                                                       'alt_to_other':'To other person!'
                                                                       },
                              show_reset_button=True):
        '''
        Generate play per-paper links for the table for the
        status "no decision taken yet"

        @param bibref: construct of unique ID for this author on this paper
        @type bibref: string
        @param pid: the Person ID
        @type pid: int
        @param verbiage_dict: language for the link descriptions
        @type verbiage_dict: dict
        '''
        # batchprocess?mconfirm=True&bibrefs=['100:17,16']&pid=1
        string = ('<!--0!--><span id="aid_status_details"> '
                '<a rel="nofollow" id="aid_confirm" href="%(url)s/author/claim/action?confirm=True&selection=%(ref)s&pid=%(pid)s">'
                '<img src="%(url)s/img/aid_check.png" alt="%(alt_confirm)s" />'
                '%(confirm_text)s</a><br />'
                '<a rel="nofollow" id="aid_repeal" href="%(url)s/author/claim/action?repeal=True&selection=%(ref)s&pid=%(pid)s">'
                '<img src="%(url)s/img/aid_reject.png" alt="%(alt_repeal)s" />'
                '%(repeal_text)s</a> <br />'
                '<a rel="nofollow" id="aid_to_other" href="%(url)s/author/claim/action?to_other_person=True&selection=%(ref)s">'
                '<img src="%(url)s/img/aid_to_other.png" alt="%(alt_to_other)s" />'
                '%(to_other_text)s</a> </span>')
        return (string
                % ({'url': CFG_SITE_URL, 'ref': bibref, 'pid': pid,
                    'alt_confirm':verbiage_dict['alt_confirm'],
                    'confirm_text':verbiage_dict['confirm_text'],
                    'alt_repeal':verbiage_dict['alt_repeal'],
                    'repeal_text':verbiage_dict['repeal_text'],
                    'to_other_text':verbiage_dict['to_other_text'],
                    'alt_to_other':verbiage_dict['alt_to_other']}))


    def tmpl_open_claim(self, bibrefs, pid, last_viewed_pid,
                        search_enabled=True):
        '''
        Generate entry page for "claim or attribute this paper"

        @param bibref: construct of unique ID for this author on this paper
        @type bibref: string
        @param pid: the Person ID
        @type pid: int
        @param last_viewed_pid: last ID that had been subject to an action
        @type last_viewed_pid: int
        '''
        t_html = []
        h = t_html.append

        h(self.tmpl_notification_box('info', 'attribute_papers', bibrefs, show_close_btn=False))
        h('<p> ' + self._('Your options') + ': </p>')

        bibs = ''
        for paper in bibrefs:
            if bibs:
                bibs = bibs + '&'
            bibs = bibs + 'selection=' + str(paper)

        if pid > -1:
            h('<a rel="nofollow" id="clam_for_myself" href="%s/author/claim/action?confirm=True&%s&pid=%s"> ' % (CFG_SITE_URL, bibs, str(pid)))
            h(self._('Claim for yourself') + ' </a> <br>')

        if last_viewed_pid:
            h('<a rel="nofollow" id="clam_for_last_viewed" href="%s/author/claim/action?confirm=True&%s&pid=%s"> ' % (CFG_SITE_URL, bibs, str(last_viewed_pid[0])))
            h(self._('Attribute to') + ' %s </a> <br>' % (last_viewed_pid[1]))

        if search_enabled:
            h('<a rel="nofollow" id="claim_search" href="%s/author/claim/action?to_other_person=True&%s"> ' % (CFG_SITE_URL, bibs))
            h(self._('Search for a person to attribute the paper to') + ' </a> <br>')

        return "\n".join(t_html)


    def __tmpl_admin_records_table(self, form_id, person_id, bibrecids, verbiage_dict={'no_doc_string':'Sorry, there are currently no documents to be found in this category.',
                                                                                              'b_confirm':'Confirm',
                                                                                              'b_repeal':'Repeal',
                                                                                              'b_to_others':'Assign to other person',
                                                                                              'b_forget':'Forget decision'},
                                                                            buttons_verbiage_dict={'mass_buttons':{'no_doc_string':'Sorry, there are currently no documents to be found in this category.',
                                                                                                      'b_confirm':'Confirm',
                                                                                                      'b_repeal':'Repeal',
                                                                                                      'b_to_others':'Assign to other person',
                                                                                                      'b_forget':'Forget decision'},
                                                                                     'record_undecided':{'alt_confirm':'Confirm!',
                                                                                                         'confirm_text':'Confirm record assignment.',
                                                                                                         'alt_repeal':'Rejected!',
                                                                                                         'repeal_text':'This record has been repealed.'},
                                                                                     'record_confirmed':{'alt_confirm':'Confirmed.',
                                                                                                           'confirm_text':'This record assignment has been confirmed.',
                                                                                                           'alt_forget':'Forget decision!',
                                                                                                           'forget_text':'Forget assignment decision',
                                                                                                           'alt_repeal':'Repeal!',
                                                                                                           'repeal_text':'Repeal record assignment'},
                                                                                     'record_repealed':{'alt_confirm':'Confirm!',
                                                                                                        'confirm_text':'Confirm record assignment.',
                                                                                                        'alt_forget':'Forget decision!',
                                                                                                        'forget_text':'Forget assignment decision',
                                                                                                        'alt_repeal':'Rejected!',
                                                                                                        'repeal_text':'Repeal this record assignment.'}},
                                                                            show_reset_button=True):
        '''
        Generate the big tables for the person overview page

        @param form_id: name of the form
        @type form_id: string
        @param person_id: Person ID
        @type person_id: int
        @param bibrecids: List of records to display
        @type bibrecids: list
        @param verbiage_dict: language for the elements
        @type verbiage_dict: dict
        @param buttons_verbiage_dict: language for the buttons
        @type buttons_verbiage_dict: dict
        '''
        no_papers_html = ['<div style="text-align:left;margin-top:1em;"><strong>']
        no_papers_html.append('%s' % self._(verbiage_dict['no_doc_string']))
        no_papers_html.append('</strong></div>')

        if not bibrecids or not person_id:
            return "\n".join(no_papers_html)

        pp_html = []
        h = pp_html.append

        h('<form id="%s" action="/author/claim/action" method="post">'
                   % (form_id))

        # +self._(' On all pages: '))
        h('<div class="aid_reclist_selector">')
        h('<a rel="nofollow" rel="group_1" href="#select_all">' + self._('Select All') + '</a> | ')
        h('<a rel="nofollow" rel="group_1" href="#select_none">' + self._('Select None') + '</a> | ')
        h('<a rel="nofollow" rel="group_1" href="#invert_selection">' + self._('Invert Selection') + '</a> | ')
        h('<a rel="nofollow" id="toggle_claimed_rows" href="javascript:toggle_claimed_rows();" '
          'alt="hide">' + self._('Hide successful claims') + '</a>')
        h('</div>')

        h('<div class="aid_reclist_buttons">')
        h(('<img src="%s/img/aid_90low_right.png" alt="∟" />')
          % (CFG_SITE_URL))
        h('<input type="hidden" name="pid" value="%s" />' % (person_id))
        h('<input type="submit" name="confirm" value="%s" class="aid_btn_blue" />' % self._(verbiage_dict['b_confirm']))
        h('<input type="submit" name="repeal" value="%s" class="aid_btn_blue" />' % self._(verbiage_dict['b_repeal']))
        h('<input type="submit" name="to_other_person" value="%s" class="aid_btn_blue" />' % self._(verbiage_dict['b_to_others']))
        # if show_reset_button:
        #    h('<input type="submit" name="reset" value="%s" class="aid_btn_blue" />' % verbiage_dict['b_forget'])
        h("  </div>")


        h('<table  class="paperstable" cellpadding="3" width="100%">')
        h("<thead>")
        h("  <tr>")
        h('    <th>&nbsp;</th>')
        h('    <th>' + self._('Paper Short Info') + '</th>')
        h('    <th>' + self._('Author Name') + '</th>')
        h('    <th>' + self._('Affiliation') + '</th>')
        h('    <th>' + self._('Date') + '</th>')
        h('    <th>' + self._('Experiment') + '</th>')
        h('    <th>' + self._('Actions') + '</th>')
        h('  </tr>')
        h('</thead>')
        h('<tbody>')


        for idx, paper in enumerate(bibrecids):
            h('  <tr style="padding-top: 6px; padding-bottom: 6px;">')

            h('    <td><input type="checkbox" name="selection" '
                           'value="%s" /> </td>' % (paper['bibref']))
            rec_info = format_record(int(paper['recid']), "ha")
            rec_info = str(idx + 1) + '.  ' + rec_info
            h("    <td>%s</td>" % (rec_info))
            h("    <td>%s</td>" % (paper['authorname']))
            aff = ""

            if paper['authoraffiliation']:
                aff = paper['authoraffiliation']
            else:
                aff = self._("Not assigned")

            h("    <td>%s</td>" % (aff))

            if paper['paperdate']:
                pdate = paper['paperdate']
            else:
                pdate = 'N.A.'
            h("    <td>%s</td>" % pdate)

            if paper['paperexperiment']:
                pdate = paper['paperexperiment']
            else:
                pdate = 'N.A.'
            h("    <td>%s</td>" % pdate)

            paper_status = self._("No status information found.")

            if paper['flag'] == 2:
                paper_status = self.tmpl_author_confirmed(paper['bibref'], person_id,
                                            verbiage_dict=buttons_verbiage_dict['record_confirmed'],
                                            show_reset_button=show_reset_button)
            elif paper['flag'] == -2:
                paper_status = self.tmpl_author_repealed(paper['bibref'], person_id,
                                            verbiage_dict=buttons_verbiage_dict['record_repealed'])
            else:
                paper_status = self.tmpl_author_undecided(paper['bibref'], person_id,
                                            verbiage_dict=buttons_verbiage_dict['record_undecided'],
                                            show_reset_button=show_reset_button)

            h('    <td><div id="bibref%s" style="float:left"><!--%s!-->%s &nbsp;</div>'
                           % (paper['bibref'], paper['flag'], paper_status))

            if 'rt_status' in paper and paper['rt_status']:
                h('<img src="%s/img/aid_operator.png" title="%s" '
                  'alt="actions pending" style="float:right" '
                  'height="24" width="24" />'
                  % (CFG_SITE_URL, self._("Operator review of user actions pending")))

            h('    </td>')
            h("  </tr>")

        h("  </tbody>")
        h("</table>")

        # +self._(' On all pages: '))
        h('<div class="aid_reclist_selector">')
        h('<a rel="nofollow" rel="group_1" href="#select_all">' + self._('Select All') + '</a> | ')
        h('<a rel="nofollow" rel="group_1" href="#select_none">' + self._('Select None') + '</a> | ')
        h('<a rel="nofollow" rel="group_1" href="#invert_selection">' + self._('Invert Selection') + '</a> | ')
        h('<a rel="nofollow" id="toggle_claimed_rows" href="javascript:toggle_claimed_rows();" '
          'alt="hide">' + self._('Hide successful claims') + '</a>')
        h('</div>')

        h('<div class="aid_reclist_buttons">')
        h(('<img src="%s/img/aid_90low_right.png" alt="∟" />')
          % (CFG_SITE_URL))
        h('<input type="hidden" name="pid" value="%s" />' % (person_id))
        h('<input type="submit" name="confirm" value="%s" class="aid_btn_blue" />' % verbiage_dict['b_confirm'])
        h('<input type="submit" name="repeal" value="%s" class="aid_btn_blue" />' % verbiage_dict['b_repeal'])
        h('<input type="submit" name="to_other_person" value="%s" class="aid_btn_blue" />' % verbiage_dict['b_to_others'])
        # if show_reset_button:
        #    h('<input type="submit" name="reset" value="%s" class="aid_btn_blue" />' % verbiage_dict['b_forget'])
        h("  </div>")
        h("</form>")
        return "\n".join(pp_html)


    def __tmpl_reviews_table(self, person_id, bibrecids, admin=False):
        '''
        Generate the table for potential reviews.

        @param form_id: name of the form
        @type form_id: string
        @param person_id: Person ID
        @type person_id: int
        @param bibrecids: List of records to display
        @type bibrecids: list
        @param admin: Show admin functions
        @type admin: boolean
        '''
        no_papers_html = ['<div style="text-align:left;margin-top:1em;"><strong>']
        no_papers_html.append(self._('Sorry, there are currently no records to be found in this category.'))
        no_papers_html.append('</strong></div>')

        if not bibrecids or not person_id:
            return "\n".join(no_papers_html)

        pp_html = []
        h = pp_html.append
        h('<form id="review" action="/author/claim/batchprocess" method="post">')
        h('<table  class="reviewstable" cellpadding="3" width="100%">')
        h('  <thead>')
        h('    <tr>')
        h('      <th>&nbsp;</th>')
        h('      <th>' + self._('Paper Short Info') + '</th>')
        h('      <th>' + self._('Actions') + '</th>')
        h('    </tr>')
        h('  </thead>')
        h('  <tbody>')

        for paper in bibrecids:
            h('  <tr>')
            h('    <td><input type="checkbox" name="selected_bibrecs" '
                       'value="%s" /> </td>' % (paper))
            rec_info = format_record(int(paper[0]), "ha")

            if not admin:
                rec_info = rec_info.replace("person/search?q=", "author/")

            h("    <td>%s</td>" % (rec_info))
            h('    <td><a rel="nofollow" href="/author/claim/batchprocess?selected_bibrecs=%s&mfind_bibref=claim">' + self._('Review Transaction') + '</a></td>'
                           % (paper))
            h("  </tr>")

        h("  </tbody>")
        h("</table>")

        h('<div style="text-align:left;"> ' + self._('On all pages') + ': ')
        h('<a rel="nofollow" rel="group_1" href="#select_all">' + self._('Select All') + '</a> | ')
        h('<a rel="nofollow" rel="group_1" href="#select_none">' + self._('Select None') + '</a> | ')
        h('<a rel="nofollow" rel="group_1" href="#invert_selection">' + self._('Invert Selection') + '</a>')
        h('</div>')

        h('<div style="vertical-align:middle;">')
        h('∟ ' + self._('With selected do') + ': ')
        h('<input type="hidden" name="pid" value="%s" />' % (person_id))
        h('<input type="hidden" name="mfind_bibref" value="claim" />')
        h('<input type="submit" name="submit" value="Review selected transactions" />')
        h("  </div>")
        h('</form>')

        return "\n".join(pp_html)


    def tmpl_admin_person_info_box(self, ln, person_id= -1, names=[]):
        '''
        Generate the box showing names

        @param ln: the language to use
        @type ln: string
        @param person_id: Person ID
        @type person_id: int
        @param names: List of names to display
        @type names: list
        '''
        html = []
        h = html.append

        if not ln:
            pass

        # class="ui-tabs ui-widget ui-widget-content ui-corner-all">
        h('<div id="aid_person_names"')
        h('<p><strong>' + self._('Names variants') + ':</strong></p>')
        h("<p>")
        h('<!--<span class="aid_lowlight_text">Person ID: <span id="pid%s">%s</span></span><br />!-->'
                      % (person_id, person_id))

        for name in names:
#            h(("%s "+self._('as appeared on')+" %s"+self._(' records')+"<br />")
#                             % (name[0], name[1]))
            h(("%s (%s); ")
                             % (name[0], name[1]))

        h("</p>")
        h("</div>")

        return "\n".join(html)


    def tmpl_admin_tabs(self, ln=CFG_SITE_LANG, person_id= -1,
                        rejected_papers=[],
                        rest_of_papers=[],
                        review_needed=[],
                        rt_tickets=[],
                        open_rt_tickets=[],
                        show_tabs=['records', 'repealed', 'review', 'comments', 'tickets', 'data'],
                        show_reset_button=True,
                        ticket_links=['delete', 'commit', 'del_entry', 'commit_entry'],
                        verbiage_dict={'confirmed':'Records', 'repealed':'Not this person\'s records',
                                         'review':'Records in need of review',
                                         'tickets':'Open Tickets', 'data':'Data',
                                         'confirmed_ns':'Papers of this Person',
                                         'repealed_ns':'Papers _not_ of this Person',
                                         'review_ns':'Papers in need of review',
                                         'tickets_ns':'Tickets for this Person',
                                         'data_ns':'Additional Data for this Person'},
                        buttons_verbiage_dict={'mass_buttons':{'no_doc_string':'Sorry, there are currently no documents to be found in this category.',
                                                                  'b_confirm':'Confirm',
                                                                  'b_repeal':'Repeal',
                                                                  'b_to_others':'Assign to other person',
                                                                  'b_forget':'Forget decision'},
                                                 'record_undecided':{'alt_confirm':'Confirm!',
                                                                     'confirm_text':'Confirm record assignment.',
                                                                     'alt_repeal':'Rejected!',
                                                                     'repeal_text':'This record has been repealed.'},
                                                 'record_confirmed':{'alt_confirm':'Confirmed.',
                                                                       'confirm_text':'This record assignment has been confirmed.',
                                                                       'alt_forget':'Forget decision!',
                                                                       'forget_text':'Forget assignment decision',
                                                                       'alt_repeal':'Repeal!',
                                                                       'repeal_text':'Repeal record assignment'},
                                                 'record_repealed':{'alt_confirm':'Confirm!',
                                                                    'confirm_text':'Confirm record assignment.',
                                                                    'alt_forget':'Forget decision!',
                                                                    'forget_text':'Forget assignment decision',
                                                                    'alt_repeal':'Rejected!',
                                                                    'repeal_text':'Repeal this record assignment.'}}):
        '''
        Generate the tabs for the person overview page

        @param ln: the language to use
        @type ln: string
        @param person_id: Person ID
        @type person_id: int
        @param rejected_papers: list of repealed papers
        @type rejected_papers: list
        @param rest_of_papers: list of attributed of undecided papers
        @type rest_of_papers: list
        @param review_needed: list of papers that need a review (choose name)
        @type review_needed:list
        @param rt_tickets: list of tickets for this Person
        @type rt_tickets: list
        @param open_rt_tickets: list of open request tickets
        @type open_rt_tickets: list
        @param show_tabs: list of tabs to display
        @type show_tabs: list of strings
        @param ticket_links: list of links to display
        @type ticket_links: list of strings
        @param verbiage_dict: language for the elements
        @type verbiage_dict: dict
        @param buttons_verbiage_dict: language for the buttons
        @type buttons_verbiage_dict: dict
        '''
        html = []
        h = html.append

        h('<div id="aid_tabbing">')
        h('  <ul>')
        if 'records' in show_tabs:
            r = verbiage_dict['confirmed']
            h('    <li><a rel="nofollow" href="#tabRecords"><span>%(r)s (%(l)s)</span></a></li>' %
              ({'r':r, 'l':len(rest_of_papers)}))
        if 'repealed' in show_tabs:
            r = verbiage_dict['repealed']
            h('    <li><a rel="nofollow" href="#tabNotRecords"><span>%(r)s (%(l)s)</span></a></li>' %
              ({'r':r, 'l':len(rejected_papers)}))
        if 'review' in show_tabs:
            r = verbiage_dict['review']
            h('    <li><a rel="nofollow" href="#tabReviewNeeded"><span>%(r)s (%(l)s)</span></a></li>' %
              ({'r':r, 'l':len(review_needed)}))
        if 'tickets' in show_tabs:
            r = verbiage_dict['tickets']
            h('    <li><a rel="nofollow" href="#tabTickets"><span>%(r)s (%(l)s)</span></a></li>' %
              ({'r':r, 'l':len(open_rt_tickets)}))
        if 'data' in show_tabs:
            r = verbiage_dict['data']
            h('    <li><a rel="nofollow" href="#tabData"><span>%s</span></a></li>' % r)

            userid = get_uid_of_author(person_id)
            if userid:
                h('<img src="%s/img/webbasket_user.png" alt="%s" width="30" height="30" />' %
                   (CFG_SITE_URL, self._("The author has an internal ID!")))
        h('  </ul>')

        if 'records' in show_tabs:
            h('  <div id="tabRecords">')
            r = verbiage_dict['confirmed_ns']
            h('<noscript><h5>%s</h5></noscript>' % r)
            h(self.__tmpl_admin_records_table("massfunctions",
                                             person_id, rest_of_papers,
                                             verbiage_dict=buttons_verbiage_dict['mass_buttons'],
                                             buttons_verbiage_dict=buttons_verbiage_dict,
                                             show_reset_button=show_reset_button))
            h("  </div>")

        if 'repealed' in show_tabs:
            h('  <div id="tabNotRecords">')
            r = verbiage_dict['repealed_ns']
            h('<noscript><h5>%s</h5></noscript>' % r)
            h(self._('These records have been marked as not being from this person.'))
            h('<br />' + self._('They will be regarded in the next run of the author ')
              + self._('disambiguation algorithm and might disappear from this listing.'))
            h(self.__tmpl_admin_records_table("rmassfunctions",
                                             person_id, rejected_papers,
                                             verbiage_dict=buttons_verbiage_dict['mass_buttons'],
                                              buttons_verbiage_dict=buttons_verbiage_dict,
                                              show_reset_button=show_reset_button))
            h("  </div>")

        if 'review' in show_tabs:
            h('  <div id="tabReviewNeeded">')
            r = verbiage_dict['review_ns']
            h('<noscript><h5>%s</h5></noscript>' % r)
            h(self.__tmpl_reviews_table(person_id, review_needed, True))
            h('  </div>')
        if 'tickets' in show_tabs:
            h('  <div id="tabTickets">')
            r = verbiage_dict['tickets']
            h('<noscript><h5>%s</h5></noscript>' % r)
            r = verbiage_dict['tickets_ns']
            h('<p>%s:</p>' % r)

            if rt_tickets:
                pass
#            open_rt_tickets = [a for a in open_rt_tickets if a[1] == rt_tickets]

            for t in open_rt_tickets:
                name = self._('Not provided')
                surname = self._('Not provided')
                uidip = self._('Not available')
                comments = self._('No comments')
                email = self._('Not provided')
                date = self._('Not Available')
                actions = []

                for info in t[0]:
                    if info[0] == 'firstname':
                        name = info[1]
                    elif info[0] == 'lastname':
                        surname = info[1]
                    elif info[0] == 'uid-ip':
                        uidip = info[1]
                    elif info[0] == 'comments':
                        comments = info[1]
                    elif info[0] == 'email':
                        email = info[1]
                    elif info[0] == 'date':
                        date = info[1]
                    elif info[0] in ['confirm', 'repeal']:
                        actions.append(info)

                if 'delete' in ticket_links:
                    h(('<strong>Ticket number: %(tnum)s </strong> <a rel="nofollow" id="cancel" href=%(url)s/author/claim/action?cancel_rt_ticket=True&selection=%(tnum)s&pid=%(pid)s>' + self._(' Delete this ticket') + ' </a>')
                  % ({'tnum':t[1], 'url':CFG_SITE_URL, 'pid':str(person_id)}))

                if 'commit' in ticket_links:
                    h((' or <a rel="nofollow" id="commit" href=%(url)s/author/claim/action?commit_rt_ticket=True&selection=%(tnum)s&pid=%(pid)s>' + self._(' Commit this entire ticket') + ' </a> <br>')
                  % ({'tnum':t[1], 'url':CFG_SITE_URL, 'pid':str(person_id)}))

                h('<dd>')
                h('Open from: %s, %s <br>' % (surname, name))
                h('Date: %s <br>' % date)
                h('identified by: %s <br>' % uidip)
                h('email: %s <br>' % email)
                h('comments: %s <br>' % comments)
                h('Suggested actions: <br>')
                h('<dd>')

                for a in actions:
                    bibref, bibrec = a[1].split(',')
                    pname = get_bibrefrec_name_string(bibref)
                    title = ""

                    try:
                        title = get_fieldvalues(int(bibrec), "245__a")[0]
                    except IndexError:
                        title = self._("No title available")
                    title = escape_html(title)

                    if 'commit_entry' in ticket_links:
                        h('<a rel="nofollow" id="action" href="%(url)s/author/claim/action?%(action)s=True&pid=%(pid)s&selection=%(bib)s&rt_id=%(rt)s">%(action)s - %(name)s on %(title)s </a>'
                      % ({'action': a[0], 'url': CFG_SITE_URL,
                          'pid': str(person_id), 'bib':a[1],
                          'name': pname, 'title': title, 'rt': t[1]}))
                    else:
                        h('%(action)s - %(name)s on %(title)s'
                      % ({'action': a[0], 'name': pname, 'title': title}))

                    if 'del_entry' in ticket_links:
                        h(' - <a rel="nofollow" id="action" href="%(url)s/author/claim/action?cancel_rt_ticket=True&pid=%(pid)s&selection=%(bib)s&rt_id=%(rt)s&rt_action=%(action)s"> Delete this entry </a>'
                      % ({'action': a[0], 'url': CFG_SITE_URL,
                          'pid': str(person_id), 'bib': a[1], 'rt': t[1]}))

                    h(' - <a rel="nofollow" id="show_paper" target="_blank" href="%(url)s/record/%(record)s"> View record <br>' % ({'url':CFG_SITE_URL, 'record':str(bibrec)}))
                h('</dd>')
                h('</dd><br>')
                # h(str(open_rt_tickets))
            h("  </div>")

        if 'data' in show_tabs:
            h('  <div id="tabData">')
            r = verbiage_dict['data_ns']
            h('<noscript><h5>%s</h5></noscript>' % r)
            full_canonical_name = str(get_canonical_id_from_person_id(person_id))
            if '.' in str(full_canonical_name) and not isinstance(full_canonical_name, int):
                canonical_name = full_canonical_name[0:full_canonical_name.rindex('.')]
            h('<div><div> <strong> Person id </strong> <br> %s <br>' % person_id)
            h('<strong> <br> Canonical name setup </strong>')
            h('<div style="margin-top: 15px;"> Current canonical name: %s' % full_canonical_name)
            h('<form method="GET" action="%s/author/claim/action" rel="nofollow">' % CFG_SITE_URL)
            h('<input type="hidden" name="set_canonical_name" value="True" />')
            h('<input name="canonical_name" id="canonical_name" type="text" style="border:1px solid #333; width:500px;" value="%s" /> ' % canonical_name)
            h('<input type="hidden" name="pid" value="%s" />' % person_id)
            h('<input type="submit" value="set canonical name" class="aid_btn_blue" />')

            h('<br>NOTE: If the canonical ID is without any number (e.g. J.Ellis), it will take the first available number. ')
            h('If the canonical ID is complete (e.g. J.Ellis.1) that ID will be assigned to the current person ')
            h('and if another person had that ID, he will lose it and get a new one. </form>')

            userid = get_uid_of_author(person_id)
            h('<div> <br>')
            h('<strong> Internal IDs </strong> <br>')
            if userid:
                email = get_email(int(userid))
                h('UserID: INSPIRE user %s is associated with this profile with email: %s' % (str(userid), str(email)))
            else:
                h('UserID: There is no INSPIRE user associated to this profile!')
            h('<br></div>')

            external_ids = get_external_ids_of_author(person_id)
            h('<div> <br>')
            h('<strong> External IDs </strong> <br>')

            h('<form method="GET" action="%s/author/claim/action" rel="nofollow">' % (CFG_SITE_URL))
            h('<input type="hidden" name="add_missing_external_ids" value="True">')
            h('<input type="hidden" name="pid" value="%s">' % person_id)
            h('<br> <input type="submit" value="add missing ids" class="aid_btn_blue"> </form>')

            if external_ids:
                h('<form method="GET" action="%s/author/claim/action" rel="nofollow">' % (CFG_SITE_URL))
                h('   <input type="hidden" name="delete_external_ids" value="True">')
                h('   <input type="hidden" name="pid" value="%s">' % person_id)
                for idx in external_ids:
                    try:
                        sys = [s for s in PERSONID_EXTERNAL_IDENTIFIER_MAP if PERSONID_EXTERNAL_IDENTIFIER_MAP[s] == idx][0]
                    except (IndexError):
                        sys = ''
                    for k in external_ids[idx]:
                        h('<br> <input type="checkbox" name="existing_ext_ids" value="%s||%s"> <strong> %s: </strong> %s' % (idx, k, sys, k))
                h('        <br> <br> <input type="submit" value="delete selected ids" class="aid_btn_blue"> <br> </form>')
            else:
                h('UserID: There are no external users associated to this profile!')



            h('<br> <br>')
            h('<form method="GET" action="%s/author/claim/action" rel="nofollow">' % (CFG_SITE_URL))
            h('   <input type="hidden" name="add_external_id" value="True">')
            h('   <input type="hidden" name="pid" value="%s">' % person_id)
            h('   <select name="ext_system">')
            h('      <option value="" selected>-- ' + self._('Choose system') + ' --</option>')
            for el in PERSONID_EXTERNAL_IDENTIFIER_MAP:
                h('  <option value="%s"> %s </option>' % (PERSONID_EXTERNAL_IDENTIFIER_MAP[el], el))
            h('   </select>')
            h('   <input type="text" name="ext_id" id="ext_id" style="border:1px solid #333; width:350px;">')
            h('   <input type="submit" value="add external id" class="aid_btn_blue">')
            # h('<br>NOTE: please note that if you add an external id it will replace the previous one (if any).')
            h('<br> </form> </div>')

            h('</div> </div>')
        h('</div>')

        return "\n".join(html)


    def tmpl_bibref_check(self, bibrefs_auto_assigned, bibrefs_to_confirm):
        '''
        Generate overview to let user chose the name on the paper that
        resembles the person in question.

        @param bibrefs_auto_assigned: list of auto-assigned papers
        @type bibrefs_auto_assigned: list
        @param bibrefs_to_confirm: list of unclear papers and names
        @type bibrefs_to_confirm: list
        '''
        html = []
        h = html.append
        h('<form id="review" action="/author/claim/action" method="post">')
        h('<p><strong>' + self._("Make sure we match the right names!")
          + '</strong></p>')
        h('<p>' + self._('Please select an author on each of the records that will be assigned.') + '<br/>')
        h(self._('Papers without a name selected will be ignored in the process.'))
        h('</p>')

        for person in bibrefs_to_confirm:
            if not "bibrecs" in bibrefs_to_confirm[person]:
                continue

            person_name = bibrefs_to_confirm[person]["person_name"]
            if person_name.isspace():
                h((self._('Claim for person with id') + ': %s. ') % person)
                h(self._('This seems to be an empty profile without names associated to it yet'))
                h(self._('(the names will be automatically gathered when the first paper is claimed to this profile).'))
            else:
                h((self._("Select name for") + " %s") % (person_name))
            pid = person

            for recid in bibrefs_to_confirm[person]["bibrecs"]:
                h('<div id="aid_moreinfo">')

                try:
                    fv = get_fieldvalues(int(recid), "245__a")[0]
                except (ValueError, IndexError, TypeError):
                    fv = self._('Error retrieving record title')
                fv = escape_html(fv)

                h(self._("Paper title: ") + fv)
                h('<select name="bibrecgroup%s">' % (recid))
                h('<option value="" >-- ' + self._('Ignore') + ' --</option>')
                h('<option value="" selected>-- Choose author name --</option>')


                for bibref in bibrefs_to_confirm[person]["bibrecs"][recid]:
                    h('<option value="%s||%s">%s</option>'
                      % (pid, bibref[0], bibref[1]))

                h('</select>')
                h("</div>")

        if bibrefs_auto_assigned:
            h(self._('The following names have been automatically chosen:'))
            for person in bibrefs_auto_assigned:
                if not "bibrecs" in bibrefs_auto_assigned[person]:
                    continue

                h((self._("For") + " %s:") % bibrefs_auto_assigned[person]["person_name"])
                pid = person

                for recid in bibrefs_auto_assigned[person]["bibrecs"]:
                    try:
                        fv = get_fieldvalues(int(recid), "245__a")[0]
                    except (ValueError, IndexError, TypeError):
                        fv = self._('Error retrieving record title')
                    fv = escape_html(fv)

                    h('<div id="aid_moreinfo">')
                    h(('%s' + self._(' --  With name: ')) % (fv))
                    # , bibrefs_auto_assigned[person]["bibrecs"][recid][0][1]))
                    # asbibref = "%s||%s" % (person, bibrefs_auto_assigned[person]["bibrecs"][recid][0][0])
                    pbibref = bibrefs_auto_assigned[person]["bibrecs"][recid][0][0]
                    h('<select name="bibrecgroup%s">' % (recid))
                    h('<option value="" selected>-- ' + self._('Ignore') + ' --</option>')

                    for bibref in bibrefs_auto_assigned[person]["bibrecs"][recid]:
                        selector = ""

                        if bibref[0] == pbibref:
                            selector = ' selected="selected"'

                        h('<option value="%s||%s"%s>%s</option>'
                          % (pid, bibref[0], selector, bibref[1]))

                    h('</select>')
                    # h('<input type="hidden" name="bibrecgroup%s" value="%s" />'
                    #          % (recid, asbibref))
                    h('</div>')

        h('<div style="text-align:center;">')
        h('  <input type="submit" class="aid_btn_green" name="bibref_check_submit" value="Accept" />')
        h('  <input type="submit" class="aid_btn_blue" name="cancel_stage" value="Delete all transactions" />')
        h("</div>")
        h('</form>')

        return "\n".join(html)


    def tmpl_invenio_search_box(self):
        '''
        Generate little search box for missing papers. Links to main invenio
        search on start papge.
        '''
        html = []
        h = html.append
        h('<div style="margin-top: 15px;"> <strong>Search for missing papers:</strong> <form method="GET" action="%s/search">' % CFG_SITE_URL)
        h('<input name="p" id="p" type="text" style="border:1px solid #333; width:500px;" /> ')
        h('<input type="submit" name="action_search" value="search" '
          'class="aid_btn_blue" />')
        h('</form> </div>')

        return "\n".join(html)


    def tmpl_person_menu(self):
        '''
        Generate the menu bar
        '''
        html = []
        h = html.append
        h('<div id="aid_menu">')
        h('  <ul>')
        h('    <li>' + self._('Navigation:') + '</li>')
        h(('    <li><a rel="nofollow" href="%s/author/claim/search">' + self._('Run paper attribution for another author') + '</a></li>') % CFG_SITE_URL)
        h('    <!--<li><a rel="nofollow" href="#">' + self._('Person Interface FAQ') + '</a></li>!-->')
        h('  </ul>')
        h('</div>')

        return "\n".join(html)

    def tmpl_person_menu_admin(self, pid):
        '''
        Generate the menu bar
        '''
        html = []
        h = html.append
        h('<div id="aid_menu">')
        h('  <ul>')
        h('    <li>' + self._('Navigation:') + '</li>')
        h(('    <li><a rel="nofollow" href="%s/author/claim/search">' + self._('Person Search') + '</a></li>') % CFG_SITE_URL)
        h(('    <li><a rel="nofollow" href="%s/author/claim/manage_profile?pid=%s">' + self._('Manage Profile') + '</a></li>') % (CFG_SITE_URL, pid))
        h(('    <li><a rel="nofollow" href="%s/author/claim/tickets_admin">' + self._('Open tickets') + '</a></li>') % CFG_SITE_URL)
        h('    <!--<li><a rel="nofollow" href="#">' + self._('Person Interface FAQ') + '</a></li>!-->')
        h('  </ul>')
        h('</div>')

        return "\n".join(html)

    def tmpl_ticket_final_review(self, req, mark_yours=[], mark_not_yours=[],
                                 mark_theirs=[], mark_not_theirs=[]):
        '''
        Generate final review page. Displaying transactions if they
        need confirmation.

        @param req: Apache request object
        @type req: Apache request object
        @param mark_yours: papers marked as 'yours'
        @type mark_yours: list
        @param mark_not_yours: papers marked as 'not yours'
        @type mark_not_yours: list
        @param mark_theirs: papers marked as being someone else's
        @type mark_theirs: list
        @param mark_not_theirs: papers marked as NOT being someone else's
        @type mark_not_theirs: list
        '''
        def html_icon_legend():
            html = []
            h = html.append
            h('<div id="legend">')
            h("<p>")
            h(self._("Symbols legend: "))
            h("</p>")
            h('<span style="margin-left:25px; vertical-align:middle;">')
            h('<img src="%s/img/aid_granted.png" '
              'alt="%s" width="30" height="30" />'
              % (CFG_SITE_URL, self._("Everything is shiny, captain!")))
            h(self._('The result of this request will be visible immediately'))
            h('</span><br />')
            h('<span style="margin-left:25px; vertical-align:middle;">')
            h('<img src="%s/img/aid_warning_granted.png" '
              'alt="%s" width="30" height="30" />'
              % (CFG_SITE_URL, self._("Confirmation needed to continue")))
            h(self._('The result of this request will be visible immediately but we need your confirmation to do so for this paper has been manually claimed before'))
            h('</span><br />')
            h('<span style="margin-left:25px; vertical-align:middle;">')
            h('<img src="%s/img/aid_denied.png" '
              'alt="%s" width="30" height="30" />'
              % (CFG_SITE_URL, self._("This will create a change request for the operators")))
            h(self._("The result of this request will be visible upon confirmation through an operator"))
            h("</span>")
            h("</div>")

            return "\n".join(html)


        def mk_ticket_row(ticket):
            recid = -1
            rectitle = ""
            recauthor = "No Name Found."
            personname = "No Name Found."

            try:
                recid = ticket['bibref'].split(",")[1]
            except (ValueError, KeyError, IndexError):
                return ""

            try:
                rectitle = get_fieldvalues(int(recid), "245__a")[0]
            except (ValueError, IndexError, TypeError):
                rectitle = self._('Error retrieving record title')
            rectitle = escape_html(rectitle)

            if "authorname_rec" in ticket:
                recauthor = ticket['authorname_rec']

            if "person_name" in ticket:
                personname = ticket['person_name']

            html = []
            h = html.append

            # h("Debug: " + str(ticket) + "<br />")
            h('<td width="25">&nbsp;</td>')
            h('<td>')
            h(rectitle)
            h('</td>')
            h('<td>')
            h((personname + " (" + self._("Selected name on paper") + ": %s)") % recauthor)
            h('</td>')
            h('<td>')

            if ticket['status'] == "granted":
                h('<img src="%s/img/aid_granted.png" '
                  'alt="%s" width="30" height="30" />'
                  % (CFG_SITE_URL, self._("Everything is shiny, captain!")))
            elif ticket['status'] == "warning_granted":
                h('<img src="%s/img/aid_warning_granted.png" '
                  'alt="%s" width="30" height="30" />'
                  % (CFG_SITE_URL, self._("Verification needed to continue")))
            else:
                h('<img src="%s/img/aid_denied.png" '
                  'alt="%s" width="30" height="30" />'
                  % (CFG_SITE_URL, self._("This will create a request for the operators")))

            h('</td>')
            h('<td>')
            h('<a rel="nofollow" href="%s/author/claim/action?checkout_remove_transaction=%s ">'
              'Cancel'
              '</a>' % (CFG_SITE_URL, ticket['bibref']))
            h('</td>')

            return "\n".join(html)


        session = get_session(req)
        pinfo = session["personinfo"]
        ulevel = pinfo["ulevel"]

        html = []
        h = html.append

        # h(html_icon_legend())

        if "checkout_faulty_fields" in pinfo and pinfo["checkout_faulty_fields"]:
            h(self.tmpl_error_box('sorry', 'check_entries'))

        if ("checkout_faulty_fields" in pinfo
            and pinfo["checkout_faulty_fields"]
            and "tickets" in pinfo["checkout_faulty_fields"]):
            h(self.tmpl_error_box('error', 'provide_transaction'))

        # h('<div id="aid_checkout_teaser">' +
        #          self._('Almost done! Please use the button "Confirm these changes" '
        #                 'at the end of the page to send this request to an operator '
        #                 'for review!') + '</div>')

        h('<div id="aid_person_names" '
          'class="ui-tabs ui-widget ui-widget-content ui-corner-all"'
          'style="padding:10px;">')

        h("<h4>" + self._('Please provide your information') + "</h4>")
        h('<form id="final_review" action="%s/author/claim/action" method="post">'
          % (CFG_SITE_URL))

        if ("checkout_faulty_fields" in pinfo
            and pinfo["checkout_faulty_fields"]
            and "user_first_name" in pinfo["checkout_faulty_fields"]):
            h("<p class='aid_error_line'>" + self._('Please provide your first name') + "</p>")

        h("<p>")
        if "user_first_name_sys" in pinfo and pinfo["user_first_name_sys"]:
            h((self._("Your first name:") + " %s") % pinfo["user_first_name"])
        else:
            h(self._('Your first name:') + ' <input type="text" name="user_first_name" value="%s" />'
              % pinfo["user_first_name"])

        if ("checkout_faulty_fields" in pinfo
            and pinfo["checkout_faulty_fields"]
            and "user_last_name" in pinfo["checkout_faulty_fields"]):
            h("<p class='aid_error_line'>" + self._('Please provide your last name') + "</p>")

        h("</p><p>")

        if "user_last_name_sys" in pinfo and pinfo["user_last_name_sys"]:
            h((self._("Your last name:") + " %s") % pinfo["user_last_name"])
        else:
            h(self._('Your last name:') + ' <input type="text" name="user_last_name" value="%s" />'
              % pinfo["user_last_name"])

        h("</p>")

        if ("checkout_faulty_fields" in pinfo
            and pinfo["checkout_faulty_fields"]
            and "user_email" in pinfo["checkout_faulty_fields"]):
            h("<p class='aid_error_line'>" + self._('Please provide your eMail address') + "</p>")

        if ("checkout_faulty_fields" in pinfo
            and pinfo["checkout_faulty_fields"]
            and "user_email_taken" in pinfo["checkout_faulty_fields"]):
            h("<p class='aid_error_line'>" +
              self._('This eMail address is reserved by a user. Please log in or provide an alternative eMail address')
              + "</p>")

        h("<p>")
        if "user_email_sys" in pinfo and pinfo["user_email_sys"]:
            h((self._("Your eMail:") + " %s") % pinfo["user_email"])
        else:
            h((self._('Your eMail:') + ' <input type="text" name="user_email" value="%s" />')
              % pinfo["user_email"])
        h("</p><p>")

        h(self._("You may leave a comment (optional)") + ":<br>")
        h('<textarea name="user_comments">')

        if "user_ticket_comments" in pinfo:
            h(pinfo["user_ticket_comments"])

        h("</textarea>")

        h("</p>")
        h("<p>&nbsp;</p>")

        h('<div style="text-align: center;">')
        h(('  <input type="submit" name="checkout_continue_claiming" class="aid_btn_green" value="%s" />')
          % self._("Continue claiming*"))
        h(('  <input type="submit" name="checkout_submit" class="aid_btn_green" value="%s" />')
          % self._("Confirm these changes**"))
        h('<span style="margin-left:150px;">')
        h(('  <input type="submit" name="cancel" class="aid_btn_red" value="%s" />')
          % self._("!Delete the entire request!"))
        h('</span>')
        h('</div>')
        h("</form>")
        h('</div>')

        h('<div id="aid_person_names" '
          'class="ui-tabs ui-widget ui-widget-content ui-corner-all"'
          'style="padding:10px;">')
        h('<table width="100%" border="0" cellspacing="0" cellpadding="4">')

        if not ulevel == "guest":
            h('<tr>')
            h("<td colspan='5'><h4>" + self._('Mark as your documents') + "</h4></td>")
            h('</tr>')

            if mark_yours:
                for idx, ticket in enumerate(mark_yours):
                    h('<tr id="aid_result%s">' % ((idx + 1) % 2))
                    h(mk_ticket_row(ticket))
                    h('</tr>')
            else:
                h('<tr>')
                h('<td width="25">&nbsp;</td>')
                h('<td colspan="4">Nothing staged as yours</td>')
                h("</tr>")

            h('<tr>')
            h("<td colspan='5'><h4>" + self._("Mark as _not_ your documents") + "</h4></td>")
            h('</tr>')

            if mark_not_yours:
                for idx, ticket in enumerate(mark_not_yours):
                    h('<tr id="aid_result%s">' % ((idx + 1) % 2))
                    h(mk_ticket_row(ticket))
                    h('</tr>')
            else:
                h('<tr>')
                h('<td width="25">&nbsp;</td>')
                h('<td colspan="4">' + self._('Nothing staged as not yours') + '</td>')
                h("</tr>")

        h('<tr>')
        h("<td colspan='5'><h4>" + self._('Mark as their documents') + "</h4></td>")
        h('</tr>')

        if mark_theirs:
            for idx, ticket in enumerate(mark_theirs):
                h('<tr id="aid_result%s">' % ((idx + 1) % 2))
                h(mk_ticket_row(ticket))
                h('</tr>')
        else:
            h('<tr>')
            h('<td width="25">&nbsp;</td>')
            h('<td colspan="4">' + self._('Nothing staged in this category') + '</td>')
            h("</tr>")

        h('<tr>')
        h("<td colspan='5'><h4>" + self._('Mark as _not_ their documents') + "</h4></td>")
        h('</tr>')

        if mark_not_theirs:
            for idx, ticket in enumerate(mark_not_theirs):
                h('<tr id="aid_result%s">' % ((idx + 1) % 2))
                h(mk_ticket_row(ticket))
                h('</tr>')
        else:
            h('<tr>')
            h('<td width="25">&nbsp;</td>')
            h('<td colspan="4">' + self._('Nothing staged in this category') + '</td>')
            h("</tr>")

        h('</table>')
        h("</div>")
        h("<p>")
        h(self._("  * You can come back to this page later. Nothing will be lost. <br />"))
        h(self._("  ** Performs all requested changes. Changes subject to permission restrictions "
                 "will be submitted to an operator for manual review."))
        h("</p>")

        h(html_icon_legend())

        return "\n".join(html)

    def tmpl_choose_profile_search_new_person_generator(self):
        def stub():
            text = self._("Create new profile")
            link = "%s/author/claim/action?associate_profile=True&pid=%s" % (CFG_SITE_URL, str(-1))
            return text, link

        return stub

    def tmpl_assigning_search_new_person_generator(self, bibrefs):
        def stub():
            text = self._("Create a new Person")
            link = "%s/author/claim/action?confirm=True&pid=%s" % (CFG_SITE_URL, str(CREATE_NEW_PERSON))

            for r in bibrefs:
                link = link + '&selection=%s' % str(r)

            return text, link

        return stub

    def tmpl_choose_profile_search_button_generator(self):
        def stub(pid):
            text = self._("This is my profile")
            link = "%s/author/claim/action?associate_profile=True&pid=%s" % (CFG_SITE_URL, str(pid))
            return text, link

        return stub

    def tmpl_assigning_search_button_generator(self, bibrefs):
        def stub(pid):
            text = self._("Attribute paper")
            link = "%s/author/claim/action?confirm=True&pid=%s" % (CFG_SITE_URL, str(pid))

            for r in bibrefs:
                link = link + '&selection=%s' % str(r)

            return text, link

        return stub

    def tmpl_choose_profile_search_bar(self):
        def stub(search_param):
            activated = True
            parameters = [('search_param', search_param)]
            link = "/author/claim/choose_profile"
            return activated, parameters, link

        return stub

    def tmpl_general_search_bar(self):
        def stub(search_param,):
            activated = True
            parameters = [('q', search_param)]
            link = "/author/claim/search"
            return activated, parameters, link

        return stub

    def tmpl_merge_profiles_search_bar(self, primary_profile):
        def stub(search_param):
            activated = True
            parameters = [('search_param', search_param), ('primary_profile', primary_profile)]
            link = "/author/claim/merge_profiles"
            return activated, parameters, link

        return stub

    def merge_profiles_check_box_column(self):
        def stub(pid):
            #link = link + '&selection='.join([str(element) for element in pidlist+prof])
            checkbox = '<input type="checkbox" name="profile" value=%s>' %(str(pid),)
            return checkbox

        return stub
    def tmpl_author_search(self, query, results, shown_element_functions):
        '''
        Generates the search for Person entities.

        @param query: the query a user issued to the search
        @type query: string
        @param results: list of results
        @type results: list
        @param search_ticket: search ticket object to inform about pending
            claiming procedure
        @type search_ticket: dict
        '''

        if not query:
            query = ""

        html = []
        h = html.append

        search_bar_activated = False
        if 'show_search_bar' in shown_element_functions.keys():
            search_bar_activated, parameters, link = shown_element_functions['show_search_bar'](query)

        if search_bar_activated:
            h('<div class="fg-toolbar ui-toolbar ui-widget-header ui-corner-tl ui-corner-tr ui-helper-clearfix" id="aid_search_bar">')
            h('<form id="searchform" action="%s" method="GET">' % (link,))
            h('Find author clusters by name. e.g: <i>Ellis, J</i>: <br>')

            for param in parameters[1:]:
                h('<input type="hidden" name=%s value=%s>' % (param[0], param[1]))

            h('<input placeholder="Search for a name, e.g: Ellis, J" type="text" name=%s style="border:1px solid #333; width:500px;" '
                        'maxlength="250" value="%s" class="focus" />' % (parameters[0][0], parameters[0][1]))
            h('<input type="submit" value="Search" />')
            h('</form>')
            if 'new_person_gen' in shown_element_functions.keys():
                new_person_text, new_person_link = shown_element_functions['new_person_gen']()
                h('<a rel="nofollow" href="%s" ><button type="button" id="new_person_link">%s' % (new_person_link, new_person_text))
                h('</button></a>')
            h('</div>')

        if not results and not query:
            h('</div>')
            return "\n".join(html)

        if query and not results:
            authemail = CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL
            h(('<strong>' + self._("We do not have a publication list for '%s'." +
                                 " Try using a less specific author name, or check" +
                                 " back in a few days as attributions are updated " +
                                 "frequently.  Or you can send us feedback, at ") +
                                 "<a rel='nofollow' href=\"mailto:%s\">%s</a>.</strong>") % (query, authemail, authemail))
            h('</div>')
            return "\n".join(html)

        show_action_button = False
        if 'button_gen' in shown_element_functions.keys():
            show_action_button = True

        # base_color = 100
        # row_color = 0
        # html table
        h('<table id="personsTable">')
        h('<!-- Table header -->\
                <thead>\
                    <tr>\
                        <th scope="col" id="" style="width:85px;">Number</th>\
                        <th scope="col" id="">Identifier</th>\
                        <th scope="col" id="">Names</th>\
                        <th scope="col" id="">IDs</th>\
                        <th scope="col" id="" style="width:350px">Papers</th>\
                        <th scope="col" id="">Link</th>')
        if show_action_button:
            h('         <th scope="col" id="">Action</th>')
        h('         </tr>\
                </thead>\
           <!-- Table body -->\
                <tbody>')
        for index, result in enumerate(results):
            # if len(results) > base_color:
                # row_color += 1
            # else:
            #     row_color = base_color - (base_color - index *
            #                 base_color / len(results)))

            pid = result['pid']
            canonical_id = result['canonical_id']

            # person row
            h('<tr id="pid'+ str(pid) + '">')
            # (TODO pageNum - 1) * personsPerPage + 1
            h('<td>%s</td>' % (index + 1))

#            for nindex, name in enumerate(names):
#                color = row_color + nindex * 35
#                color = min(color, base_color)
#                h('<span style="color:rgb(%d,%d,%d);">%s; </span>'
#                            % (color, color, color, name[0]))
            #Identifier
            if canonical_id:
                h('<td>%s</td>' % (canonical_id,))
            else:
                h('<td>%s</td>' % ('No canonical id',))
            #Names
            h('<td class="emptyName' + str(pid) + '">')
            #html.extend(self.tmpl_gen_names(names))
            h('</td>')
            # IDs
            h('<td class="emptyIDs' + str(pid) + '" >')#style="text-align:left;padding-left:35px;"
            #html.extend(self.tmpl_gen_ext_ids(external_ids))
            h('</td>')
            # Recent papers
            h('<td>')
            h(('<a rel="nofollow" href="#" id="aid_moreinfolink" class="mpid%s">'
                        '<img src="../img/aid_plus_16.png" '
                        'alt = "toggle additional information." '
                        'width="11" height="11"/> '
                        + self._('Recent Papers') +
                        '</a>')
                        % (pid))
            h('<div class="more-mpid%s" id="aid_moreinfo">' % (pid))
            h('</div>')
            h('</td>')

            #Link
            h('<td>')
            h(('<span>'
                    '<em><a rel="nofollow" href="%s/author/profile/%s" id="aid_moreinfolink" target="_blank">'
                    + self._('Publication List ') + '(%s)</a></em></span>')
                    % (CFG_SITE_URL,get_person_redirect_link(pid),
                       get_person_redirect_link(pid)))
            h('</td>')

            if show_action_button:
                action_button_text, action_button_link = shown_element_functions['button_gen'](pid)
                #Action link
                h('<td class="uncheckedProfile' + str(pid) + '" style="text-align:center">')
                # h(('<span >'
                #             '<a rel="nofollow" href="%s" class="confirmlink">'
                #             '<strong>%s</strong>' + '</a></span>')
                #             % (action_button_link, action_button_text))
                h('<a rel="nofollow" href="%s" class="confirmlink"><button type="button">%s' % (action_button_link, action_button_text))
                h('</button></a>')
                h('</td>')
            h('</tr>')
        h('</tbody>')
        h('</table>')

        return "\n".join(html)

    def old_tmpl_author_search(self, query, results,
                           search_ticket=None, author_pages_mode=True,
                           new_person_link=False, welcome_mode = False):
        '''
        Generates the search for Person entities.

        @param query: the query a user issued to the search
        @type query: string
        @param results: list of results
        @type results: list
        @param search_ticket: search ticket object to inform about pending
            claiming procedure
        @type search_ticket: dict
        '''
        linktarget = "person"

        if author_pages_mode:
            linktarget = "author"

        if not query:
            query = ""

        html = []
        h = html.append

        if welcome_mode:
            h('<form id="searchform" action="/author/claim/welcome" method="GET">')
            h('Find author clusters by name. e.g: <i>Ellis, J</i>: <br>')
            h('<input type="hidden" name="action" value="search">')
            h('<input placeholder="Search for a name, e.g: Ellis, J" type="text" name="search_param" style="border:1px solid #333; width:500px;" '
                        'maxlength="250" value="%s" class="focus" />' % query)
            h('<input type="submit" value="Search" />')
            h('</form>')
        else:
            h('<form id="searchform" action="/author/claim/search" method="GET">')
            h('Find author clusters by name. e.g: <i>Ellis, J</i>: <br>')
            h('<input placeholder="Search for a name, e.g: Ellis, J" type="text" name="q" style="border:1px solid #333; width:500px;" '
                        'maxlength="250" value="%s" class="focus" />' % query)
            h('<input type="submit" value="Search" />')
            h('</form>')

        if not results and not query:
            h('</div>')
            return "\n".join(html)

        h("<p>&nbsp;</p>")

        if query and not results:
            authemail = CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL
            h(('<strong>' + self._("We do not have a publication list for '%s'." +
                                 " Try using a less specific author name, or check" +
                                 " back in a few days as attributions are updated " +
                                 "frequently.  Or you can send us feedback, at ") +
                                 "<a rel='nofollow' href=\"mailto:%s\">%s</a>.</strong>") % (query, authemail, authemail))
            h('</div>')
            if new_person_link:
                link = "%s/author/claim/action?confirm=True&pid=%s" % (CFG_SITE_URL, str(CREATE_NEW_PERSON))
                if search_ticket:
                    for r in search_ticket['bibrefs']:
                        link = link + '&selection=%s' % str(r)
                h('<div>')
                h('<a rel="nofollow" href="%s">' % (link))
                h(self._("Create a new Person for your search"))
                h('</a>')
                h('</div>')
            return "\n".join(html)

        # base_color = 100
        # row_color = 0
        # html table
        h('<table id="personsTable">')
        h('<!-- Table header -->\
                <thead>\
                    <tr>\
                        <th scope="col" id="" style="width:85px;">Number</th>\
                        <th scope="col" id="">Identifiers</th>\
                        <th scope="col" id="">Names</th>\
                        <th scope="col" id="">IDs</th>\
                        <th scope="col" id="" style="width:350px">Papers</th>\
                        <th scope="col" id="">Link</th>\
                        <th scope="col" id="">Action</th>\
                    </tr>\
                </thead>\
           <!-- Table footer -->\
                <tfoot>\
                    <tr>\
                        <td>Footer</td>\
                    </tr>\
                </tfoot>\
           <!-- Table body -->\
                <tbody>')
        for index, result in enumerate(results):
            # if len(results) > base_color:
                # row_color += 1
            # else:
            #     row_color = base_color - (base_color - index *
            #                 base_color / len(results)))

            pid = result[0]
            names = result[1]
            papers = result[2]
            try:
                total_papers = result[3]
                if total_papers > 1:
                    papers_string = '(%s Papers)' % str(total_papers)
                elif total_papers == 1:
                    if (len(papers) == 1 and
                        len(papers[0]) == 1 and
                        papers[0][0] == 'Not retrieved to increase performances.'):
                        papers_string = ''
                    else:
                        papers_string = '(1 Paper)'
                else:
                    papers_string = '(No papers)'
            except IndexError:
                papers_string = ''

            # person row
            h('<tr id="pid'+ str(pid) + '">')
            h('<td><span>%s</span></td>' % (index + 1))

#            for nindex, name in enumerate(names):
#                color = row_color + nindex * 35
#                color = min(color, base_color)
#                h('<span style="color:rgb(%d,%d,%d);">%s; </span>'
#                            % (color, color, color, name[0]))
            #Identifiers
            h('<td>Sample identifier</td>')
            #Names
            h('<td>')
            for name in names:
                h('<span style="margin-right:20px;">%s </span>'
                            % (name[0]))
            h('</td>')
            # IDs
            h('<td>Sample Id</td>') # TODO: get id
            # recent papers
            h('<td>')
            if index < bconfig.PERSON_SEARCH_RESULTS_SHOW_PAPERS_PERSON_LIMIT:
                h(('<a rel="nofollow" href="#" id="aid_moreinfolink" class="mpid%s">'
                            '<img src="../img/aid_plus_16.png" '
                            'alt = "toggle additional information." '
                            'width="11" height="11"/> '
                            + self._('Recent Papers') +
                            '</a>')
                            % (pid))
                h('<div class="more-mpid%s" id="aid_moreinfo">' % (pid))
                #html.extend(self.tmpl_gen_papers(pid, papers))
                # if papers and index < bconfig.PERSON_SEARCH_RESULTS_SHOW_PAPERS_PERSON_LIMIT:
                #     h((self._('Showing the') + ' %d ' + self._('most recent documents:')) % len(papers))
                #     h("<ul>")

                #     for paper in papers:
                #         h("<li>%s</li>"
                #                % (format_record(int(paper[0]), "ha")))

                #     h("</ul>")
                # elif not papers:
                #     h("<p>" + self._('Sorry, there are no documents known for this person') + "</p>")
                # elif index >= bconfig.PERSON_SEARCH_RESULTS_SHOW_PAPERS_PERSON_LIMIT:
                #     h("<p>" + self._('Information not shown to increase performances. Please refine your search.') + "</p>")

                # h(('<span style="margin-left: 40px;">'
                #             '<em><a rel="nofollow" href="%s/%s/%s" target="_blank" id="aid_moreinfolink">'
                #             + self._('Publication List ') + '(%s)</a> (in a new window or tab)</em></span>')
                #             % (CFG_SITE_URL, linktarget,
                #                get_person_redirect_link(pid),
                #                get_person_redirect_link(pid)))
                h('</div>')
                h('</td>')
            else:
                h('</td>')

            #Link
            h('<td>')
            if search_ticket:
                link = "%s/author/claim/action?confirm=True&pid=%s" % (CFG_SITE_URL, pid)

                for r in search_ticket['bibrefs']:
                    link = link + '&selection=%s' % str(r)

                h(('<span style="margin-left: 120px;float:left;">'
                            '<em><a rel="nofollow" href="%s" id="confirmlink">'
                            '<strong>' + self._('YES!') + '</strong>'
                            + self._(' Attribute Papers To ') +
                            '%s %s </a></em></span>')
                            % (link, get_person_redirect_link(pid), papers_string))
            else:
                if welcome_mode:
                    link =  "%s/author/claim/welcome?action=select&pid=%s" % (CFG_SITE_URL, pid)
                    h(('<span style="margin-left: 120px;">'
                                '<em><a rel="nofollow" href="%s" id="confirmlink">'
                                '<strong>' + self._('Claim this profile!') + '</strong>'
                                +'</a></em></span>')
                                % (link))
                else:
                    h(('<span>'
                                '<em><a rel="nofollow" href="%s/%s/%s" id="aid_moreinfolink">'
                                + self._('Publication List ') + '(%s) %s </a></em></span>')
                                % (CFG_SITE_URL, linktarget,
                                   get_person_redirect_link(pid),
                                   get_person_redirect_link(pid), papers_string))

            #Action link
            h('<td><a class="actionLink" href="">Sample action</a></td>')

            h('</td>')
            h('</tr>')
        h('</tbody>')
        h('</table>')

        if new_person_link:
            link = "%s/author/claim/action?confirm=True&pid=%s" % (CFG_SITE_URL, str(CREATE_NEW_PERSON))
            if search_ticket:
                for r in search_ticket['bibrefs']:
                    link = link + '&selection=%s' % str(r)
            h('<div>')
            h('<a rel="nofollow" href="%s">' % (link))
            h(self._("Create a new Person for your search"))
            h('</a>')
            h('</div>')

        return "\n".join(html)


    def tmpl_gen_papers(self, papers):
        """
            Generates the recent papers html code.
            Returns a list of strings
        """
        html = []
        h = html.append

        if papers:
            h((self._('Showing the') + ' %d ' + self._('most recent documents:')) % len(papers))
            h("<ul>")

            for paper in papers:
                h("<li>%s</li>"
                       % (format_record(int(paper[0]), "ha")))

            h("</ul>")
        elif not papers:
            h("<p>" + self._('Sorry, there are no documents known for this person') + "</p>")
        return html

    def tmpl_gen_names(self, names):
        """
            Generates the names html code.
            Returns a list of strings
        """
        html = []
        h = html.append
        delimiter = ";"
        if names:
            for i,name in enumerate(names):
                if i == 0:
                    h('<span>%s</span>'
                            % (name[0],))
                else:
                    h('<span">%s  &nbsp%s</span>'
                            % (delimiter, name[0]))
        else:
            h('%s' % ('No names found',))
        return html


    def tmpl_gen_ext_ids(self, external_ids):
        """
            Generates the external ids html code.
            Returns a list of strings
        """
        html = []
        h = html.append

        if external_ids:
            h('<table id="externalIDsTable">')
            for key, value in external_ids.iteritems():
                h('<tr>')
                h('<td style="margin-top:5px; width:1px;  padding-right:2px;">%s:</td>' % key)
                h('<td style="padding-left:5px;width:1px;">')
                for i, item in enumerate(value):
                    if i == 0:
                        h('%s' % item)
                    else:
                        h('; %s' % item)
                h('</td>')
                h('</tr>')
            h('</table>')
        else:
            h('%s' % ('No external ids found',))

        return html


    def tmpl_welcome_start(self):
        '''
        Shadows the behaviour of tmpl_search_pagestart
        '''
        return '<div class="pagebody"><div class="pagebodystripemiddle">'


    def tmpl_welcome_remote_login_systems(self, remote_login_systems_info, uid):
        '''
        SSO landing/welcome page.
        '''
        html = []
        h = html.append
        message = self._('Congratulations! you have now successfully connected to INSPIRE as a user with userid: %s via %s!'% (str(uid), (', ').join(remote_login_systems_info.keys())))
        h('<p><b>%s</b></p>' % (message,))
        message = self._('Right now, you can verify your'
        ' publication records, which will help us to produce better publication lists and'
        ' citation statistics.')
        h('<p>%s</p>' % (message,))

        message = self._('We are currently importing your publication list from %s .'
        'When we\'re done, you\'ll see a link to verify your'
        ' publications below; please claim the papers that are yours '
        ' and remove the ones that are not. This information will be automatically processed'
        ' or be sent to our operator for approval if needed, usually within 24'
        ' hours.' % ((', ').join(remote_login_systems_info.keys()),))
        h('<p>%s</p>' % (message,))
        message = self._('If you have '
          'any questions or encounter any problems please contact us here: ')
        h('%s <a rel="nofollow" href="mailto:%s">%s</a></p>'
          % (message, CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL,
             CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL))

        return "\n".join(html)

    def tmpl_welcome_arxiv(self):
        '''
        SSO landing/welcome page.
        '''
        html = []
        h = html.append
        h('<p><b>Congratulations! you have now successfully connected to INSPIRE via arXiv.org!</b></p>')

        h('<p>Right now, you can verify your'
        ' publication records, which will help us to produce better publication lists and'
        ' citation statistics.'
        '</p>')

        h('<p>We are currently importing your publication list from arXiv.org .'
        'When we\'re done, you\'ll see a link to verify your'
        ' publications below; please claim the papers that are yours '
        ' and remove the ones that are not. This information will be automatically processed'
        ' or be sent to our operator for approval if needed, usually within 24'
        ' hours.'
        '</p>')
        h('If you have '
          'any questions or encounter any problems please contact us here: '
          '<a rel="nofollow" href="mailto:%s">%s</a></p>'
          % (CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL,
             CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL))

        return "\n".join(html)


    def tmpl_welcome_not_logged_in(self):
        '''
        Inform user that is not logged in
        '''

        html = []
        h = html.append

        message = self._('Unfortunately you cannot continue as it is seems that you are not logged in. Please login and try again.')
        h('<p>%s</p>' % (message,))
        return "\n".join(html)

    def tmpl_suggest_not_remote_logged_in_systems(self, suggested_remote_login_systems):
        '''
        suggest external systems that the user is currently not logged in through
        '''

        html = []
        h = html.append
        links = []

        for system in suggested_remote_login_systems:
            links.append('<a href=%s>%s</a>' % (bconfig.CFG_BIBAUTHORID_REMOTE_LOGIN_SYSTEMS_LINKS[system], system))

        message = self._('It is recommended to log in via as many remote login systems as possible. You can log in via the following: %s'
                                                                                                            % (', ').join(links))
        h('<p>%s</p>' % (message,))
        return "\n".join(html)

    def tmpl_welcome(self):
        '''
        SSO landing/welcome page.
        '''
        html = []
        h = html.append
        message = self._('Congratulations! you have successfully logged in!')
        h('<p><b>%s</b></p>'% (message,))

        message = self._('We are currently creating your publication list. When we\'re done, you\'ll see a link to correct your publications below.')
        h('<p>%s</p>' % (message,))

        message = self._('When the link appears we invite you to confirm the papers that are '
          'yours and to reject the ones that you are not author of. If you have '
          'any questions or encounter any problems please contact us here: ')
        h('<p>%s'
          '<a rel="nofollow" href="mailto:%s">%s</a></p>'
          % (message, CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL,
             CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL))

        return "\n".join(html)


    def tmpl_claim_profile(self):
        '''
        claim profile
        '''
        html = []
        h = html.append
        message = self._('Unfortunately it was not possible to automatically match your arXiv account to an INSPIRE person profile.'
                         'Please choose the correct person profile from the list below.'
                         ' If your profile is not in the list or none of them represents you correctly, please select the one which fits you best or choose '
                         'to create a new one; keep in mind that no matter what your choice is, you will be able to correct your publication list until it contains all of your publications.'
                         ' In case of any question please do not hesitate to contact us at ')
        h('<p>%s <a rel="nofollow" href="mailto:%s">%s</a></p>' % (message, CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL,
             CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL))

        return "\n".join(html)


    def tmpl_profile_option(self, top5_list):
        '''
        show profile option
        '''
        html = []
        h = html.append

        h('<table border="0"> <tr>')
        for pid in top5_list:
            pid = int(pid)
            canonical_id = get_canonical_name_of_author(pid)
            full_name = get_person_names_from_id(pid)
            name_length = 0
            most_common_name = ""
            for name in full_name:
                if len(name[0]) > name_length:
                    most_common_name = name [0]

            if len(full_name) > 0:
                name_string = most_common_name
            else:
                name_string = "[No name available]  "

            if len(canonical_id) > 0:
                canonical_name_string = "(" + canonical_id[0][0] + ")"
                canonical_id = canonical_id[0][0]
            else:
                canonical_name_string = "(" + pid + ")"
                canonical_id = pid

            h('<td>')
            h('%s ' % (name_string))
            h('<a href="%s/author/profile/%s" target="_blank"> %s </a>' % (CFG_SITE_URL, canonical_id, canonical_name_string))
            h('</td>')
            h('<td>')
            h('<INPUT TYPE="BUTTON" VALUE="This is my profile" ONCLICK="window.location.href=\'welcome?chosen_profile=%s\'">' % (str(pid)))
            h('</td>')
            h('</tr>')
        h('</table>')
        h('</br>')
        if top5_list:
            h('If none of the above is your profile it seems that you cannot match any of the existing accounts.</br>Would you like to create one?')
            h('<INPUT TYPE="BUTTON" VALUE="Create an account" ONCLICK="window.location.href=\'welcome?chosen_profile=%s\'">' % (str(-1)))


        else:
            h('It seems that you cannot match any of the existig accounts.</br>Would you like to create one?')
            h('<INPUT TYPE="BUTTON" VALUE="Create an account" ONCLICK="window.location.href=\'welcome?chosen_profile=%s\'">' % (str(-1)))

        return "\n".join(html)

    def tmpl_welcome_select_empty_profile(self):
        html = []
        h = html.append
        message = self._("If your profile has not been presented, it seems that you cannot match any of the existing accounts.")
        h('<p>%s</p>' % message)
        h('<table border="0"> <tr>')
        h('<td>')
        h('%s ' % (self._('Would you like to create a new one?')))
        h('</td>')
        h('<td>')
        h('<INPUT TYPE="BUTTON" VALUE="Create a profile" ONCLICK="window.location.href=\'welcome?action=%s&pid=%s\'">' % ('select', str(-1)))
        h('</td>')
        h('</tr>')
        h('</table>')
        h('</br>')
        return "\n".join(html)

    def tmpl_welcome_probable_profile_suggestion(self, probable_profile_suggestion_info, last_viewed_profile_suggestion_info):
        '''
        Suggest the most likely profile that the user can be based on his papers in external systems that is logged in through.
        '''
        html = []
        h = html.append
        last_viewed_profile_message = self._("The following profile is the one you were viewing before logging in: ")
        probable_profile_message = self._("We strongly believe that your profile is the following: ")

        h('<table border="0">')
        if probable_profile_suggestion_info:
            h('<tr>')
            h('<td>')
            h('%s %s ' % (probable_profile_message, probable_profile_suggestion_info['name_string']))
            h('<a href="%s/author/profile/%s" target="_blank"> %s </a>' % (CFG_SITE_URL, probable_profile_suggestion_info['canonical_id'], 
                                                                           probable_profile_suggestion_info['canonical_name_string']))
            h('</td>')
            h('<td>')
            h('<a rel="nofollow" href="action?associate_profile=True&pid=%s" class="confirmlink"><button type="button">%s' % (str(probable_profile_suggestion_info['pid']), 'This is my profile'))
            h('</td>')
            h('</tr>')
        if not last_viewed_profile_suggestion_info:
            last_viewed_profile_message = self._("Unfortunately the profile you were viewing before logging in is not available.")
            h('</table>')
            h('%s' % (last_viewed_profile_message))
        else:
            h('<tr>')
            h('<td>')
            h('%s %s ' % (last_viewed_profile_message, last_viewed_profile_suggestion_info['name_string']))
            h('<a href="%s/author/profile/%s" target="_blank"> %s </a>' % (CFG_SITE_URL, last_viewed_profile_suggestion_info['canonical_id'], 
                                                                           last_viewed_profile_suggestion_info['canonical_name_string']))
            h('</td>')
            h('<td>')
            
            h('<a rel="nofollow" href="action?associate_profile=True&pid=%s" class="confirmlink"><button type="button">%s' % (str(last_viewed_profile_suggestion_info['pid']), 'This is my profile'))
            h('</td>')
            h('</tr>')      
            h('</table>')
        h('</br>')
        return "\n".join(html)

    def tmpl_profile_not_available(self):
        '''
        show profile option
        '''
        html = []
        h = html.append
        message = self._('Unfortunately the profile that you previously chose is no longer available. A new empty profile has been created. You will be able to correct '
          'your publication list until it contains all of your publications.')
        h('<p>%s</p>' % (message,))
        return "\n".join(html)

    def tmpl_profile_assigned_by_user(self):
        html = []
        h = html.append
        message = self._(' Congratulations you have successfully claimed the chosen profile.')
        h('<p>%s</p>'%(message,))
        return "\n".join(html)


    def tmpl_claim_stub(self, person='-1'):
        '''
        claim stub page
        '''
        html = []
        h = html.append

        h(' <ul><li><a rel="nofollow" href=%s> Login through arXiv.org </a> <small>' % bconfig.BIBAUTHORID_CFG_INSPIRE_LOGIN)
        h(' - Use this option if you have an arXiv account and have claimed your papers in arXiv.')
        h('(If you login through arXiv.org, INSPIRE will immediately verify you as an author and process your claimed papers.) </small><br><br>')
        h(' <li><a rel="nofollow" href=%s/author/claim/%s?open_claim=True> Continue as a guest </a> <small>' % (CFG_SITE_URL, person))
        h(' - Use this option if you DON\'T have an arXiv account, or you have not claimed any paper in arXiv.')
        h('(If you login as a guest, INSPIRE will need to confirm you as an author before processing your claimed papers.) </small><br><br>')
        h('If you login through arXiv.org we can verify that you are the author of these papers and accept your claims rapidly, '
          'as well as adding additional claims from arXiv. <br>If you choose not to login via arXiv your changes will '
          'be publicly visible only after our editors check and confirm them, usually a few days.<br>  '
          'Either way, claims made on behalf of another author will go through our staff and may take longer to display. '
          'This applies as well to papers which have been previously claimed, by yourself or someone else.')
        return "\n".join(html)

    def tmpl_welcome_link(self):
        '''
        Creates the link for the actual user action.
        '''
        return '<a rel="nofollow" href=action?checkout=True><b>' + \
            self._('Correct my publication lists!') + \
            '</b></a>'

    def tmpl_welcome_personid_association(self, pid):
        """
        """
        canon_name = get_canonical_name_of_author(pid)
        head = "<br>"
        if canon_name:
            message = self._("Your external_systems accounts are associated "
                    "with person %s." % (canon_name[0][0],))
        else:
            message = self._("Warning: your external systems accounts account are associated with an empty profile. "
                    "This can happen if it is the first time you log in and you do not have any "
                    "paper directly claimed from your external_systems accounts"
                    " In this case, you are welcome to search and claim your papers to your"
                    " new profile manually, or please contact us to get help.")
        body = (message)
        message = self._("You are very welcome to contact us shall you need any help or explanation"
                 " about the management of"
                 " your profile page"
                 " in INSPIRE and it's connections with arXiv.org: ")
        body += ("<br>%s" % (message,))
        body += ('''<a href="mailto:authors@inspirehep.net?subject=Help on arXiv.org SSO login and paper claiming"> authors@inspirehep.net </a>''')
        tail = "<br>"

        return head + body + tail

    def tmpl_welcome_autoclaim_remote_login_systems_papers(self, remote_login_systems_papers, cached_ids_association, auto_claim_list):
        papers_found = False
        html = []
        h = html.append
        message = self._("<br><br><strong>We have got "
                                "the following papers from the remote login systems you are logged in through: </strong><br>")
        h('<p>%s</p>' % message)
        h('<table class="idsAssociationTable" id="idsAssociationClaim">')
        h('<!-- Table header -->\
                <thead>\
                    <tr>\
                        <th scope="col" id="">%s</th>\
                        <th scope="col" id="">%s</th>\
                        <th scope="col" id="">%s</th>\
                        <th scope="col" id="">%s</th>\
                       </tr>\
                </thead>\
           <!-- Table body -->\
                <tbody>' % (self._("External system"), self._("External id"), self._("Resolved record id"), self._("Status")))

        for system in remote_login_systems_papers.keys():
            if remote_login_systems_papers[system]:
                papers_found = True

            for paper in remote_login_systems_papers[system]:
                h('<tr>')
                h('<td>')
                h('%s ' % (system))
                h('</td>')
                h('<td>')
                h('%s ' % (paper))
                h('</td>')
                h('<td>')
                key = (bconfig.CFG_BIBAUTHORID_REMOTE_LOGIN_SYSTEMS_IDENTIFIER_TYPES[system], paper)

                if key in cached_ids_association.keys() and cached_ids_association[key] != -1:
                    recid = cached_ids_association[key]
                    h('%s ' % (recid,))

                    if recid in auto_claim_list:
                        status = "Paper in the process of auto-claimed by the system."
                    else:
                        status = "Paper already claimed."
                else:
                    h(self._('Not available'))
                    status = "Paper not present."

                h('</td>')
                h('<td>')
                h('%s ' % (status,))
                h('</td>')
                h('</tr>')
        h('</tbody>')
        h('</table>')
        h('</br>')

        if not papers_found:
            html = []
            h = html.append
            h('<p>%s</p>' % "We have got no papers from the remote login systems that you are currently logged in through. <br>")

        return "\n".join(html)

    def tmpl_welcome_remote_login_systems_papers(self, remote_login_systems_papers, cached_ids_association):
        papers_found = False
        html = []
        h = html.append
        message = self._("<br><br><strong>We have got "
                                "the following papers from the remote login systems you are logged in through: </strong><br>")
        h('<p>%s</p>' % message)
        h('<table class="idsAssociationTable" id="idsAssociationReview">')
        h('<!-- Table header -->\
                <thead>\
                    <tr>\
                        <th scope="col" id="">%s</th>\
                        <th scope="col" id="">%s</th>\
                        <th scope="col" id="">%s</th>\
                       </tr>\
                </thead>\
           <!-- Table body -->\
                <tbody>' % (self._("External system"), self._("External id"), self._("Resolved record id")))
        for system in remote_login_systems_papers.keys():
            if remote_login_systems_papers[system]:
                papers_found = True

            for paper in remote_login_systems_papers[system]:
                h('<tr>')
                h('<td>')
                h('%s ' % (system))
                h('</td>')
                h('<td>')
                h('%s ' % (paper))
                h('</td>')
                h('<td>')
                key = (bconfig.CFG_BIBAUTHORID_REMOTE_LOGIN_SYSTEMS_IDENTIFIER_TYPES[system], paper)

                if key in cached_ids_association.keys() and cached_ids_association[key] != -1:
                    recid = cached_ids_association[key]
                    h('%s ' % (recid,))
                else:
                    h(self._('Not available'))

                h('</td>')
                h('</tr>')

        h('</tbody>')
        h('</table>')
        h('</br>')

        if not papers_found:
            html = []
            message = self._("<br><br>We have got "
                                "the following papers from the remote login systems you are logged in through: <br>")
            h('<p>%s</p>' % "We have got no papers from the remote login systems that you are currently logged in through. <br>")
        return "\n".join(html)

    def tmpl_welcome_arXiv_papers(self, paps):
        '''
        Creates the list of arXiv papers
        '''
        plist = "<br><br>"
        if paps:
            plist = plist + "We have got and we are about to automatically claim for You the following papers from arXiv.org: <br>"
            for p in paps:
                plist = plist + "  " + str(p) + "<br>"
        else:
            plist = "We have got no papers from arXiv.org which we could claim automatically for You. <br>"
        return plist

    def tmpl_welcome_end(self):
        '''
        Shadows the behaviour of tmpl_search_pageend
        '''
        return '</div></div>'


    def tmpl_choose_profile(self, failed):
        '''
        SSO landing/choose_profile page.
        '''
        html = []
        h = html.append
        if failed:
            h('<p><strong><font color="red">Unfortunately the profile you chose is no longer available.</font></strong></p>')
            h('<p>We apologise for the inconvenience. Please select another one.</br>Keep in mind that you can create an empty profile and then claim all of your papers in it.')
        else:
            h('<p><b>Congratulations! You have now successfully connected to INSPIRE via arXiv.org!</b></p>')
            h('<p>Before you proceed you need to help us locating your profile.')
        h('If you have '
          'any questions or encounter any problems please contact us here: '
          '<a rel="nofollow" href="mailto:%s">%s</a></p>'
          % (CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL,
             CFG_BIBAUTHORID_AUTHOR_TICKET_ADMIN_EMAIL))

        return "\n".join(html)

    def tmpl_tickets_admin(self, tickets=[]):
        '''
        Open tickets short overview for operators.
        '''
        html = []
        h = html.append
        if len(tickets) > 0:
            h('List of open tickets: <br><br>')
            for t in tickets:
                h('<a rel="nofollow" href=%(cname)s#tabTickets> %(longname)s - (%(cname)s - PersonID: %(pid)s): %(num)s open tickets. </a><br>'
                  % ({'cname':str(t[1]), 'longname':str(t[0]), 'pid':str(t[2]), 'num':str(t[3])}))
        else:
            h('There are currently no open tickets.')
        return "\n".join(html)

    def loading_html(self):
        return '<img src=/img/ui-anim_basic_16x16.gif> Loading...'

    def tmpl_personnametitle(self, person_info, ln, loading=False):
        _ = gettext_set_language(ln)

        if loading:
            html_header = '<span id="personnametitle">' + self.loading_html() + '</span>'
        else:
            if not person_info['name']:
                display_name = " Name not available"
            else:
                display_name = str(person_info['name']) + ' (' + str(person_info['canonical_name']) + ')'

            html_header = ('<h1><span id="personnametitle">%s</span></h1>'
                          % (display_name))
            html_header += ('<span id="personnametitle">%s</span>'
                            % (_("Author Managment Page")))

        return html_header


    def tmpl_profile_managment(self, ln, person_data, arxiv_data, orcid_data, claim_paper_data, ext_ids, autoclaim_data, support_data):
        '''
        '''
        _ = gettext_set_language(ln)

        html = list()

        html_header = self.tmpl_personnametitle(person_data, ln, loading=False)
        html.append(html_header)

        html_arxiv = self.tmpl_arxiv_box(arxiv_data, ln, loading=False)
        html_orcid = self.tmpl_orcid_box(orcid_data, ln, loading=False)
        html_claim_paper = self.tmpl_claim_paper_box(claim_paper_data, ln, loading=False)
        html_ext_ids = self.tmpl_ext_ids_box(ext_ids, ln, loading=False)
        html_autoclaim = self.tmpl_autoclaim_box(autoclaim_data, ln, loading=True)
            
        html_support = self.tmpl_support_box(support_data, ln, loading=False)

        g = self._grid

        if not autoclaim_data['hidden']:
            left_g = g(3, 1)(
                              g(1, 1, cell_padding=5)(html_arxiv),
                              g(1, 1, cell_padding=5)(html_claim_paper),
                              g(1, 1, cell_padding=5)(html_autoclaim))
        else:
            left_g = g(2, 1)(
                              g(1, 1, cell_padding=5)(html_arxiv),
                              g(1, 1, cell_padding=5)(html_claim_paper))
        page = g(1, 2)(
                      left_g,
                      g(3, 1)(
                              g(1, 1, cell_padding=5)(html_orcid),
                              g(1, 1, cell_padding=5)(html_ext_ids),
                              g(1, 1, cell_padding=5)(html_support))
                      )
        html.append(page)

        return ' '.join(html)

    def tmpl_print_searchresultbox(self, bid, header, body):
        """ Print a nicely formatted box for search results. """

        # first find total number of hits:
        out = ('<table class="searchresultsbox" ><thead><tr><th class="searchresultsboxheader">'
            + header + '</th></tr></thead><tbody><tr><td id ="%s" class="searchresultsboxbody">' % bid
            + body + '</td></tr></tbody></table>')
        return out

    def tmpl_arxiv_box(self, arxiv_data, ln, add_box=True, loading=True):
        _ = gettext_set_language(ln)
        html_head = _("<strong> Login with your arXiv.org account </strong>")

        if arxiv_data['login'] == True:
            if arxiv_data['view_own_profile'] == True:
                html_arxiv = _("You have succesfully logged in through arXiv. You can now manage your profile accordingly.</br>")
            else:
                html_arxiv = _("You have succesfully logged in through arXiv.</br><div><font color='red'>However the profile you are currently viewing is not your profile.</font>")
                html_arxiv += '<a rel="nofollow" href="%s" class="confirmlink"><button type="button">%s</div>' % (arxiv_data['own_profile_link'], _(arxiv_data['own_profile_text']) )

            html_arxiv += '</br><div><a rel="nofollow" href="%s" class="confirmlink"><button type="button">%s</div>' % (arxiv_data['logout_link'], _(arxiv_data['logout_text']))
        else:
            html_arxiv = _("Please login through arXiv.org to verify that you are the owner of this"
                            " profile and update your paper list automatically. You may also proceed"
                            " as a guest user, then your input will be processed by our staff and "
                            "thus might take longer to display.</br>")
            html_arxiv += '</br><div><a rel="nofollow" href="%s" class="confirmlink"><button type="button">%s</div>' % (arxiv_data['login_link'], _(arxiv_data['login_text']) )
        if loading:
            html_arxiv = self.loading_html()
        if add_box:
            arxiv_box = self.tmpl_print_searchresultbox('arxiv', html_head, html_arxiv)
            return arxiv_box
        else:
            return html_arxiv

    def tmpl_orcid_box(self, orcid_data, ln, add_box=True, loading=True):
        _ = gettext_set_language(ln)

        html_head = _("<strong> Connect this profile to an ORCID Id </strong>")
        html_orcid = _("The Open Researcher and Contributor ID provides a persistent digital identifier"
                       " that distinguishes you from every other researcher in the world and supports "
                       "automated linkages between you and your professional activities.</br>")

        if orcid_data['orcids']:
            html_orcid += _('This profile is already connected to the following orcid: %s</br>' % (orcid_data[0],))
            html_orcid += '</br><div><a rel="nofollow" href="%s" class="confirmlink"><button type="button">%s</div>' % ("mpla.com", _("Orcid publication list") )
        else:
            if orcid_data['arxiv_login'] and (orcid_data['own_profile'] or orcid_data['add_power']):
                html_orcid += '</br><div><a rel="nofollow" href="%s" class="confirmlink"><button type="button">%s</div>' % (orcid_data['add_link'],
                                                                                                                             _(orcid_data['add_text']) )
            else:
                html_orcid += '</br><div><a rel="nofollow" href="%s" class="confirmlink"><button type="button">%s</div>' % (orcid_data['suggest_link'],
                                                                                                                         _(orcid_data['suggest_text']) )                
        if loading:
            html_orcid = self.loading_html()
        if add_box:
            orcid_box = self.tmpl_print_searchresultbox('orcid', html_head, html_orcid)
            return orcid_box
        else:
            return html_orcid

    def tmpl_claim_paper_box(self, claim_paper_data, ln, add_box=True, loading=True):
        _ = gettext_set_language(ln)

        html_head = _("<strong> Claim papers for this profile </strong>")
        html_claim_paper = _("If you claim papers on INSPIRE, you make sure that your publications and citations"
                       " are being shown correctly on your pofile. You can also assi9gn publication to other "
                       "authors and colleagues - that way you can also help us providing more accurate publication"
                       " and citations statistics on INSPIRE.</br>")

        html_claim_paper += '</br><div><a rel="nofollow" href="%s" class="confirmlink"><button type="button">%s</div>'  % (claim_paper_data['link'], 
                                                                                                                                _(claim_paper_data['text']))

        if loading:
            html_claim_paper = self.loading_html()
        if add_box:
            claim_paper_box = self.tmpl_print_searchresultbox('claim_paper', html_head, html_claim_paper)
            return claim_paper_box
        else:
            return html_claim_paper

    def tmpl_ext_ids_box(self, ext_ids, ln, add_box=True, loading=True):
        _ = gettext_set_language(ln)

        html_head = _("<strong> External Ids </strong>")
        html_etx_ids = ''
        if ext_ids:
            html_etx_ids = '<tr>'
        else:
            html_etx_ids = _("There are no available external ids")

        for idType in ext_ids.keys():
            html_etx_ids += '<td>' + str(idType) +'</td>' + '<td>' + str(ext_ids[idType]) +'</td>'

        if ext_ids:
            html_etx_ids = '</tr>'

        if loading:
            html_etx_ids = self.loading_html()
        if add_box:
            etx_ids_box = self.tmpl_print_searchresultbox('external_ids', html_head, html_etx_ids)
            return etx_ids_box
        else:
            return html_etx_ids
    # for ajax requests add_box and loading are false
    def tmpl_autoclaim_box(self, autoclaim_data, ln, add_box=True, loading=True): 
        _ = gettext_set_language(ln)
        
        html_head = None

        if autoclaim_data['hidden']:
            return None
        if loading:
            html_head = _("<strong> Autoclaim Papers </strong>")
            html_autoclaim = _("<span id=\"autoClaimMessage\">Please wait as we are claiming %s papers from external systems to your"
                               " Inspire profile</span></br>"% (str(autoclaim_data["num_of_claims"])))
            
            html_autoclaim += self.loading_html();
        else:
            html_autoclaim = ''
            if autoclaim_data["successfull_claims"]:
                html_autoclaim += _("<span id=\"autoClaimSuccessMessage\">The following %s papers were successfully claimed to your"
                                   " profile</span></br>"% (str(autoclaim_data["num_of_successfull_claims"])))
                html_autoclaim += '<table border="0" cellpadding="5" cellspacing="5" width="30%"><tr>'
                html_autoclaim += '<th>External System Id</th><th>Record id</th></tr>'

                for rec in autoclaim_data['successfull_recids'].keys()[:5]:
                    html_autoclaim += '<tr><td>' + str(autoclaim_data['successfull_recids'][rec]) +'</td>' + '<td>' + str(rec) +'</td></tr>'
                html_autoclaim += '</table>'
            
            if autoclaim_data["unsuccessfull_claims"]:
                html_autoclaim += _("<span id=\"autoClaimUnSuccessMessage\">The following %s papers were unsuccessfully claimed. Do you want"
                                   " to review the claiming now?</span></br>"% (str(autoclaim_data["num_of_unsuccessfull_claims"])))
                html_autoclaim += '<table border="0" cellpadding="5" cellspacing="5" width="30%"><tr>'
                html_autoclaim += '<th>External System Id</th><th>Record id</th></tr>'

                for rec in autoclaim_data['unsuccessfull_recids'].keys()[:5]:
                    html_autoclaim += '<tr><td>' + str(autoclaim_data['unsuccessfull_recids'][rec]) +'</td>' + '<td>' + str(rec) +'</td></tr>'
                html_autoclaim += '</table>'    
                html_autoclaim += '</br><div><a rel="nofollow" href="%s" class="confirmlink"><button type="button">%s</div>'  % (autoclaim_data["link"], 
                                                                                                                                _(autoclaim_data['text']))

        if add_box:
            autoclaim_box = self.tmpl_print_searchresultbox('autoclaim', html_head, html_autoclaim)
            return autoclaim_box
        else:
            return html_autoclaim

    def tmpl_support_box(self, support_data, ln, add_box=True, loading=True):
        _ = gettext_set_language(ln)

        html_head = _("<strong> Contact and support </strong>")
        html_support = _("Please, contact our support if you need any kind of help or if you want to suggest"
                       " us  new ideas. We will get back to you quickly.</br>")

        html_support += '</br><div><a rel="nofollow" href="%s" class="confirmlink"><button type="button">%s</div>'  % (support_data['merge_link'], 
                                                                                                                                  _(support_data['merge_text'])) 
                                                                                                                            

        html_support += '</br><div><a rel="nofollow" href="%s" class="confirmlink"><button type="button">%s</div>'  % (support_data['problem_link'], 
                                                                                                                            _(support_data['problem_text']))
        html_support += '</br><div><a rel="nofollow" href="%s" class="confirmlink"><button type="button">%s</div>'  % (support_data['help_link'], 
                                                                                                                            _(support_data['help_text']))
        if loading:
            html_support = self.loading_html()
        if add_box:
            support_box = self.tmpl_print_searchresultbox('support', html_head, html_support)
            return support_box
        else:
            return html_support

    def tmpl_open_table(self, width_pcnt=False, cell_padding=False, height_pcnt=False):
        options = []

        if height_pcnt:
            options.append('height=%s' % height_pcnt)

        if width_pcnt:
            options.append('width=%s' % width_pcnt)
        else:
            options.append('width=100%')

        if cell_padding:
            options.append('cellpadding=%s' % cell_padding)
        else:
            options.append('cellpadding=0')

        return '<table border=0 %s >' % ' '.join(options)

    def tmpl_close_table(self):
        return "</table>"

    def tmpl_open_row(self):
        return "<tr>"
    def tmpl_close_row(self):
        return "</tr>"
    def tmpl_open_col(self):
        return "<td valign='top'>"
    def tmpl_close_col(self):
        return "</td>"

    def _grid(self, rows, cols, table_width=False, cell_padding=False):
        tmpl = self
        def cont(*boxes):
            out = []
            h = out.append
            idx = 0
            h(tmpl.tmpl_open_table(width_pcnt=table_width, cell_padding=cell_padding))
            for _ in range(rows):
                h(tmpl.tmpl_open_row())
                for _ in range(cols):
                    h(tmpl.tmpl_open_col())
                    h(boxes[idx])
                    idx += 1
                    h(tmpl.tmpl_close_col())
                h(tmpl.tmpl_close_row())
            h(tmpl.tmpl_close_table())
            return '\n'.join(out)
        return cont

    def tmpl_message_form(self):
        html = []
        h = html.append
        #h('<div style="display: block; width: 600px; text-align: left;">')
        h('<div style="width:100%; height: 600px;">'
        
            '<div  style="display: table; border-radius: 10px; padding: 20px; color: #0900C4; font: Helvetica 12pt;border: 1px solid black; margin: 0px auto;">'

                '<form action="mailto:admin@example.com" enctype="text/plain" method="post">'
                  '<fieldset style="border: 0; display: inline-block;">'
                    '<p><label for="Name"> Name: </label><input style="float: right;" name="Name" type="text"  size="40"></p>'
                    '<p><label for="E-mail"> E-mail address: </label><input style="float: right;" name="E-mail" type="email" size="40"></p>'
                    '<p>Comment:</p>'

                    '<p><textarea name="Comment" cols="55" rows="5" id="Comment"></textarea></p>'
                 '</fieldset>'
                 '<button style="display: block; margin: 0 auto;" type="submit" name="Submit">Submit</button>'

               '</form>'
        
            '</div>'
        
        '</div>')


        return ' '.join(html)
    # pylint: enable=C0301

verbiage_dict = {'guest': {'confirmed': 'Papers',
                           'repealed': 'Papers removed from this profile',
                           'review': 'Papers in need of review',
                           'tickets': 'Open Tickets', 'data': 'Data',
                           'confirmed_ns': 'Papers of this Person',
                           'repealed_ns': 'Papers _not_ of this Person',
                           'review_ns': 'Papers in need of review',
                           'tickets_ns': 'Tickets for this Person',
                           'data_ns': 'Additional Data for this Person'},
                 'user': {'owner': {'confirmed': 'Your papers',
                                    'repealed': 'Not your papers',
                                    'review': 'Papers in need of review',
                                    'tickets': 'Your tickets', 'data': 'Data',
                                    'confirmed_ns': 'Your papers',
                                    'repealed_ns': 'Not your papers',
                                    'review_ns': 'Papers in need of review',
                                    'tickets_ns': 'Your tickets',
                                    'data_ns': 'Additional Data for this Person'},
                          'not_owner': {'confirmed': 'Papers',
                                        'repealed': 'Papers removed from this profile',
                                        'review': 'Papers in need of review',
                                        'tickets': 'Your tickets', 'data': 'Data',
                                        'confirmed_ns': 'Papers of this Person',
                                        'repealed_ns': 'Papers _not_ of this Person',
                                        'review_ns': 'Papers in need of review',
                                        'tickets_ns': 'Tickets you created about this person',
                                        'data_ns': 'Additional Data for this Person'}},
                 'admin': {'confirmed': 'Papers',
                           'repealed': 'Papers removed from this profile',
                           'review': 'Papers in need of review',
                           'tickets': 'Tickets', 'data': 'Data',
                           'confirmed_ns': 'Papers of this Person',
                           'repealed_ns': 'Papers _not_ of this Person',
                           'review_ns': 'Papers in need of review',
                           'tickets_ns': 'Request Tickets',
                           'data_ns': 'Additional Data for this Person'}}

buttons_verbiage_dict = {'guest': {'mass_buttons': {'no_doc_string': 'Sorry, there are currently no documents to be found in this category.',
                                                    'b_confirm': 'Yes, those papers are by this person.',
                                                    'b_repeal': 'No, those papers are not by this person',
                                                    'b_to_others': 'Assign to other person',
                                                    'b_forget': 'Forget decision'},
                                   'record_undecided': {'alt_confirm': 'Confirm!',
                                                        'confirm_text': 'Yes, this paper is by this person.',
                                                        'alt_repeal': 'Rejected!',
                                                        'repeal_text': 'No, this paper is <i>not</i> by this person',
                                                        'to_other_text': 'Assign to another person',
                                                        'alt_to_other': 'To other person!'},
                                   'record_confirmed': {'alt_confirm': 'Confirmed.',
                                                        'confirm_text': 'Marked as this person\'s paper',
                                                        'alt_forget': 'Forget decision!',
                                                        'forget_text': 'Forget decision.',
                                                        'alt_repeal': 'Repeal!',
                                                        'repeal_text': 'But it\'s <i>not</i> this person\'s paper.',
                                                        'to_other_text': 'Assign to another person',
                                                        'alt_to_other': 'To other person!'},
                                   'record_repealed': {'alt_confirm': 'Confirm!',
                                                       'confirm_text': 'But it <i>is</i> this person\'s paper.',
                                                       'alt_forget': 'Forget decision!',
                                                       'forget_text': 'Forget decision.',
                                                       'alt_repeal': 'Repealed',
                                                       'repeal_text': 'Marked as not this person\'s paper',
                                                       'to_other_text': 'Assign to another person',
                                                       'alt_to_other': 'To other person!'}},
                         'user': {'owner': {'mass_buttons': {'no_doc_string': 'Sorry, there are currently no documents to be found in this category.',
                                                             'b_confirm': 'These are mine!',
                                                             'b_repeal': 'These are not mine!',
                                                             'b_to_others': 'It\'s not mine, but I know whose it is!',
                                                             'b_forget': 'Forget decision'},
                                            'record_undecided': {'alt_confirm': 'Mine!',
                                                                 'confirm_text': 'This is my paper!',
                                                                 'alt_repeal': 'Not mine!',
                                                                 'repeal_text': 'This is not my paper!',
                                                                 'to_other_text': 'Assign to another person',
                                                                 'alt_to_other': 'To other person!'},
                                            'record_confirmed': {'alt_confirm': 'Not Mine.',
                                                                 'confirm_text': 'Marked as my paper!',
                                                                 'alt_forget': 'Forget decision!',
                                                                 'forget_text': 'Forget assignment decision',
                                                                 'alt_repeal': 'Not Mine!',
                                                                 'repeal_text': 'But this is mine!',
                                                                 'to_other_text': 'Assign to another person',
                                                                 'alt_to_other': 'To other person!'},
                                            'record_repealed': {'alt_confirm': 'Mine!',
                                                                'confirm_text': 'But this is my paper!',
                                                                'alt_forget': 'Forget decision!',
                                                                'forget_text': 'Forget decision!',
                                                                'alt_repeal': 'Not Mine!',
                                                                'repeal_text': 'Marked as not your paper.',
                                                                'to_other_text': 'Assign to another person',
                                                                'alt_to_other': 'To other person!'}},
                                  'not_owner': {'mass_buttons': {'no_doc_string': 'Sorry, there are currently no documents to be found in this category.',
                                                                 'b_confirm': 'Yes, those papers are by this person.',
                                                                 'b_repeal': 'No, those papers are not by this person',
                                                                 'b_to_others': 'Assign to other person',
                                                                 'b_forget': 'Forget decision'},
                                                'record_undecided': {'alt_confirm': 'Confirm!',
                                                                     'confirm_text': 'Yes, this paper is by this person.',
                                                                     'alt_repeal': 'Rejected!',
                                                                     'repeal_text': 'No, this paper is <i>not</i> by this person',
                                                                     'to_other_text': 'Assign to another person',
                                                                     'alt_to_other': 'To other person!'},
                                                'record_confirmed': {'alt_confirm': 'Confirmed.',
                                                                     'confirm_text': 'Marked as this person\'s paper',
                                                                     'alt_forget': 'Forget decision!',
                                                                     'forget_text': 'Forget decision.',
                                                                     'alt_repeal': 'Repeal!',
                                                                     'repeal_text': 'But it\'s <i>not</i> this person\'s paper.',
                                                                     'to_other_text': 'Assign to another person',
                                                                     'alt_to_other': 'To other person!'},
                                                'record_repealed': {'alt_confirm': 'Confirm!',
                                                                    'confirm_text': 'But it <i>is</i> this person\'s paper.',
                                                                    'alt_forget': 'Forget decision!',
                                                                    'forget_text': 'Forget decision.',
                                                                    'alt_repeal': 'Repealed',
                                                                    'repeal_text': 'Marked as not this person\'s paper',
                                                                    'to_other_text': 'Assign to another person',
                                                                    'alt_to_other': 'To other person!'}}},
                         'admin': {'mass_buttons': {'no_doc_string': 'Sorry, there are currently no documents to be found in this category.',
                                                    'b_confirm': 'Yes, those papers are by this person.',
                                                    'b_repeal': 'No, those papers are not by this person',
                                                    'b_to_others': 'Assign to other person',
                                                    'b_forget': 'Forget decision'},
                                   'record_undecided': {'alt_confirm': 'Confirm!',
                                                        'confirm_text': 'Yes, this paper is by this person.',
                                                        'alt_repeal': 'Rejected!',
                                                        'repeal_text': 'No, this paper is <i>not</i> by this person',
                                                        'to_other_text': 'Assign to another person',
                                                        'alt_to_other': 'To other person!'},
                                   'record_confirmed': {'alt_confirm': 'Confirmed.',
                                                        'confirm_text': 'Marked as this person\'s paper',
                                                        'alt_forget': 'Forget decision!',
                                                        'forget_text': 'Forget decision.',
                                                        'alt_repeal': 'Repeal!',
                                                        'repeal_text': 'But it\'s <i>not</i> this person\'s paper.',
                                                        'to_other_text': 'Assign to another person',
                                                        'alt_to_other': 'To other person!'},
                                   'record_repealed': {'alt_confirm': 'Confirm!',
                                                       'confirm_text': 'But it <i>is</i> this person\'s paper.',
                                                       'alt_forget': 'Forget decision!',
                                                       'forget_text': 'Forget decision.',
                                                       'alt_repeal': 'Repealed',
                                                       'repeal_text': 'Marked as not this person\'s paper',
                                                       'to_other_text': 'Assign to another person',
                                                       'alt_to_other': 'To other person!'}}}
