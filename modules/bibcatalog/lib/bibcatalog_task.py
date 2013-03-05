# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2013 CERN.
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
BibCatalog task

Based on configured plug-ins this task will create tickets for records.
"""
import sys
import os

from invenio.bibtask import task_init, task_set_option, \
                            task_get_option, write_message, \
                            task_update_progress, \
                            task_sleep_now_if_required
from invenio.config import CFG_VERSION, \
                           CFG_SITE_SECURE_URL, \
                           CFG_BIBCATALOG_SYSTEM, \
                           CFG_PYLIBDIR
from invenio.docextract_task import split_ids, \
                                    fetch_last_updated, \
                                    store_last_updated
from invenio.search_engine import perform_request_search
from invenio.bibcatalog import bibcatalog_system
from invenio.bibcatalog_utils import record_id_from_record
from invenio.bibedit_utils import get_bibrecord
from invenio.bibrecord import record_get_field_instances, \
                              field_get_subfield_values
from invenio.pluginutils import PluginContainer


class BibCatalogTicket(object):
    """
    Represents a Ticket to create using BibCatalog API.
    """
    def __init__(self, subject="", text="", queue="", ticketid=None, recid=""):
        self.subject = subject
        self.queue = queue
        self.text = text
        self.ticketid = ticketid
        self.recid = recid

    def submit(self):
        self.ticketid = bibcatalog_system.ticket_submit(subject=self.subject,
                                                        queue=self.queue,
                                                        text=self.text,
                                                        recordid=self.recid)
        return self.ticketid


def task_check_options():
    """ Reimplement this method for having the possibility to check options
    before submitting the task, in order for example to provide default
    values. It must return False if there are errors in the options.
    """
    if not task_get_option('new') \
            and not task_get_option('modified') \
            and not task_get_option('recids') \
            and not task_get_option('collections'):
        print >>sys.stderr, 'Error: No records specified, you need' \
            ' to specify which records to run on'
        return False

    ticket_plugins = {}
    all_plugins, error_messages = load_ticket_plugins()
    if error_messages:
        # We got broken plugins. We alert only for now.
        print >>sys.stderr, "\n".join(error_messages)

    if task_get_option('tickets'):
        # specified
        for ticket in task_get_option('tickets'):
            if ticket not in all_plugins.get_enabled_plugins():
                print >>sys.stderr, 'Error: plugin %s is broken or does not exist'
                return False
            ticket_plugins[ticket] = all_plugins[ticket]
    else:
        ticket_plugins = all_plugins.get_enabled_plugins()
    task_set_option('tickets', ticket_plugins)

    if not bibcatalog_system:
        print >>sys.stderr, 'Error: no cataloging system defined'
        return False

    res = bibcatalog_system.check_system()
    if res:
        print >>sys.stderr, 'Error while checking cataloging system: %s' % \
            (res,)
    return True


def task_parse_options(key, value, opts, args):
    """ Must be defined for bibtask to create a task """
    if args and len(args) > 0:
        # There should be no standalone arguments for any bibcatalog job
        # This will catch args before the job is shipped to Bibsched
        raise StandardError("Error: Unrecognised argument '%s'." % args[0])

    if key in ('-a', '--new'):
        task_set_option('new', True)
    elif key in ('-m', '--modified'):
        task_set_option('modified', True)
    elif key in ('-c', '--collections'):
        collections = task_get_option('collections')
        if not collections:
            collections = set()
            task_set_option('collections', collections)
        for v in value.split(","):
            collections.update(perform_request_search(c=v))
    elif key in ('-r', '--recids'):
        recids = task_get_option('recids')
        if not recids:
            recids = set()
            task_set_option('recids', recids)
        recids.update(split_ids(value))
    elif key in ('-t', '--tickets'):
        tickets = task_get_option('tickets')
        if not tickets:
            tickets = set()
            task_set_option('tickets', tickets)
        for item in value.split(','):
            tickets.update(item.strip())
    elif key in ('-q', '--query'):
        query = task_get_option('query')
        if not query:
            query = set()
            task_set_option('query', query)
        query.update(value)
    return True


def task_run_core():
    """
    Main daemon task.

    Returns True when run successfully. False otherwise.
    """
    tickets_to_apply = task_get_option('tickets')
    write_message("Ticket plugins found: %s" %
                  (str(tickets_to_apply),), verbose=9)

    records_concerned = load_records()
    write_message("Number of records found: %i" %
                  (len(records_concerned),), verbose=9)


    # CHECK IF TICKET CREATED. recid Y in custom field in queue X

    records_processed = []
    for record in records_concerned:
        task_update_progress("Processing records %s/%s (%i %%)" \
                             % (len(records_processed), len(records_concerned), \
                                int(float(len(records_processed)) / len(records_concerned) * 100)))
        task_sleep_now_if_required(can_stop_too=False)
        for ticket_name, plugin in tickets_to_apply.items():
            if plugin:
                if plugin['check_record'](record):
                    subject, text, queue = plugin['generate_ticket'](record)
                    recid = record_id_from_record(record)
                    ticket = BibCatalogTicket(subject=subject,
                                              text=text,
                                              queue=queue,
                                              recid=recid)
                    if ticket.submit():
                        write_message("Ticket #%s created for %i" %
                                      (ticket.ticketid, recid))
                    else:
                        write_message("Error submitting ticket for record %s" %
                                      (recid,))
                else:
                    write_message("Record NOT OK")
    return True


def load_ticket_plugins():
    """
    Will load all the ticket plugins found under CFG_BIBCATALOG_PLUGIN_DIR.

    Returns a tuple of plugin_object, list of errors.
    """
    #TODO add to configfile
    CFG_BIBCATALOG_PLUGIN_DIR = os.path.join(CFG_PYLIBDIR,
                                             "invenio",
                                             "bibcatalog_ticket_templates",
                                             "*.py")
    # Load plugins
    plugins = PluginContainer(CFG_BIBCATALOG_PLUGIN_DIR,
                              plugin_builder=_bibcatalog_plugin_builder)

    error_messages = []
    # Check for broken plug-ins
    broken = plugins.get_broken_plugins()
    if broken:
        error_messages = []
        import traceback
        for plugin, info in broken.items():
            error_messages.append("Failed to load %s:\n"
                                  " %s" % (plugin, "".join(traceback.format_exception(*info))))
    return plugins, error_messages


def load_records():
    """
    Will load the records given.
    """
    recids_given = task_get_option("recids")
    loaded_records = []
    for recid in recids_given:
        record = get_bibrecord(recid)
        if not record:
            write_message("Error: could not load record %s" % (recid,))
            continue
        loaded_records.append(record)

    query_given = task_get_option("query")
    if query_given:
        write_message("Performing a search query")

        # We are doing a search query, rg=0 allows the return of all results.
        result = perform_request_search(p=query, \
                                        cc=CFG_APSHARVEST_SEARCH_COLLECTION, \
                                        of='id', \
                                        rg=0, \
                                        wl=0)
        for recid in result:
            final_record_list.append(APSRecord(recid))

    last_id, last_date = fetch_last_updated(name="apsharvest")
    if records in ("new", "modified", "both"):
        # We fetch records from the database
        records_found = []
        if records == "new":
            records_found = get_all_new_records(since=last_date, last_id=last_id)
        elif records == "modified":
            records_found = get_all_modified_records(since=last_date, last_id=last_id)
        elif records == "both":
            records_found.extend(get_all_new_records(since=last_date, last_id=last_id))
            records_found.extend(get_all_modified_records(since=last_date, last_id=last_id))

        for recid, date in records_found:
            final_record_list.append(APSRecord(recid, date=date))



    return loaded_records


def _bibcatalog_plugin_builder(plugin_name, plugin_code):
    """
    Custom builder for pluginutils.

    @param plugin_name: the name of the plugin.
    @type plugin_name: string
    @param plugin_code: the code of the module as just read from
        filesystem.
    @type plugin_code: module
    @return: the plugin
    """
    if plugin_name == "__init__":
        return
    final_plugin = {}
    final_plugin["check_record"] = getattr(plugin_code, "check_record", None)
    final_plugin["process_ticket"] = getattr(plugin_code, "process_ticket", None)
    return final_plugin


def main():
    """Constructs the BibCatalog bibtask."""
    # Build and submit the task
    task_init(authorization_action='runbibcatalog',
              authorization_msg="BibCatalog Task Submission",
              description="",
              help_specific_usage="""

  Scheduled (daemon) options:
  -a, --new          Run on all newly inserted records.
  -m, --modified     Run on all newly modified records.
  -r, --recids       Record id for extraction.
  -c, --collections  Entire Collection for extraction.
  -t, --tickets=     All arxiv modified records within last week
  -q, --query=       Specify a search query to fetch records.

  Examples:
   (run a periodical daemon job on a given ticket template)
      bibcatalog -a -t metadata_curation -s1h
   (run on a set of records)
      bibcatalog --recids 1,2 -r 3
   (run on a collection)
      bibcatalog --collections "Articles"

""",
        version="Invenio v%s" % CFG_VERSION,
        specific_params=("hVv:r:c:t:q:am",
                            ["help",
                             "version",
                             "verbose=",
                             "recids=",
                             "collections=",
                             "tickets=",
                             "query=",
                             "new",
                             "modified"]),
        task_submit_elaborate_specific_parameter_fnc=task_parse_options,
        task_submit_check_options_fnc=task_check_options,
        task_run_fnc=task_run_core)
