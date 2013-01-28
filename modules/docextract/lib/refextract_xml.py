# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011 CERN.
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

import re

from xml.sax.saxutils import escape as encode_for_xml
from datetime import datetime

from invenio.refextract_re import re_num
from invenio.docextract_utils import write_message
from invenio.refextract_config import \
    CFG_REFEXTRACT_TAG_ID_REFERENCE, \
    CFG_REFEXTRACT_IND1_REFERENCE, \
    CFG_REFEXTRACT_IND2_REFERENCE, \
    CFG_REFEXTRACT_SUBFIELD_MARKER, \
    CFG_REFEXTRACT_SUBFIELD_AUTH, \
    CFG_REFEXTRACT_SUBFIELD_TITLE, \
    CFG_REFEXTRACT_SUBFIELD_MISC, \
    CFG_REFEXTRACT_SUBFIELD_REPORT_NUM, \
    CFG_REFEXTRACT_XML_RECORD_OPEN, \
    CFG_REFEXTRACT_CTRL_FIELD_RECID, \
    CFG_REFEXTRACT_TAG_ID_EXTRACTION_STATS, \
    CFG_REFEXTRACT_IND1_EXTRACTION_STATS, \
    CFG_REFEXTRACT_IND2_EXTRACTION_STATS, \
    CFG_REFEXTRACT_SUBFIELD_EXTRACTION_STATS, \
    CFG_REFEXTRACT_SUBFIELD_EXTRACTION_TIME, \
    CFG_REFEXTRACT_SUBFIELD_EXTRACTION_VERSION, \
    CFG_REFEXTRACT_VERSION, \
    CFG_REFEXTRACT_XML_RECORD_CLOSE, \
    CFG_REFEXTRACT_SUBFIELD_URL_DESCR, \
    CFG_REFEXTRACT_SUBFIELD_URL, \
    CFG_REFEXTRACT_SUBFIELD_DOI, \
    CFG_REFEXTRACT_SUBFIELD_QUOTED, \
    CFG_REFEXTRACT_SUBFIELD_ISBN, \
    CFG_REFEXTRACT_SUBFIELD_PUBLISHER, \
    CFG_REFEXTRACT_SUBFIELD_YEAR, \
    CFG_REFEXTRACT_SUBFIELD_RECID, \
    CFG_REFEXTRACT_SUBFIELD_COLLABORATION

from invenio import config
CFG_INSPIRE_SITE = getattr(config, 'CFG_INSPIRE_SITE', False)


def format_marker(line_marker):
    return line_marker.strip("[](){}. ")


def create_xml_record(counts, recid, xml_lines, status_code=0):
    """Given a series of MARC XML-ized reference lines and a record-id, write a
       MARC XML record to the stdout stream. Include in the record some stats
       for the extraction job.
       The printed MARC XML record will essentially take the following
       structure:
        <record>
           <controlfield tag="001">1</controlfield>
           <datafield tag="999" ind1="C" ind2="5">
              [...]
           </datafield>
           [...]
           <datafield tag="999" ind1="C" ind2="6">
              <subfield code="a">
        Invenio/X.XX.X refextract/X.XX.X-timestamp-err-repnum-title-URL-misc
              </subfield>
           </datafield>
        </record>
       Timestamp, error(code), reportnum, title, URL, and misc will are of
       course take the relevant values.

       @param status_code: (integer)the status of reference-extraction for the
        given record: was there an error or not? 0 = no error; 1 = error.
       @param count_reportnum: (integer) - the number of institutional
        report-number citations found in the document's reference lines.
       @param count_title: (integer) - the number of journal title citations
        found in the document's reference lines.
       @param count_url: (integer) - the number of URL citations found in the
        document's reference lines.
       @param count_misc: (integer) - the number of sections of miscellaneous
        text (i.e. 999C5$m) from the document's reference lines.
       @param count_auth_group: (integer) - the total number of author groups
        identified ($h)
       @param recid: (string) - the record-id of the given document. (put into
        001 field.)
       @param xml_lines: (list) of strings. Each string in the list contains a
        group of MARC XML 999C5 datafields, making up a single reference line.
        These reference lines will make up the document body.
       @return: The entire MARC XML textual output, plus recognition statistics.
    """
    out = []

    ## Start with the opening record tag:
    out += u"%(record-open)s\n" \
              % {'record-open': CFG_REFEXTRACT_XML_RECORD_OPEN, }

    ## Display the record-id controlfield:
    out += \
     u"""   <controlfield tag="%(cf-tag-recid)s">%(recid)d</controlfield>\n""" \
     % {'cf-tag-recid' : CFG_REFEXTRACT_CTRL_FIELD_RECID,
        'recid'        : recid,
       }

    ## Loop through all xml lines and add them to the output string:
    out.extend(xml_lines)

    ## add the 999C6 status subfields:
    out += u"""   <datafield tag="%(df-tag-ref-stats)s" ind1="%(df-ind1-ref-stats)s" ind2="%(df-ind2-ref-stats)s">
      <subfield code="%(sf-code-ref-stats)s">%(status)s-%(reportnum)s-%(title)s-%(author)s-%(url)s-%(doi)s-%(misc)s</subfield>
      <subfield code="%(sf-code-ref-time)s">%(timestamp)s</subfield>
      <subfield code="%(sf-code-ref-version)s">%(version)s</subfield>
   </datafield>\n""" \
        % {'df-tag-ref-stats'   : CFG_REFEXTRACT_TAG_ID_EXTRACTION_STATS,
           'df-ind1-ref-stats'  : CFG_REFEXTRACT_IND1_EXTRACTION_STATS,
           'df-ind2-ref-stats'  : CFG_REFEXTRACT_IND2_EXTRACTION_STATS,
           'sf-code-ref-stats'  : CFG_REFEXTRACT_SUBFIELD_EXTRACTION_STATS,
           'sf-code-ref-time'   : CFG_REFEXTRACT_SUBFIELD_EXTRACTION_TIME,
           'sf-code-ref-version': CFG_REFEXTRACT_SUBFIELD_EXTRACTION_VERSION,
           'version'            : CFG_REFEXTRACT_VERSION,
           'timestamp'          : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           'status'             : status_code,
           'reportnum'          : counts['reportnum'],
           'title'              : counts['title'],
           'author'             : counts['auth_group'],
           'url'                : counts['url'],
           'doi'                : counts['doi'],
           'misc'               : counts['misc'],
          }

    ## Now add the closing tag to the record:
    out += u"%(record-close)s\n" \
           % {'record-close' : CFG_REFEXTRACT_XML_RECORD_CLOSE, }

    ## Be sure to call this BEFORE compress_subfields
    out = filter_processed_references(''.join(out))
    ## Compress mulitple 'm' subfields in a datafield
    out = compress_subfields(out, CFG_REFEXTRACT_SUBFIELD_MISC)
    ## Compress multiple 'h' subfields in a datafield
    out = compress_subfields(out, CFG_REFEXTRACT_SUBFIELD_AUTH)
    return out


def build_xml_references(citations):
    """Build marc xml from a references list

    Transform the reference elements into marc xml
    """
    xml_references = []

    for c in citations:
        # Now, run the method which will take as input:
        # 1. A list of lists of dictionaries, where each dictionary is a piece
        # of citation information corresponding to a tag in the citation.
        # 2. The line marker for this entire citation line (mulitple citation
        # 'finds' inside a single citation will use the same marker value)
        # The resulting xml line will be a properly marked up form of the
        # citation. It will take into account authors to try and split up
        # references which should be read as two SEPARATE ones.
        xml_lines = build_xml_references_from_elements(c['elements'],
                                                       c['line_marker'])
        xml_references.extend(xml_lines)

    return xml_references


def build_xml_references_from_elements(splitted_citations, line_marker):
    return [build_xml_reference(citation_elements, line_marker) \
                                   for citation_elements in splitted_citations]


def build_xml_reference(citation_elements, line_marker, inspire_format=None):
    """ Create the MARC-XML string of the found reference information which
        was taken from a tagged reference line.
        @param citation_elements: (list) an ordered list of dictionary elements,
                                  with each element corresponding to a found
                                  piece of information from a reference line.
        @param line_marker: (string) The line marker for this single reference
                            line (e.g. [19])
        @return xml_line: (string) The MARC-XML representation of the list of
                          reference elements
    """
    if inspire_format is None:
        inspire_format = CFG_INSPIRE_SITE

    ## Begin the datafield element
    xml_line = start_datafield_element(line_marker)

    ## This will hold the ordering of tags which have been appended to the xml line
    ## This list will be used to control the desisions involving the creation of new citation lines
    ## (in the event of a new set of authors being recognised, or strange title ordering...)
    line_elements = []

    ## This is a list which will hold the current 'over-view' of a single reference line,
    ## as a list of lists, where each list corresponds to the contents of a datafield element
    ## in the xml mark-up
    citation_structure = []
    auth_for_ibid = None

    for element in citation_elements:
        ## Before going onto checking 'what' the next element is, handle misc text and semi-colons
        ## Multiple misc text subfields will be compressed later
        ## This will also be the only part of the code that deals with MISC tag_typed elements
        misc_txt = element['misc_txt']
        if misc_txt.strip("., [](){}"):
            misc_txt = misc_txt.lstrip('])} ,.').rstrip('[({ ,.')
            xml_line = append_subfield_element(xml_line,
                                               CFG_REFEXTRACT_SUBFIELD_MISC,
                                               misc_txt)

        # Now handle the type dependent actions
        # TITLE
        if element['type'] == "JOURNAL":

            # Select the journal title output format
            if inspire_format:
                # ADD to current datafield
                xml_line += """
      <subfield code="%(sf-code-ref-title)s">%(title)s,%(volume)s,%(page)s</subfield>""" \
              % {'sf-code-ref-title': CFG_REFEXTRACT_SUBFIELD_TITLE,
                 'title'            : encode_for_xml(element['title']),
                 'volume'           : encode_for_xml(element['volume']),
                 'page'             : encode_for_xml(element['page']),
                }
            else:
                # ADD to current datafield
                xml_line += """
      <subfield code="%(sf-code-ref-title)s">%(title)s %(volume)s (%(year)s) %(page)s</subfield>""" \
              % {'sf-code-ref-title': CFG_REFEXTRACT_SUBFIELD_TITLE,
                 'title'            : encode_for_xml(element['title']),
                 'volume'           : encode_for_xml(element['volume']),
                 'year'             : encode_for_xml(element['year']),
                 'page'             : encode_for_xml(element['page']),
                }

            # Now, if there are any extra (numeration based) IBID's after this title
            if len(element['extra_ibids']) > 0:
                # At least one IBID is present, these are to be outputted each into their own datafield
                for ibid in element['extra_ibids']:
                    # %%%%% Set as NEW citation line %%%%%
                    (xml_line, auth_for_ibid) = append_datafield_element(line_marker,
                                                                         citation_structure,
                                                                         line_elements,
                                                                         auth_for_ibid,
                                                                         xml_line)
                    if inspire_format:
                        xml_line += """
      <subfield code="%(sf-code-ref-title)s">%(title)s,%(volume)s,%(page)s</subfield>""" \
                          % {'sf-code-ref-title': CFG_REFEXTRACT_SUBFIELD_TITLE,
                             'title'            : encode_for_xml(ibid['title']),
                             'volume'           : encode_for_xml(ibid['volume']),
                             'page'             : encode_for_xml(ibid['page']),
                            }
                    else:
                        xml_line += """
      <subfield code="%(sf-code-ref-title)s">%(title)s %(volume)s (%(year)s) %(page)s</subfield>""" \
                          % {'sf-code-ref-title': CFG_REFEXTRACT_SUBFIELD_TITLE,
                             'title'            : encode_for_xml(ibid['title']),
                             'volume'           : encode_for_xml(ibid['volume']),
                             'year'             : encode_for_xml(ibid['year']),
                             'page'             : encode_for_xml(ibid['page']),
                            }
            # Add a Title element to the past elements list, since we last found an IBID
            line_elements.append(element)

        # REPORT NUMBER
        elif element['type'] == "REPORTNUMBER":
            # ADD to current datafield
            xml_line = append_subfield_element(xml_line,
                                               CFG_REFEXTRACT_SUBFIELD_REPORT_NUM,
                                               element['report_num'])
            line_elements.append(element)

        # URL
        elif element['type'] == "URL":
            if element['url_string'] == element['url_desc']:
                # Build the datafield for the URL segment of the reference line:
                xml_line = append_subfield_element(xml_line,
                                                   CFG_REFEXTRACT_SUBFIELD_URL,
                                                   element['url_string'])
            # Else, in the case that the url string and the description differ in some way, include them both
            else:
                # Build the datafield for the URL segment of the reference line:
                xml_line += """
      <subfield code="%(sf-code-ref-url)s">%(url)s</subfield>
      <subfield code="%(sf-code-ref-url-desc)s">%(url-desc)s</subfield>""" \
                    % {'sf-code-ref-url'     : CFG_REFEXTRACT_SUBFIELD_URL,
                       'sf-code-ref-url-desc': CFG_REFEXTRACT_SUBFIELD_URL_DESCR,
                        'url'                : encode_for_xml(element['url_string']),
                        'url-desc'           : encode_for_xml(element['url_desc'])
                      }
            line_elements.append(element)

        # DOI
        elif element['type'] == "DOI":
            ## Split on hitting another DOI in the same line
            if is_in_line_elements("DOI", line_elements):
                ## %%%%% Set as NEW citation line %%%%%
                xml_line, auth_for_ibid = append_datafield_element(line_marker,
                                                                   citation_structure,
                                                                   line_elements,
                                                                   auth_for_ibid,
                                                                   xml_line)
            xml_line = append_subfield_element(xml_line,
                                               CFG_REFEXTRACT_SUBFIELD_DOI,
                                               element['doi_string'])
            line_elements.append(element)

        # AUTHOR
        elif element['type'] == "AUTH":
            value = element['auth_txt']
            if element['auth_type'] == 'incl':
                value = "(%s)" % value

            if is_in_line_elements("AUTH", line_elements) \
                                       and line_elements[-1]['type'] != "AUTH":
                xml_line = append_subfield_element(xml_line,
                                                   CFG_REFEXTRACT_SUBFIELD_MISC,
                                                   value)
            else:
                xml_line = append_subfield_element(xml_line,
                                                   CFG_REFEXTRACT_SUBFIELD_AUTH,
                                                   value)
                line_elements.append(element)

        elif element['type'] == "QUOTED":
            xml_line = append_subfield_element(xml_line,
                                               CFG_REFEXTRACT_SUBFIELD_QUOTED,
                                               element['title'])
            line_elements.append(element)

        elif element['type'] == "ISBN":
            xml_line = append_subfield_element(xml_line,
                                               CFG_REFEXTRACT_SUBFIELD_ISBN,
                                               element['ISBN'])
            line_elements.append(element)

        elif element['type'] == "BOOK":
            xml_line = append_subfield_element(xml_line,
                                               CFG_REFEXTRACT_SUBFIELD_QUOTED,
                                               element['title'])
            line_elements.append(element)

        elif element['type'] == "PUBLISHER":
            xml_line = append_subfield_element(xml_line,
                                               CFG_REFEXTRACT_SUBFIELD_PUBLISHER,
                                               element['publisher'])
            line_elements.append(element)

        elif element['type'] == "YEAR":
            xml_line = append_subfield_element(xml_line,
                                               CFG_REFEXTRACT_SUBFIELD_YEAR,
                                               element['year'])
            line_elements.append(element)

        elif element['type'] == "COLLABORATION":
            xml_line = append_subfield_element(xml_line,
                                               CFG_REFEXTRACT_SUBFIELD_COLLABORATION,
                                               element['collaboration'])
            line_elements.append(element)

        elif element['type'] == "RECID":
            xml_line = append_subfield_element(xml_line,
                                               CFG_REFEXTRACT_SUBFIELD_RECID,
                                               str(element['recid']))

    # Append the author, if needed for an ibid, for the last element
    # in the entire line. Don't bother setting the author to be used
    # for ibids, since the line is finished
    xml_line += check_author_for_ibid(line_elements, auth_for_ibid)[0]

    # Close the ending datafield element
    xml_line += "\n   </datafield>\n"

    return xml_line


def append_subfield_element(xml_line, subfield_code, value):
    xml_element = '\n      <subfield code="' \
        '%(sf-code-ref-auth)s">%(value)s</subfield>' % {
            'value'             : encode_for_xml(value),
            'sf-code-ref-auth'  : subfield_code,
        }
    return xml_line + xml_element


def start_datafield_element(line_marker):
    """ Start a brand new datafield element with a marker subfield.
        @param line_marker: (string) The line marker which will be the sole
        content of the newly created marker subfield. This will always be the
        first subfield to be created for a new datafield element.
        @return: (string) The string holding the relevant datafield and
        subfield tags.
    """
    if not format_marker(line_marker):
        marker_subfield = ""
    else:
        marker_subfield = """
      <subfield code="%(marker-code)s">%(marker-val)s</subfield>""" \
            % {'marker-code': CFG_REFEXTRACT_SUBFIELD_MARKER,
               'marker-val' : encode_for_xml(format_marker(line_marker))}

    new_datafield = """   <datafield tag="%(df-tag-ref)s" ind1="%(df-ind1-ref)s" ind2="%(df-ind2-ref)s">%(marker-subfield)s""" \
    % {'df-tag-ref'     : CFG_REFEXTRACT_TAG_ID_REFERENCE,
       'df-ind1-ref'    : CFG_REFEXTRACT_IND1_REFERENCE,
       'df-ind2-ref'    : CFG_REFEXTRACT_IND2_REFERENCE,
       'marker-subfield': marker_subfield}

    return new_datafield


def is_in_line_elements(element_type, line_elements):
    """ Checks the list of current elements in the line for the given element type """
    for i, element in enumerate(line_elements):
        if element['type'] == element_type:
            return (True, line_elements[i])
    return False


def check_author_for_ibid(line_elements, author):
    """ Given a list of elements for an *entire* reference line, and the current
        author element to be used for ibids, check to see if that author element needs
        to be inserted into this line, depending on the presence of ibids and whether
        or not there is already an author paired with an ibid.
        Also, if no ibids are present in the line, see if the author element needs
        to be updated, depending on the presence of a normal title and a corresponding
        author group.
        @param line_elements: List of line elements for the entire processed reference
        line
        @param author: The current parent author element to be used with an ibid
        @return: (tuple) - containing a possible new author subfield, and the parent
        author element to be used for future ibids (if any)
    """
    ## Upon splitting, check for ibids in the previous line,
    ## If an appropriate author was found, pair it with this ibid.
    ## (i.e., an author has not been explicitly paired with this ibid already
    ## and an author exists with the parent title to which this ibid refers)
    if is_in_line_elements("JOURNAL", line_elements):
        ## Get the title element for this line
        title_element = is_in_line_elements("JOURNAL", line_elements)[1]

        if author != None and not is_in_line_elements("AUTH", line_elements) \
        and title_element['is_ibid']:
            ## Return the author subfield which needs to be appended for an ibid in the line
            ## No need to reset the author to be used for ibids, since this line holds an ibid
            return """
          <subfield code="%(sf-code-ref-auth)s">%(authors)s</subfield>""" \
                % {'authors'          : encode_for_xml(author['auth_txt'].strip('()')),
                   'sf-code-ref-auth' : CFG_REFEXTRACT_SUBFIELD_AUTH,
                  }, author

        ## Set the author for to be used for ibids, when a standard title is present in this line,
        ## as well as an author
        if not title_element['is_ibid'] and is_in_line_elements("AUTH", line_elements):
            ## Set the author to be used for ibids, in the event that a subsequent ibid is found
            ## this author element will be repeated.
            ## This author is only used when an ibid is in a line
            ## and there is no other author found in the line.
            author = is_in_line_elements("AUTH", line_elements)[1]
        ## If there is no author associated with this head title, clear the author to be used for ibids
        elif not title_element['is_ibid']:
            author = None

    ## If an author does not need to be replicated for an ibid, append nothing to the xml line
    return "", author


def append_datafield_element(line_marker,
                             citation_structure,
                             line_elements,
                             author,
                             xml_line):
    """ Finish the current datafield element and start a new one, with a new
        marker subfield.
        @param line_marker: (string) The line marker which will be the sole
        content of the newly created marker subfield. This will always be the
        first subfield to be created for a new datafield element.
        @return new_datafield: (string) The string holding the relevant
        datafield and subfield tags.
    """
    ## Add an author, if one must be added for ibid's, before splitting this line
    ## Also, if a standard title and an author are both present, save the author for future use
    new_datafield, author = check_author_for_ibid(line_elements, author)

    xml_line += new_datafield
    ## Start the new datafield
    xml_line += """
   </datafield>
   <datafield tag="%(df-tag-ref)s" ind1="%(df-ind1-ref)s" ind2="%(df-ind2-ref)s">
      <subfield code="%(sf-code-ref-marker)s">%(marker-val)s</subfield>""" \
    % {'df-tag-ref'         : CFG_REFEXTRACT_TAG_ID_REFERENCE,
       'df-ind1-ref'        : CFG_REFEXTRACT_IND1_REFERENCE,
       'df-ind2-ref'        : CFG_REFEXTRACT_IND2_REFERENCE,
       'sf-code-ref-marker' : CFG_REFEXTRACT_SUBFIELD_MARKER,
       'marker-val'         : encode_for_xml(format_marker(line_marker))
    }

    ## add the past elements for end previous citation to the citation_structure list
    ## (citation_structure is a reference to the initial citation_structure list found in the calling method)
    citation_structure.append(line_elements)

    ## Clear the elements in the referenced list of elements
    del line_elements[:]

    return xml_line, author


def filter_processed_references(out):
    """ apply filters to reference lines found - to remove junk"""
    reference_lines = out.split('\n')

    # Removes too long and too short m tags
    m_restricted, ref_lines = restrict_m_subfields(reference_lines)

    if m_restricted:
        a_tag = re.compile('\<subfield code=\"a\"\>(.*?)\<\/subfield\>')
        for i in range(len(ref_lines)):
            # Checks to see that the datafield has the attribute ind2="6",
            # Before looking to see if the subfield code attribute is 'a'
            if ref_lines[i].find('<datafield tag="999" ind1="C" ind2="6">') != -1 \
                and (len(ref_lines) - 1) > i:
                # For each line in this datafield element, try to find the subfield whose code attribute is 'a'
                while ref_lines[i].find('</datafield>') != -1 and (len(ref_lines) - 1) > i:
                    i += 1
                    # <subfield code="a">Invenio/X.XX.X
                    # refextract/X.XX.X-timestamp-err-repnum-title-URL-misc
                    # remake the "a" tag for new numbe of "m" tags
                    if a_tag.search(ref_lines[i]):
                        data = a_tag.search(ref_lines[i]).group(1)
                        words1 = data.split()
                        words2 = words1[-1].split('-')
                        old_m = int(words2[-1])
                        words2[-1] = str(old_m - m_restricted)
                        data1 = '-'.join(words2)
                        words1[-1] = data1
                        new_data = ' '.join(words1)
                        ref_lines[i] = '      <subfield code="a">' + new_data + '</subfield>'
                        break

    new_out = '\n'.join([l for l in [rec.rstrip() for rec in ref_lines] if l])

    if len(reference_lines) != len(new_out):
        write_message("  * filter results: unfilter references line length is %d and filtered length is %d" \
              % (len(reference_lines), len(new_out)), verbose=2)

    return new_out


def restrict_m_subfields(reference_lines):
    """Remove complete datafields which hold ONLY a single 'm' subfield,
       AND where the misc content is too short or too long to be of use.
       Min and max lengths derived by inspection of actual data. """
    min_length = 4
    max_length = 1024
    m_tag = re.compile('\<subfield code=\"m\"\>(.*?)\<\/subfield\>')
    filter_list = []
    m_restricted = 0
    for i in range(len(reference_lines)):  # set up initial filter
        filter_list.append(1)
    for i in range(len(reference_lines)):
        if m_tag.search(reference_lines[i]):
            if (i - 2) >= 0 and (i + 1) < len(reference_lines):
                if reference_lines[i + 1].find('</datafield>') != -1 and \
                    reference_lines[i - 1].find('<subfield code="o">') != -1 and \
                    reference_lines[i - 2].find('<datafield') != -1:
                    ## If both of these are true then its a solitary "m" tag
                    mlength = len(m_tag.search(reference_lines[i]).group(1))
                    if mlength < min_length or mlength > max_length:
                        filter_list[i - 2] = filter_list[i - 1] = filter_list[i] = filter_list[i + 1] = 0
                        m_restricted += 1
    new_reference_lines = []
    for i in range(len(reference_lines)):
        if filter_list[i]:
            new_reference_lines.append(reference_lines[i])
    return m_restricted, new_reference_lines


def get_subfield_content(line, subfield_code):
    """ Given a line (subfield element) and a xml code attribute for a subfield element,
        return the contents of the subfield element.
    """
    content = line.split('<subfield code="' + subfield_code + '">')[1]
    content = content.split('</subfield>')[0]
    return content


def compress_subfields(out, subfield_code):
    """
    For each datafield, compress multiple subfields of type 'subfield_code' into a single one
    e.g. for MISC text, change xml format from:
           <datafield tag="999" ind1="C" ind2="5">
              <subfield code="o">1.</subfield>
              <subfield code="m">J. Dukelsky, S. Pittel and G. Sierra</subfield>
              <subfield code="s">Rev. Mod. Phys. 76 (2004) 643</subfield>
              <subfield code="m">and this is some more misc text</subfield>
           </datafield>
           <datafield tag="999" ind1="C" ind2="5">
              <subfield code="o">2.</subfield>
              <subfield code="m">J. von Delft and D.C. Ralph,</subfield>
              <subfield code="s">Phys. Rep. 345 (2001) 61</subfield>
           </datafield>
        to:
           <datafield tag="999" ind1="C" ind2="5">
              <subfield code="o">1.</subfield>
              <subfield code="m">J. Dukelsky, S. Pittel and G. Sierra and this is some more misc text</subfield>
              <subfield code="s">Rev. Mod. Phys. 76 (2004) 643</subfield>
           </datafield>
           <datafield tag="999" ind1="C" ind2="5">
              <subfield code="o">2.</subfield>
              <subfield code="m">J. von Delft and D.C. Ralph,</subfield>
              <subfield code="s">Phys. Rep. 345 (2001) 61</subfield>
           </datafield>
           """
    in_lines = out.split('\n')
    # hold the subfield compressed version of the xml, line by line
    new_rec_lines = []
    # Used to indicate when the selected subfield has already been reached
    # inside a particular datafield
    position = 0
    # Where the concatenated misc text is held before appended at the end
    content_text = ""
    # Components of the misc subfield elements
    subfield_start = "      <subfield code=\"%s\">" % subfield_code
    subfield_end = "</subfield>"

    for line in in_lines:
        ## If reached the end of the datafield
        if line.find('</datafield>') != -1:
            if len(content_text) > 0:
                # Insert the concatenated misc contents back where it was first
                # encountered (dont RIGHTstrip semi-colons, as these may be
                # needed for &amp; or &lt;)
                if subfield_code == 'm':
                    content_text = content_text.strip(" ,.").lstrip(" ;")
                new_rec_lines[position] = new_rec_lines[position] + \
                    content_text + subfield_end
                content_text = ""
            position = 0
            new_rec_lines.append(line)
        # Found subfield in question, concatenate subfield contents
        # for this single datafield
        elif line.find(subfield_start.strip()) != -1:
            if position == 0:
                ## Save the position of this found subfield
                ## for later insertion into the same place
                new_rec_lines.append(subfield_start)
                position = len(new_rec_lines) - 1
            new_text = get_subfield_content(line, subfield_code)
            if content_text and new_text:
                ## Append spaces between merged text, if needed
                if (content_text[-1] + new_text[0]).find(" ") == -1:
                    new_text = " " + new_text
            content_text += new_text
        else:
            new_rec_lines.append(line)

    ## Create the readable file from the list of lines.
    new_out = [l.rstrip() for l in new_rec_lines]
    return '\n'.join(filter(None, new_out))
