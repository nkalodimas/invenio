# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2012 CERN.
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

from invenio.sequtils import SequenceGenerator
from invenio.bibedit_utils import get_bibrecord
from invenio.bibrecord import record_get_field_value, create_record

import string
import random
from unidecode import unidecode

TEXKEY_MAXTRIES = 10


class TexkeyNoAuthorError(Exception):
    """ Error raised when the record does not have a main author or a
    collaboration field
    """
    pass


def _texkey_random_chars(recid, use_random=False):
    """ Generate the three random chars for the end of the texkey """
    if recid and not use_random:
        # Legacy random char generation from Spires
        texkey_third_part = chr((recid % 26) + 97) + \
                            chr(((recid / 26) % 26) + 97) + \
                            chr(((recid * 26) % 26) + 97)
    else:
        letters = string.letters.lower()
        texkey_third_part = ""
        for _ in range(3):
            texkey_third_part += random.choice(letters)

    return texkey_third_part


class TexkeySeq(SequenceGenerator):
    """
    texkey sequence generator
    """
    seq_name = 'texkey'

    def _next_value(self, recid=None, xml_record=None):
        """
        Returns the next texkey for the given recid

        @param recid: id of the record where the texkey will be generated
        @type recid: int

        @param xml_record: record in xml format
        @type xml_record: string

        @return: next texkey for the given recid.
        @rtype: string

        @raises TexkeyNoAuthorError: No main author (100__a) or collaboration
        (710__g) in the given recid
        """
        if recid is None and xml_record is not None:
            bibrecord = create_record(xml_record)[0]
        else:
            bibrecord = get_bibrecord(recid)

        main_author = record_get_field_value(bibrecord,
                                            tag="100",
                                            ind1="",
                                            ind2="",
                                            code="a")
        # Remove utf-8 special characters
        main_author = unidecode(main_author.decode('utf-8'))

        if not main_author:
            # Try with collaboration name
            main_author = record_get_field_value(bibrecord,
                                            tag="710",
                                            ind1="",
                                            ind2="",
                                            code="g")
            main_author = "".join([p for p in main_author.split()
                                if p.lower() != "collaboration"])

            if not main_author:
                raise TexkeyNoAuthorError

        try:
            texkey_first_part = main_author.split(',')[0].replace(" ", "")
        except KeyError:
            texkey_first_part = ""

        year = record_get_field_value(bibrecord,
                                        tag="269",
                                        ind1="",
                                        ind2="",
                                        code="c")
        if not year:
            year = record_get_field_value(bibrecord,
                                    tag="260",
                                    ind1="",
                                    ind2="",
                                    code="c")
            if not year:
                year = record_get_field_value(bibrecord,
                                    tag="773",
                                    ind1="",
                                    ind2="",
                                    code="y")
                if not year:
                    year = record_get_field_value(bibrecord,
                                    tag="502",
                                    ind1="",
                                    ind2="",
                                    code="d")
        try:
            texkey_second_part = year.split("-")[0]
        except KeyError:
            texkey_second_part = ""

        texkey_third_part = _texkey_random_chars(recid)

        texkey = texkey_first_part + ":" + texkey_second_part + texkey_third_part

        tries = 0
        while self._value_exists(texkey) and tries < TEXKEY_MAXTRIES:
            # Key is already in the DB, generate a new one
            texkey_third_part = _texkey_random_chars(recid, use_random=True)
            texkey = texkey_first_part + ":" + texkey_second_part + texkey_third_part
            tries += 1

        return texkey
