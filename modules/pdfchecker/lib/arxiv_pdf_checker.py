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
ArXiv Pdf Checker Task

Checks arxiv records for missing pdfs and downloads them from arXiv
"""

import os
import time
from tempfile import mkstemp
from datetime import datetime
import urllib2
import socket

from invenio.docextract_task import store_last_updated, \
                                    fetch_last_updated
from invenio.shellutils import split_cli_ids_arg
from invenio.dbquery import run_sql
from invenio.bibtask import task_low_level_submission
from invenio.refextract_api import record_has_fulltext
from invenio.bibtask import task_init, \
                            write_message, \
                            task_update_progress, \
                            task_get_option, \
                            task_set_option, \
                            task_sleep_now_if_required
from invenio.search_engine_utils import get_fieldvalues
from invenio.config import CFG_VERSION, \
                           CFG_TMPSHAREDDIR
# Help message is the usage() print out of how to use Refextract
from invenio.refextract_cli import HELP_MESSAGE, DESCRIPTION
from invenio.bibdocfile import BibRecDocs, InvenioWebSubmitFileError


NAME = 'arxiv-pdf-checker'
ARXIV_URL_PATTERN = "http://export.arxiv.org/pdf/%s.pdf"


STATUS_OK = 'ok'
STATUS_MISSING = 'missing'


class InvenioFileDownloadError(Exception):
    """A generic download exception."""
    def __init__(self, msg, code=None):
        Exception.__init__(self, msg)
        self.code = code


class PdfNotAvailable(Exception):
    pass


class InvalidReportNumber(Exception):
    pass


class FoundExistingPdf(Exception):
    pass


class AlreadyHarvested(Exception):
    def __init__(self, status):
        Exception.__init__(self)
        self.status = status


def build_arxiv_url(arxiv_id):
    return ARXIV_URL_PATTERN % arxiv_id


def extract_arxiv_ids_from_recid(recid):
    for report_number in get_fieldvalues(recid, '037__a'):
        if not report_number.startswith('arXiv'):
            continue

        # Extract arxiv id
        try:
            yield report_number.split(':')[1]
        except IndexError:
            raise InvalidReportNumber(report_number)


def look_for_fulltext(recid):
    """Look for fulltext pdf (bibdocfile) for a given recid

    Function that was missing from refextract when arxiv-pdf-checker
    was implemented. It should be switched to using the refextract version
    when it is merged to master"""
    rec_info = BibRecDocs(recid)
    docs = rec_info.list_bibdocs()

    for doc in docs:
        for d in doc.list_all_files():
            if d.get_format().strip('.') in ['pdf', 'pdfa', 'PDF']:
                try:
                    yield doc, d
                except InvenioWebSubmitFileError:
                    pass


def shellquote(s):
    """Quote a string to use it safely as a shell argument"""
    return "'" + s.replace("'", "'\\''") + "'"


def cb_parse_option(key, value, opts, args):
    """ Must be defined for bibtask to create a task """
    if args:
        # There should be no standalone arguments for any refextract job
        # This will catch args before the job is shipped to Bibsched
        raise StandardError("Error: Unrecognised argument '%s'." % args[0])

    if key in ('-i', '--id'):
        recids = task_get_option('recids')
        if not recids:
            recids = set()
            task_set_option('recids', recids)
        recids.update(split_cli_ids_arg(value))

    return True


def store_arxiv_pdf_status(recid, status):
    """Store pdf harvesting status in the database"""
    valid_status = (STATUS_OK, STATUS_MISSING)
    if status not in valid_status:
        raise ValueError('invalid status %s' % status)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_sql("""REPLACE INTO bibARXIVPDF (id_bibrec, status, date_harvested)
            VALUES (%s, %s, %s)""", (recid, status, now))


def fetch_arxiv_pdf_status(recid):
    ret = run_sql("""SELECT status FROM bibARXIVPDF
                     WHERE id_bibrec = %s""", [recid])
    if ret:
        return ret[0][0]
    return None


### File utils temporary acquisition

#: block size when performing I/O.
CFG_FILEUTILS_BLOCK_SIZE = 1024 * 8


def open_url(url, headers=None):
    """
    Opens a URL. If headers are passed as argument, no check is performed and
    the URL will be opened. Otherwise checks if the URL is present in
    CFG_BIBUPLOAD_FFT_ALLOWED_EXTERNAL_URLS and uses the headers specified in
    the config variable.

    @param url: the URL to open
    @type url: string
    @param headers: the headers to use
    @type headers: dictionary
    @return: a file-like object as returned by urllib2.urlopen.
    """
    request = urllib2.Request(url)
    if headers:
        for key, value in headers.items():
            request.add_header(key, value)
    return urllib2.urlopen(request)


def download_external_url(url, download_to_file, content_type=None,
                          retry_count=3, timeout=2.0):
    """
    Download a url (if it corresponds to a remote file) and return a
    local url to it. If format is specified, a check will be performed
    in order to make sure that the format of the downloaded file is equal
    to the expected format.

    @param url: the URL to download
    @type url: string

    @param format: the format of the file (will be found if not specified)
    @type format: string

    @return: the path to the download local file
    @rtype: string
    @raise StandardError: if the download failed
    """
    # 1. Attempt to download the external file
    attempts = 0
    error_str = ""
    error_code = None
    while attempts < retry_count:
        try:
            request = open_url(url)
        except urllib2.HTTPError, e:
            error_code = e.code
            error_str = str(e)
            attempts += 1
            if e.code == 503:
                retry_after = int(e.headers.get("Retry-After", (timeout * timeout)))
            else:
                retry_after = timeout
            time.sleep(retry_after)
            continue
        except (urllib2.URLError, socket.timeout, socket.gaierror, socket.error), e:
            error_str = str(e)
            attempts += 1
            time.sleep(timeout)
            continue
        # When we get here, it means that the download was a success.
        try:
            finalize_download(url, download_to_file, content_type, request)
        finally:
            request.close()
        return download_to_file
    else:
        # All the attempts were used, but no successfull download - so raise error
        raise InvenioFileDownloadError('URL could not be opened: %s' % (error_str,), code=error_code)


def finalize_download(url, download_to_file, content_type, request):
    # 3. Save the downloaded file to desired or generated location.
    to_file = open(download_to_file, 'w')
    try:
        try:
            while True:
                block = request.read(CFG_FILEUTILS_BLOCK_SIZE)
                if not block:
                    break
                to_file.write(block)
        except Exception, e:
            raise InvenioFileDownloadError("Error when downloading %s into %s: %s" % \
                    (url, download_to_file, e))
    finally:
        to_file.close()

    if os.path.getsize(download_to_file) == 0:
        raise InvenioFileDownloadError("%s seems to be empty" % (url,))

    f = open(download_to_file)
    try:
        for line in f:
            if 'PDF unavailable' in line:
                raise PdfNotAvailable()
    finally:
        f.close()

    # 4. If format is given, a format check is performed.
    if content_type and content_type not in request.headers['content-type']:
        raise InvenioFileDownloadError('The downloaded file is not of the desired format')

    # download successful, return the new path
    return download_to_file


### End of file utils temporary acquisition


def download_one(recid):
    write_message('fetching %s' % recid)
    for count, arxiv_id in enumerate(extract_arxiv_ids_from_recid(recid)):
        if count != 0:
            time.sleep(60)
        url_for_pdf = build_arxiv_url(arxiv_id)
        filename_arxiv_id = arxiv_id.replace('/', '_')
        temp_fd, temp_path = mkstemp(prefix="arxiv-pdf-checker",
                                     dir=CFG_TMPSHAREDDIR,
                                     suffix="%s.pdf" % filename_arxiv_id)
        try:
            os.close(temp_fd)
            write_message('downloading pdf from %s' % url_for_pdf)
            path = download_external_url(url_for_pdf,
                                         temp_path,
                                         content_type='pdf')
            docs = BibRecDocs(recid)
            docs.add_new_file(path,
                              doctype="arXiv",
                              docname="arXiv:%s" % filename_arxiv_id)
        except:
            if os.path.isfile(temp_path):
                os.unlink(temp_path)
            raise


def process_one(recid):
    write_message('checking %s' % recid)

    harvest_status = fetch_arxiv_pdf_status(recid)
    if harvest_status:
        raise AlreadyHarvested(status=harvest_status)

    if record_has_fulltext(recid):
        raise FoundExistingPdf()

    try:
        download_one(recid)
        store_arxiv_pdf_status(recid, STATUS_OK)
        submit_refextract_task(recid)
    except PdfNotAvailable:
        store_arxiv_pdf_status(recid, STATUS_MISSING)
        raise


def submit_refextract_task(recid):
    return task_low_level_submission('refextract', NAME, '-r', str(recid))


def fetch_updated_arxiv_records(date):
    def check_arxiv(recid):
        for report_number in get_fieldvalues(recid, '037__a'):
            if report_number.startswith('arXiv'):
                return True
        return False

    # Fetch all records inserted since last run
    sql = "SELECT `id`, `modification_date` FROM `bibrec` " \
          "WHERE `modification_date` >= %s " \
          "ORDER BY `modification_date`"
    records = run_sql(sql, [date.isoformat()])
    records = [(r, mod_date) for r, mod_date in records if check_arxiv(r)]
    write_message("recids %s" % repr(records))
    task_update_progress("Done fetching arxiv record ids")
    return records


def task_run_core(name=NAME):
    start_date = datetime.now()
    dummy, last_date = fetch_last_updated(name)

    recids = task_get_option('recids')
    if recids:
        recids = [(recid, None) for recid in recids]
    else:
        recids = fetch_updated_arxiv_records(last_date)

    for count, (recid, mod_date) in enumerate(recids):
        if count % 50 == 0:
            write_message('done %s of %s' % (count, len(recids)))

        # BibTask sleep
        task_sleep_now_if_required(can_stop_too=True)
        # Internal sleep
        needs_sleep = True

        write_message('processing %s' % recid, verbose=9)
        try:
            process_one(recid)
        except AlreadyHarvested, e:
            if e.status == STATUS_OK:
                write_message('already harvested successfully')
            if e.status == STATUS_MISSING:
                write_message('already harvested and pdf is missing')
            else:
                write_message('already harvested: %s' % e.status)
            needs_sleep = False
        except FoundExistingPdf:
            write_message('found existing pdf')
            needs_sleep = False
        except PdfNotAvailable:
            write_message("no pdf available")
        except InvenioFileDownloadError, e:
            write_message("failed to download: %s" % e)

        if mod_date:
            store_last_updated(recid, start_date, name)

        if needs_sleep and count + 1 != len(recids):
            time.sleep(60)

    return True


def main():
    """Constructs the refextract bibtask."""
    # Build and submit the task
    task_init(authorization_action='runarxivpdfchecker',
        authorization_msg="Arxiv Pdf Checker Task Submission",
        description=DESCRIPTION,
        # get the global help_message variable imported from refextract.py
        help_specific_usage=HELP_MESSAGE + """
  Scheduled (daemon) options:
  -i, --id       Record id to check.

  Examples:
   (run a daemon job)
      arxiv-pdf-checker

""",
        version="Invenio v%s" % CFG_VERSION,
        specific_params=("i:", ["id="]),
        task_submit_elaborate_specific_parameter_fnc=cb_parse_option,
        task_run_fnc=task_run_core)
