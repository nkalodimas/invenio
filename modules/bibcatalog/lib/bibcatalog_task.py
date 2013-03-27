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

from invenio.bibtask import \
    task_init, \
    task_set_option, \
    task_get_option, write_message, \
    task_update_progress, \
    task_sleep_now_if_required
from invenio.config import \
    CFG_VERSION, \
    CFG_PYLIBDIR
from invenio.docextract_task import \
    split_ids, \
    fetch_last_updated, \
    store_last_updated
from invenio.search_engine import \
    get_collection_reclist, \
    perform_request_search
from invenio.bibcatalog import bibcatalog_system
from invenio.bibcatalog_utils import record_id_from_record
from invenio.bibcatalog_dblayer import \
    get_all_new_records, \
    get_all_modified_records
from invenio.bibedit_utils import get_bibrecord
from invenio.pluginutils import PluginContainer


class BibCatalogTicket(object):
    """
    Represents a Ticket to create using BibCatalog API.
    """
    def __init__(self, subject="", text="", queue="", ticketid=None, recid=-1):
        self.subject = subject
        self.queue = queue
        self.text = text
        self.ticketid = ticketid
        self.recid = recid

    def submit(self):
        """
        Submits the ticket using BibCatalog API.

        @raise Exception: if ticket creation is not successful.
        @return bool: True if created, False if not.
        """
        if not self.exists():
            comment = False
            if "\n" in self.text:
                # The RT client does not support newlines in the initial text
                # We need to add the ticket then add a comment.
                comment = True
                res = bibcatalog_system.ticket_submit(subject=self.subject,
                                                      queue=self.queue,
                                                      recordid=self.recid)
            else:
                res = bibcatalog_system.ticket_submit(subject=self.subject,
                                                      queue=self.queue,
                                                      text=self.text,
                                                      recordid=self.recid)
            try:
                # The BibCatalog API returns int if successful or
                # a string explaining the error if unsuccessful.
                self.ticketid = int(res)
            except ValueError:
                # Not a number. Must be an error string
                raise Exception(res)
            if comment:
                bibcatalog_system.ticket_comment(ticketid=self.ticketid,
                                                 comment=self.text)
            return True
        return False

    def exists(self):
        """
        Does the ticket already exist in the RT system?

        @return bool: True if it exists, False if not.
        """
        results = bibcatalog_system.ticket_search(None,
                                                  recordid=self.recid,
                                                  queue=self.queue,
                                                  subject=self.subject)
        if results:
            return True
        return False


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
        # Tickets specified
        for ticket in task_get_option('tickets'):
            if ticket not in all_plugins.get_enabled_plugins():
                print >>sys.stderr, 'Error: plugin %s is broken or does not exist'
                return False
            ticket_plugins[ticket] = all_plugins[ticket]
    else:
        ticket_plugins = all_plugins.get_enabled_plugins()
    # Set the parameter. Dictionary of "plugin_name" -> func
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
            collections.update(get_collection_reclist(v))
    elif key in ('-i', '--recids'):
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
    # Dictionary of "plugin_name" -> func
    tickets_to_apply = task_get_option('tickets')
    write_message("Ticket plugins found: %s" %
                  (str(tickets_to_apply),), verbose=9)

    records_concerned = get_recids_to_load()
    write_message("Number of records found: %i" %
                  (len(records_concerned),), verbose=9)

    records_processed = []
    for record, last_date in load_records_from_id(records_concerned):
        recid = record_id_from_record(record)
        task_update_progress("Processing records %s/%s (%i%%)"
                             % (len(records_processed), len(records_concerned),
                                int(float(len(records_processed)) / len(records_concerned) * 100)))
        task_sleep_now_if_required(can_stop_too=False)
        for ticket_name, plugin in tickets_to_apply.items():
            if plugin:
                if plugin['check_record'](record):
                    subject, text, queue = plugin['generate_ticket'](record)
                    ticket = BibCatalogTicket(subject=subject,
                                              text=text,
                                              queue=queue,
                                              recid=int(recid))
                    try:
                        ticket.submit()
                        write_message("Ticket #%s created for %i" %
                                      (ticket.ticketid, recid))
                    except Exception:
                        write_message("Error submitting ticket for record %s. "
                                      "Perhaps it already exists." %
                                      (recid,))
                else:
                    write_message("Record NOT OK")

        if last_date:
            store_last_updated(recid, last_date, name="bibcatalog")
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


def get_recids_to_load():
    """
    Generates the final list of record IDs to load.

    Returns a list of tuples like: (recid, date)
    """
    recids_given = task_get_option("recids", default=[])
    query_given = task_get_option("query")
    if query_given:
        write_message("Performing given search query: %s" % (query_given,))
        result = perform_request_search(p=query_given,
                                        of='id',
                                        rg=0,
                                        wl=0)
        recids_given.extend(result)

    recids_given = [(recid, None) for recid in recids_given]

    last_id, last_date = fetch_last_updated(name="bibcatalog")
    records_found = []
    if task_get_option("new", default=False):
        records_found.extend(get_all_new_records(since=last_date, last_id=last_id))
    if task_get_option("modified", default=False):
        records_found.extend(get_all_modified_records(since=last_date, last_id=last_id))

    for recid, date in records_found:
        recids_given.append((recid, date))
    return recids_given


def load_records_from_id(records):
    """
    Given a record tuple of record id and last updated/created date,
    this function will yield a tuple with the record id replaced with
    a record structure iterativly.

    @param record: tuple of (recid, date-string) Ex: (1, 2012-12-12 12:12:12)
    @type record: tuple

    @yield: tuple of (record structure (dict), date-string)
    """
    for recid, date in records:
        record = get_bibrecord(int(recid))
        if not record:
            write_message("Error: could not load record %s" % (recid,))
            continue
        yield record, date


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
    final_plugin["generate_ticket"] = getattr(plugin_code, "generate_ticket", None)
    return final_plugin


def main():
    """Constructs the BibCatalog bibtask."""
    # Build and submit the task
    task_init(authorization_action='runbibcatalog',
              authorization_msg="BibCatalog Task Submission",
              description="",
              help_specific_usage="""

  Scheduled (daemon) options:

  Selection of records:

  -a, --new          Run on all newly inserted records.
  -m, --modified     Run on all newly modified records.
  -i, --recids=      Record id for extraction.
  -c, --collections= Run on all records in a specific collection.
  -q, --query=       Specify a search query to fetch records to run on.

  Selection of tickets:

  -t, --tickets=     Specify which tickets to run. Runs on all by default.

  Examples:
   (run a periodical daemon job on a given ticket template)
      bibcatalog -a -t metadata_curation -s1h
   (run on a set of records)
      bibcatalog --recids 1,2 -i 3
   (run on a collection)
      bibcatalog --collections "Articles"

    """,
              version="Invenio v%s" % CFG_VERSION,
              specific_params=("hVv:i:c:t:q:am",
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
