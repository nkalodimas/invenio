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
from invenio.bibrecord import record_get_field_instances, \
                              field_get_subfield_values
from invenio.bibcatalog_utils import record_in_collection, \
                                     record_get_value_with_provenence, \
                                     record_id_from_record


def check_record(record):
    """
    Expects a record object.

    Returns True if record is a CORE record.
    """
    return record_in_collection(record, "CORE")


def generate_ticket(record):
    """
    Expects a record object.

    Returns subject, body and queue of the ticket.
    """
    arxiv_id = _get_minimal_arxiv_id(record)
    pdfurl = "http://arxiv.org/pdf/%s" % (arxiv_id,)
    abstracturl = "http://arxiv.org/abs/%s" % (arxiv_id,)

    categories = record_get_value_with_provenence(record=record, 
                                                  provenence_code="2",
                                                  provenence_value="arXiv",
                                                  tag="650",
                                                  ind1="1",
                                                  ind2="7",
                                                  code="a")
    comments = record_get_value_with_provenence(record=record,
                                                provenence_code="9",
                                                provenence_value="arXiv",
                                                tag="500",
                                                code="a")

    authors = record_get_field_values(record, tag="100", code="a")
              + record_get_field_values(record, tag="700", code="a")
    recid = record_id_from_record(record)

    subject = "ARXIV:" + arxiv_id
    text = \
"""
%(submitdate)s

ABSTRACT: %(abstracturl)s
PDF: %(pdfurl)s

Paper: %(arxiv_id)s

Title: %(title)s

Comments: %(comments)s

Authors: %(authors)s

Categories: %(categories)s
    
%(abstract)s

Edit the record on INSPIRE: %(inspireurl)s

""" \
    % {
        'submitdate': record_get_field_value(record, tag="269", code="c"),
        'pdfurl': pdfurl,
        'abstracturl': abstracturl,
        'arxiv_id': arxiv_id,
        'title': record_get_field_value(record, tag="245", code="a"),
        'comments': "; ".join(comments),
        'categories': " ".join(categories),
        'authors': " / ".join(authors[:10]),
        'abstract': record_get_field_value(record, tag="520", code="a"),
        'inspireurl': "http://inspirehep.net/record/edit/%s" % (recid,),
    }
    return subject, text.replace('%', '%%'), "Test"


def _get_minimal_arxiv_id(record):
    """
    Returns the OAI arXiv id in the given record skipping the prefixes.
    I.e. oai:arxiv.org:1234.1234 becomes 1234.1234 and oai:arxiv.org:hep-ex/2134123
    becomes hep-ex/2134123. Used for searching.
    """
    values = record_get_field_values(record, tag="035", code="a")
    for value in values:
        if 'arXiv' in value:
            return value.split(':')[-1]
