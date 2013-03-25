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
BibCatalog template
"""
import datetime

from invenio.bibrecord import record_get_field_instances, \
                              field_get_subfield_values
from invenio.config import CFG_REFEXTRACT_TICKET_QUEUE, \
                           CFG_SITE_SECURE_URL
from invenio.dbquery import run_sql
from invenio.bibcatalog_utils import record_in_collection, \
                                     record_id_from_record


def check_record(record):
    """
    Expects a record object.

    Returns True if record is a HEP record.
    """
    # Is it HEP?
    if not record_in_collection(record, "HEP"):
        return
    recid = record_id_from_record(record)
    # Do not create tickets for old records
    creation_date = run_sql("""SELECT creation_date FROM bibrec
                               WHERE id = %s""", [recid])[0][0]
    if creation_date < datetime.now() - datetime.timedelta(days=365*2):
        return

    for report_tag in record_get_field_instances(record, "037"):
        for category in field_get_subfield_values(report_tag, 'c'):
            if category.startswith('astro-ph'):
                # We do not curate astro-ph
                return

    return True


def generate_ticket(record):
    """
    Expects a record object.

    Returns tuple of: (subject, body, queue) of the ticket.
    """
    recid = record_id_from_record(record)
    subject = "Refs for #%s" % recid

    # Add report number in the subjecet
    report_number = ""
    for report_tag in record_get_field_instances(record, "037"):
        for report_number in field_get_subfield_values(report_tag, 'a'):
            subject += " " + report_number
            break

    text = '%s/record/edit/#state=edit&recid=%s' % (CFG_SITE_SECURE_URL,
                                                    recid)

    return subject, text.replace('%', '%%'), CFG_REFEXTRACT_TICKET_QUEUE
