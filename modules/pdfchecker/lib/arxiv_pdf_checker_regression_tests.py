import unittest
import logging
import os
from datetime import datetime
from tempfile import mkstemp

from invenio.testutils import make_test_suite, run_test_suite
from invenio.docextract_utils import setup_loggers
from invenio import bibupload
from invenio import bibtask
from invenio.dbquery import run_sql
from invenio.search_engine_utils import get_fieldvalues


EXAMPLE_PDF_URL = "http://invenio-software.org/download/" \
                                          "invenio-demo-site-files/9812226.pdf"

RECID = 20
ARXIV_ID = '1005.1481'


class TestTask(unittest.TestCase):
    def setUp(self, recid=RECID, arxiv_id=ARXIV_ID):
        self.recid = recid
        self.arxiv_id = arxiv_id
        self.bibupload_xml = """<record>
            <controlfield tag="001">%s</controlfield>
            <datafield tag="037" ind1=" " ind2=" ">
                <subfield code="a">arXiv:%s</subfield>
                <subfield code="9">arXiv</subfield>
                <subfield code="c">hep-ph</subfield>
            </datafield>
        </record>""" % (recid, arxiv_id)

        bibtask.setup_loggers()
        bibtask.task_set_task_param('verbose', 0)
        recs = bibupload.xml_marc_to_records(self.bibupload_xml)
        while get_fieldvalues(recid, '037__a'):
            err, recid, msg = bibupload.bibupload(recs[0], opt_mode='delete')
        err, recid, msg = bibupload.bibupload(recs[0], opt_mode='append')
        assert len(get_fieldvalues(recid, '037__a')) == 1

    def tearDown(self):
        """Helper function that restores recID 3 MARCXML"""
        recs = bibupload.xml_marc_to_records(self.bibupload_xml)
        err, recid, msg = bibupload.bibupload(recs[0], opt_mode='delete')

    def clean_bibtask(self):
        from invenio.arxiv_pdf_checker import NAME
        run_sql("""DELETE FROM schTASK
           WHERE user = %s
           ORDER BY id DESC LIMIT 1
        """, [NAME])

    def test_fetch_records(self):
        from invenio.arxiv_pdf_checker import fetch_updated_arxiv_records
        date = datetime(year=1900, month=1, day=1)
        records = fetch_updated_arxiv_records(date)
        self.assert_(records)

    def test_task_run_core(self):
        from invenio.arxiv_pdf_checker import task_run_core
        self.assert_(task_run_core())
        self.clean_bibtask()

    def test_shellquote(self):
        from invenio.arxiv_pdf_checker import shellquote
        self.assertEqual(shellquote("hel'lo"), "'hel'\\''lo'")
        self.assertEqual(shellquote("hel\"lo"), '\'hel"lo\'')

    def test_extract_arxiv_ids_from_recid(self):
        from invenio.arxiv_pdf_checker import extract_arxiv_ids_from_recid
        self.assertEqual(list(extract_arxiv_ids_from_recid(self.recid)), [self.arxiv_id])

    def test_build_arxiv_url(self):
        from invenio.arxiv_pdf_checker import build_arxiv_url
        self.assert_('1012.0299' in build_arxiv_url('1012.0299'))

    def test_record_has_fulltext(self):
        from invenio.arxiv_pdf_checker import record_has_fulltext
        record_has_fulltext(1)

    def test_download_external_url_invalid_content_type(self):
        from invenio.arxiv_pdf_checker import download_external_url, \
                                              InvenioFileDownloadError
        from invenio.config import CFG_SITE_URL
        temp_fd, temp_path = mkstemp()
        try:
            try:
                download_external_url(CFG_SITE_URL,
                                      temp_path,
                                      content_type='pdf')
                self.fail()
            except InvenioFileDownloadError:
                pass
        finally:
            os.unlink(temp_path)

    def test_download_external_url(self):
        from invenio.arxiv_pdf_checker import download_external_url, \
                                              InvenioFileDownloadError

        temp_fd, temp_path = mkstemp()
        try:
            try:
                download_external_url(EXAMPLE_PDF_URL,
                                      temp_path,
                                      content_type='pdf')
            except InvenioFileDownloadError, e:
                self.fail(str(e))
        finally:
            os.unlink(temp_path)

    def test_process_one(self):
        from invenio import arxiv_pdf_checker
        from invenio.arxiv_pdf_checker import process_one, \
                                              look_for_fulltext, \
                                              FoundExistingPdf, \
                                              fetch_arxiv_pdf_status, \
                                              STATUS_OK, \
                                              AlreadyHarvested
        arxiv_pdf_checker.ARXIV_URL_PATTERN = EXAMPLE_PDF_URL + "?%s"

        # Make sure there is no harvesting state stored or this test will fail
        run_sql('DELETE FROM bibARXIVPDF WHERE id_bibrec = %s', [self.recid])

        # Remove all pdfs from record 3
        for doc, docfile in look_for_fulltext(self.recid):
            doc.delete_file(docfile.get_format(), docfile.get_version())
            if not doc.list_all_files():
                doc.expunge()

        try:
            process_one(self.recid)
        finally:
            self.clean_bibtask()

        # Check for existing pdf
        docs = list(look_for_fulltext(self.recid))
        if not docs:
            self.fail()

        # Check that harvesting state is stored
        status = fetch_arxiv_pdf_status(self.recid)
        if status != STATUS_OK:
            self.fail('found status %s' % status)

        try:
            process_one(self.recid)
            self.fail()
        except AlreadyHarvested:
            run_sql('DELETE FROM bibARXIVPDF WHERE id_bibrec = %s',
                    [self.recid])

        # We know the PDF is attached, run process_one again
        # and it needs to raise an error
        try:
            process_one(self.recid)
            self.fail()
        except FoundExistingPdf:
            pass

        # Restore state
        for doc, docfile in docs:
            doc.delete_file(docfile.get_format(), docfile.get_version())
            if not doc.list_all_files():
                doc.expunge()


TEST_SUITE = make_test_suite(TestTask)

if __name__ == "__main__":
    run_test_suite(TEST_SUITE)
