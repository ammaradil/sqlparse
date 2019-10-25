# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andi Albrecht, albrecht.andi@gmail.com
#
# This module is part of python-bplsqlparse and is released under
# the BSD License: https://opensource.org/licenses/BSD-3-Clause

from bplsqlparse import sql, tokens as T


class StatementSplitter(object):
    """Filter that split stream at individual statements"""

    def __init__(self):
        self._reset()

    def _reset(self):
        """Set the filter attributes to its default values"""
        self._in_declare = False
        self._is_create = False
        self._in_case = 0
        self._infor = False
        self._inwhile = False
        self._begin_depth = 0

        self.consume_ws = False
        self.tokens = []
        self.level = 0

    def _change_splitlevel(self, ttype, value):
        """Get the new split level (increase, decrease or remain equal)"""
        # ANSI
        # if normal token return
        # wouldn't parenthesis increase/decrease a level?
        # no, inside a paranthesis can't start new statement
        if ttype not in T.Keyword:
            return 0

        # Everything after here is ttype = T.Keyword
        # Also to note, once entered an If statement you are done and basically
        # returning
        unified = value.upper()

        # three keywords begin with CREATE, but only one of them is DDL
        # DDL Create though can contain more words such as "or replace"
        if ttype is T.Keyword.DDL and unified == "CREATE OR REPLACE":
            self._is_create = True
            return 1

        # can have nested declare inside of being...
        if unified == 'DECLARE' and self._is_create and self._begin_depth == 0:
            self._in_declare = True
            return 1

        if unified == 'BEGIN':
            self._begin_depth += 1
            if self._is_create:
                # FIXME(andi): This makes no sense.
                return 1
            return 1

        # Should this respect a preceding BEGIN?
        # In CASE ... WHEN ... END this results in a split level -1.
        # Would having multiple CASE WHEN END and a Assignment Operator
        # cause the statement to cut off prematurely?
        if unified == 'END':
            if self._in_case > 0:
                self._in_case = self._in_case - 1
                return -1
            self._begin_depth = max(0, self._begin_depth - 1)
            return -1

        if ((unified.startswith('FOR')
             and ttype == T.ForIn) or unified == 'LOOP') and self._is_create and self._begin_depth > 0:
            if unified.startswith('FOR'):
                self._infor = True
                return 1
            if self._infor:
                self._infor = False
                return 0
            if self._inwhile:
                self._inwhile = False
                return 0
            else:
                return 1

        # Case can be outside the begin as well
        if unified == 'CASE':
            self._in_case = self._in_case + 1
            return 1

        # if (unified in ('IF', 'FOR', 'WHILE', 'LOOP') and
        # if unified in ('IF', 'WHILE', 'CASE') and self._is_create and self._begin_depth > 0:
        if unified in ('IF', 'WHILE') and self._is_create and self._begin_depth > 0:
            # if unified == 'CASE':
            #     self._in_case = True
            if unified == 'WHILE':
                self._inwhile = True
            return 1

        if unified == 'END CASE':
            self._in_case = self._in_case - 1
            return -1

        if unified in ('END IF', 'END WHILE', 'END LOOP'):
            return -1

        # Default
        return 0

    def process(self, stream):
        """Process the stream"""
        EOS_TTYPE = T.Whitespace, T.Comment.Single

        # Run over all stream tokens
        # for ttype, value in stream:
        #     # Yield token if we finished a statement and there's no whitespaces
        #     # It will count newline token as a non whitespace. In this context
        #     # whitespace ignores newlines.
        #     # why don't multi line comments also count?
        #     if self.consume_ws and ttype not in EOS_TTYPE:
        #         yield sql.Statement(self.tokens)
        #
        #         # Reset filter and prepare to process next statement
        #         self._reset()
        #
        #     # Change current split level (increase, decrease or remain equal)
        #     self.level += self._change_splitlevel(ttype, value)
        #
        #     # Append the token to the current statement
        #     self.tokens.append(sql.Token(ttype, value))
        #
        #     # Check if we get the end of a statement
        #     if self.level <= 0 and ttype is T.Punctuation and value == ';':
        #         #self.consume_ws = True
        #         self.consume_ws = False

        for ttype, value in stream:
            # start with new token
            csl = self._change_splitlevel(ttype, value)
            self.level += csl

            if csl == 1:
                self.add_new_token_array_at(self.level)
                self.append_token_at_depth(self.level, sql.Token(ttype, value))
            elif csl == -1:
                self.append_token_at_depth(self.level + 1, sql.Token(ttype, value))
                self.process_list_at_depth(self.level + 1)
            else:
                self.append_token_at_depth(self.level, sql.Token(ttype, value))
        while self.level > 0:
            self.level += -1
            self.process_list_at_depth(self.level + 1)
        # Yield pending statement (if any)
        if self.tokens:
            yield sql.Statement(self.tokens)

    # Add a new array list
    def add_new_token_array_at(self, depth):
        temp = self.tokens
        for i in range(depth):
            if i < depth - 1:
                temp = temp[len(temp) - 1]
            else:
                temp.append([])

    def append_token_at_depth(self, depth, token):
        temp = self.tokens
        for i in range(depth + 1):
            if i < depth:
                temp = temp[len(temp) - 1]
            else:
                temp.append(token)

    def process_list_at_depth(self, depth):
        temp = self.tokens
        for i in range(depth):
            if i < depth - 1:
                temp = temp[len(temp) - 1]
            else:
                temp_tokenlist = sql.Statement(temp.pop())
                temp.append(temp_tokenlist)
