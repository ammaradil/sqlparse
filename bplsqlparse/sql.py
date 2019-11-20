# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andi Albrecht, albrecht.andi@gmail.com
#
# This module is part of python-bplsqlparse and is released under
# the BSD License: https://opensource.org/licenses/BSD-3-Clause

"""This module contains classes representing syntactical elements of SQL."""
from __future__ import print_function

import re

from bplsqlparse import tokens as T
from bplsqlparse.compat import string_types, text_type, unicode_compatible
from bplsqlparse.utils import imt, remove_quotes

import inspect


@unicode_compatible
class Token(object):
    """Base class for all other classes in this module.

    It represents a single token and has two instance attributes:
    ``value`` is the unchange value of the token and ``ttype`` is
    the type of the token.
    """

    __slots__ = ('value', 'ttype', 'parent', 'normalized', 'is_keyword',
                 'is_group', 'is_whitespace')

    def __init__(self, ttype, value):
        value = text_type(value)
        self.value = value
        self.ttype = ttype
        self.parent = None
        self.is_group = False
        self.is_keyword = ttype in T.Keyword
        self.is_whitespace = self.ttype in T.Whitespace
        self.normalized = value.upper() if self.is_keyword else value

    def __str__(self):
        return self.value

    # Pending tokenlist __len__ bug fix
    # def __len__(self):
    #     return len(self.value)

    def __repr__(self):
        cls = self._get_repr_name()
        value = self._get_repr_value()

        q = u'"' if value.startswith("'") and value.endswith("'") else u"'"
        return u"<{cls} {q}{value}{q} at 0x{id:2X}>".format(
            id=id(self), **locals())

    def _get_repr_name(self):
        return str(self.ttype).split('.')[-1]

    def _get_repr_value(self):
        raw = text_type(self)
        # if len(raw) > 100:
        #     raw = raw[:99] + '...'
        return re.sub(r'\s+', ' ', raw)

    def flatten(self):
        """Resolve subgroups."""
        yield self

    def match(self, ttype, values, regex=False, ignorecase=False):
        """Checks whether the token matches the given arguments.

        *ttype* is a token type. If this token doesn't match the given token
        type.
        *values* is a list of possible values for this token. The values
        are OR'ed together so if only one of the values matches ``True``
        is returned. Except for keyword tokens the comparison is
        case-sensitive. For convenience it's ok to pass in a single string.
        If *regex* is ``True`` (default is ``False``) the given values are
        treated as regular expressions.
        """
        type_matched = self.ttype is ttype
        if not type_matched or values is None:
            return type_matched

        if isinstance(values, string_types):
            values = (values,)

        if regex:
            # TODO: Add test for regex with is_keyboard = false
            flag = re.IGNORECASE if self.is_keyword or ignorecase else 0
            values = (re.compile(v, flag) for v in values)

            for pattern in values:
                if pattern.search(self.normalized):
                    return True
            return False

        if self.is_keyword:
            values = (v.upper() for v in values)

        return self.normalized in values

    def within(self, group_cls):
        """Returns ``True`` if this token is within *group_cls*.

        Use this method for example to check if an identifier is within
        a function: ``t.within(sql.Function)``.
        """
        parent = self.parent
        while parent:
            if isinstance(parent, group_cls):
                return True
            parent = parent.parent
        return False

    def is_child_of(self, other):
        """Returns ``True`` if this token is a direct child of *other*."""
        return self.parent == other

    def has_ancestor(self, other):
        """Returns ``True`` if *other* is in this tokens ancestry."""
        parent = self.parent
        while parent:
            if parent == other:
                return True
            parent = parent.parent
        return False

    def get_ancestor(self, cls):
        parent = self.parent
        while parent:
            if isinstance(parent, cls):
                return parent
            parent = parent.parent
        return False

    def toJson(self):
        return dict(
            (key, value)
            for key, value in inspect.getmembers(self)
            if not key.startswith("__")
            and not key.startswith("parent")
            and not key.startswith("_groupable_tokens")
            and not key.startswith("M_OPEN")
            and not key.startswith("M_CLOSE")
            and not inspect.isabstract(value)
            and not inspect.isbuiltin(value)
            and not inspect.isfunction(value)
            and not inspect.isgenerator(value)
            and not inspect.isgeneratorfunction(value)
            and not inspect.ismethod(value)
            and not inspect.ismethoddescriptor(value)
            and not inspect.isroutine(value)
        )


@unicode_compatible
class TokenList(Token):
    """A group of tokens.

    It has an additional instance attribute ``tokens`` which holds a
    list of child-tokens.
    """

    __slots__ = 'tokens'

    def __init__(self, tokens=None):
        self.tokens = tokens or []
        [setattr(token, 'parent', self) for token in tokens]
        super(TokenList, self).__init__(None, text_type(self))
        self.is_group = True

    def __str__(self):
        return u''.join(token.value for token in self.flatten())

    # weird bug
    # def __len__(self):
    #     return len(self.tokens)

    def __iter__(self):
        return iter(self.tokens)

    def __getitem__(self, item):
        return self.tokens[item]

    def pop(self, index=-1):
        return self.tokens.pop(index)

    def _get_repr_name(self):
        return type(self).__name__

    def pprint_tree(self, f=None):
        self._pprint_tree(f=f)

    def _pprint_tree(self, max_depth=None, depth=0, f=None):
        """Pretty-print the object tree."""
        indent = u' | ' * depth
        for idx, token in enumerate(self.tokens):
            cls = token._get_repr_name()
            value = token._get_repr_value()

            if token.is_group and (max_depth is None or depth < max_depth):
                print(u"{indent}{idx:2d} {cls}"
                      .format(**locals()), file=f)
                token._pprint_tree(max_depth, depth + 1, f)
            else:
                q = u'"' if value.startswith("'") and value.endswith("'") else u"'"
                print(u"{indent}{idx:2d} {cls} {q}{value}{q}".format(**locals()), file=f)

    def toJson(self):
        d = {}
        for key, value in inspect.getmembers(self):
            if not key.startswith("__") \
                and not key.startswith("parent") \
                and not key.startswith("_groupable_tokens") \
                and not key.startswith("M_OPEN") \
                and not key.startswith("M_CLOSE") \
                and not inspect.isabstract(value) \
                and not inspect.isbuiltin(value) \
                and not inspect.isfunction(value) \
                and not inspect.isgenerator(value) \
                and not inspect.isgeneratorfunction(value) \
                and not inspect.ismethod(value) \
                and not inspect.ismethoddescriptor(value) \
                and not inspect.isroutine(value):
                if key == "tokens":
                    d[key] = []
                    for token in value:
                        d[key].append(token.toJson())
                else:
                    d[key] = value

        return d

    def get_token_at_offset(self, offset):
        """Returns the token that is on position offset."""
        idx = 0
        for token in self.flatten():
            end = idx + len(token.value)
            if idx <= offset < end:
                return token
            idx = end

    def flatten(self):
        """Generator yielding ungrouped tokens.

        This method is recursively called for all child tokens.
        """
        for token in self.tokens:
            if token.is_group:
                for item in token.flatten():
                    yield item
            else:
                yield token

    def get_sublists(self):
        for token in self.tokens:
            if token.is_group:
                yield token

    @property
    def _groupable_tokens(self):
        return self.tokens

    def _token_matching(self, funcs, start=0, end=None, reverse=False):
        """next token that match functions"""
        if start is None:
            return None

        if not isinstance(funcs, (list, tuple)):
            funcs = (funcs,)

        if reverse:
            assert end is None
            for idx in range(start - 2, -1, -1):
                token = self.tokens[idx]
                for func in funcs:
                    if func(token):
                        return idx, token
        else:
            for idx, token in enumerate(self.tokens[start:end], start=start):
                for func in funcs:
                    if func(token):
                        return idx, token
        return None, None

    def token_first(self, skip_ws=True, skip_cm=False):
        """Returns the first child token.

        If *skip_ws* is ``True`` (the default), whitespace
        tokens are ignored.

        if *skip_cm* is ``True`` (default: ``False``), comments are
        ignored too.
        """
        # this on is inconsistent, using Comment instead of T.Comment...
        funcs = lambda tk: not ((skip_ws and tk.is_whitespace) or
                                (skip_cm and imt(tk, t=T.Comment, i=Comment)))
        return self._token_matching(funcs)[1]

    def token_last(self, skip_ws=True, skip_cm=False):
        """Returns the first child token.

        If *skip_ws* is ``True`` (the default), whitespace
        tokens are ignored.

        if *skip_cm* is ``True`` (default: ``False``), comments are
        ignored too.
        """
        # this on is inconsistent, using Comment instead of T.Comment...
        funcs = lambda tk: not ((skip_ws and tk.is_whitespace) or
                                (skip_cm and imt(tk, t=T.Comment, i=Comment)))
        return self._token_matching(funcs, start=len(self.tokens) + 1, reverse=True)[1]

    def token_next_by(self, i=None, m=None, t=None, idx=-1, end=None):
        funcs = lambda tk: imt(tk, i, m, t)
        idx += 1
        return self._token_matching(funcs, idx, end)

    def token_not_matching(self, funcs, idx):
        funcs = (funcs,) if not isinstance(funcs, (list, tuple)) else funcs
        funcs = [lambda tk: not func(tk) for func in funcs]
        return self._token_matching(funcs, idx)

    def token_matching(self, funcs, idx):
        return self._token_matching(funcs, idx)[1]

    def token_prev(self, idx, skip_ws=True, skip_cm=False):
        """Returns the previous token relative to *idx*.

        If *skip_ws* is ``True`` (the default) whitespace tokens are ignored.
        If *skip_cm* is ``True`` comments are ignored.
        ``None`` is returned if there's no previous token.
        """
        return self.token_next(idx, skip_ws, skip_cm, _reverse=True)

    # TODO: May need to re-add default value to idx
    def token_next(self, idx, skip_ws=True, skip_cm=False, _reverse=False):
        """Returns the next token relative to *idx*.

        If *skip_ws* is ``True`` (the default) whitespace tokens are ignored.
        If *skip_cm* is ``True`` comments are ignored.
        ``None`` is returned if there's no next token.
        """
        if idx is None:
            return None, None
        idx += 1  # alot of code usage current pre-compensates for this
        funcs = lambda tk: not ((skip_ws and tk.is_whitespace) or
                                (skip_cm and imt(tk, t=T.Comment, i=Comment)))
        return self._token_matching(funcs, idx, reverse=_reverse)

    def token_index(self, token, start=0):
        """Return list index of token."""
        start = start if isinstance(start, int) else self.token_index(start)
        return start + self.tokens[start:].index(token)

    def group_tokens(self, grp_cls, start, end, include_end=True,
                     extend=False):
        """Replace tokens by an instance of *grp_cls*."""
        start_idx = start
        start = self.tokens[start_idx]

        end_idx = end + include_end

        # will be needed later for new group_clauses
        # while skip_ws and tokens and tokens[-1].is_whitespace:
        #     tokens = tokens[:-1]

        if extend and isinstance(start, grp_cls):
            subtokens = self.tokens[start_idx + 1:end_idx]

            grp = start
            grp.tokens.extend(subtokens)
            del self.tokens[start_idx + 1:end_idx]
            grp.value = text_type(start)
        else:
            subtokens = self.tokens[start_idx:end_idx]
            grp = grp_cls(subtokens)
            self.tokens[start_idx:end_idx] = [grp]
            grp.parent = self

        for token in subtokens:
            token.parent = grp

        return grp

    def insert_before(self, where, token):
        """Inserts *token* before *where*."""
        if not isinstance(where, int):
            where = self.token_index(where)
        token.parent = self
        self.tokens.insert(where, token)

    def insert_after(self, where, token, skip_ws=True):
        """Inserts *token* after *where*."""
        if not isinstance(where, int):
            where = self.token_index(where)
        nidx, next_ = self.token_next(where, skip_ws=skip_ws)
        token.parent = self
        if next_ is None:
            self.tokens.append(token)
        else:
            self.tokens.insert(nidx, token)

    def has_alias(self):
        """Returns ``True`` if an alias is present."""
        return self.get_alias() is not None

    def get_alias(self):
        """Returns the alias for this identifier or ``None``."""

        # "name AS alias"
        kw_idx, kw = self.token_next_by(m=(T.Keyword, 'AS'))
        if kw is not None:
            return self._get_first_name(kw_idx + 1, keywords=True)

        # "name alias" or "complicated column expression alias"
        _, ws = self.token_next_by(t=T.Whitespace)
        if len(self.tokens) > 2 and ws is not None:
            return self._get_first_name(reverse=True)

    def get_name(self):
        """Returns the name of this identifier.

        This is either it's alias or it's real name. The returned valued can
        be considered as the name under which the object corresponding to
        this identifier is known within the current statement.
        """
        return self.get_alias() or self.get_real_name()

    def get_real_name(self):
        """Returns the real name (object name) of this identifier."""
        # a.b
        dot_idx, _ = self.token_next_by(m=(T.Punctuation, '.'))
        return self._get_first_name(dot_idx)

    def get_parent_name(self):
        """Return name of the parent object if any.

        A parent object is identified by the first occuring dot.
        """
        dot_idx, _ = self.token_next_by(m=(T.Punctuation, '.'))
        _, prev_ = self.token_prev(dot_idx)
        return remove_quotes(prev_.value) if prev_ is not None else None

    def _get_first_name(self, idx=None, reverse=False, keywords=False):
        """Returns the name of the first token with a name"""

        tokens = self.tokens[idx:] if idx else self.tokens
        tokens = reversed(tokens) if reverse else tokens
        types = [T.Name, T.Wildcard, T.String.Symbol]

        if keywords:
            types.append(T.Keyword)

        for token in tokens:
            if token.ttype in types:
                return remove_quotes(token.value)
            elif isinstance(token, (Identifier, Function)):
                return token.get_name()


class Statement(TokenList):
    """Represents a SQL statement."""

    def get_type(self):
        """Returns the type of a statement.

        The returned value is a string holding an upper-cased reprint of
        the first DML or DDL keyword. If the first token in this group
        isn't a DML or DDL keyword "UNKNOWN" is returned.

        Whitespaces and comments at the beginning of the statement
        are ignored.
        """
        first_token = self.token_first(skip_cm=True)
        if first_token is None:
            # An "empty" statement that either has not tokens at all
            # or only whitespace tokens.
            return 'UNKNOWN'

        elif first_token.ttype in (T.Keyword.DML, T.Keyword.DDL):
            return first_token.normalized

        elif first_token.ttype == T.Keyword.CTE:
            # The WITH keyword should be followed by either an Identifier or
            # an IdentifierList containing the CTE definitions;  the actual
            # DML keyword (e.g. SELECT, INSERT) will follow next.
            fidx = self.token_index(first_token)
            tidx, token = self.token_next(fidx, skip_ws=True)
            if isinstance(token, (Identifier, IdentifierList)):
                _, dml_keyword = self.token_next(tidx, skip_ws=True)

                if dml_keyword.ttype == T.Keyword.DML:
                    return dml_keyword.normalized

        # Hmm, probably invalid syntax, so return unknown.
        return 'UNKNOWN'


class Identifier(TokenList):
    """Represents an identifier.

    Identifiers may have aliases or typecasts.
    """

    def is_wildcard(self):
        """Return ``True`` if this identifier contains a wildcard."""
        _, token = self.token_next_by(t=T.Wildcard)
        return token is not None

    def get_typecast(self):
        """Returns the typecast or ``None`` of this object as a string."""
        midx, marker = self.token_next_by(m=(T.Punctuation, '::'))
        nidx, next_ = self.token_next(midx, skip_ws=False)
        return next_.value if next_ else None

    def get_ordering(self):
        """Returns the ordering or ``None`` as uppercase string."""
        _, ordering = self.token_next_by(t=T.Keyword.Order)
        return ordering.normalized if ordering else None

    def get_array_indices(self):
        """Returns an iterator of index token lists"""

        for token in self.tokens:
            if isinstance(token, SquareBrackets):
                # Use [1:-1] index to discard the square brackets
                yield token.tokens[1:-1]


class IdentifierList(TokenList):
    """A list of :class:`~bplsqlparse.sql.Identifier`\'s."""

    def get_identifiers(self):
        """Returns the identifiers.

        Whitespaces and punctuations are not included in this generator.
        """
        for token in self.tokens:
            if not (token.is_whitespace or token.match(T.Punctuation, ',')):
                yield token


class Parenthesis(TokenList):
    """Tokens between parenthesis."""
    M_OPEN = T.Punctuation, '('
    M_CLOSE = T.Punctuation, ')'

    @property
    def _groupable_tokens(self):
        return self.tokens[1:-1]


class OpenLoopTag(TokenList):
    """Tokens between comparisons"""
    M_OPEN = T.Comparison, '<<'
    M_CLOSE = T.Comparison, '>>'


class SquareBrackets(TokenList):
    """Tokens between square brackets"""
    M_OPEN = T.Punctuation, '['
    M_CLOSE = T.Punctuation, ']'

    @property
    def _groupable_tokens(self):
        return self.tokens[1:-1]


class Assignment(TokenList):
    """An assignment like 'var := val;'"""

    @property
    def left(self):
        return self.token_first(skip_cm=True)

    @property
    def right(self):
        return self.token_last(skip_cm=True)


class If(TokenList):
    """An 'if' clause with possible 'else if' or 'else' parts."""
    M_OPEN = T.Keyword, 'IF'
    M_CLOSE = T.Keyword, 'END IF'

    def get_block(self, index):
        block_start, start_then = self.token_next_by(m=(T.Keyword, "THEN"))
        start_then += 1

        while True:
            nxtid, _nxttkn = self.token_next_by(m=(T.Keyword, "ELSIF"))
            if _nxttkn:
                if start_then <= index < nxtid:
                    return start_then, nxtid - 1
                else:
                    block_start, start_then = self.token_next_by(m=(T.Keyword, "THEN"))
                    start_then += 1
                    continue

            nxtid, _nxttkn = self.token_next_by(m=(T.Keyword, "ELSE"))
            if _nxttkn:
                if start_then <= index < nxtid:
                    return start_then, nxtid - 1
                else:
                    start_then += 1
                    continue

            nxtid, _nxttkn = self.token_next_by(m=(T.Keyword, "END IF"))
            if _nxttkn:
                if start_then <= index < nxtid:
                    return start_then, nxtid - 1
                else:
                    break

        return None, None


class Select(TokenList):
    """An 'select' clause within packages ending with ';'."""
    M_OPEN = T.Keyword.DML, 'SELECT'
    M_CLOSE = [(T.Punctuation, ';'), (T.Keyword, 'UNION'), (T.Keyword, 'UNION ALL')]

    @property
    def from_list(self):
        _from = T.Keyword, 'FROM'
        _from_index, _from_token = self.token_next_by(m=_from)
        _table_list_index, _table_list = self.token_next(_from_index, skip_ws=True, skip_cm=True)
        return _table_list

    @property
    def into_list(self):
        _into = T.Keyword, 'INTO'
        _into_index, _into_token = self.token_next_by(m=_into)
        if _into_token:
            _list_index, _list = self.token_next(_into_index, skip_ws=True, skip_cm=True)
            return _list
        return False

    @property
    def select_element_list(self):
        _select = T.Keyword.DML, 'SELECT'
        _select_index, _select_token = self.token_next_by(m=_select)
        _list_index, _list = self.token_next(_select_index, skip_ws=True, skip_cm=True)
        return _list

    @property
    def where_list(self):
        _where_index, _where_token = self.token_next_by(i=Where)
        if _where_token:
            return _where_token


class DML_Operation(TokenList):
    """An 'select' clause within packages ending with ';'."""
    M_OPEN = T.Keyword.DML, ('INSERT', 'UPDATE', 'DELETE')
    M_CLOSE = T.Punctuation, ';'


class Package(TokenList):
    """ Package """

    @property
    def fp(self):
        t = []
        # tidx, token = self.token_next_by(m=[FunctionHeading.M_OPEN, ProcedureHeading.M_OPEN])
        # fl = list(enumerate(self.flatten()))
        # for i, to in fl:
        #     if to.match(FunctionHeading.M_OPEN[0], FunctionHeading.M_OPEN[1])
        # or to.match(ProcedureHeading.M_OPEN[0], ProcedureHeading.M_OPEN[1]):
        #         # self.__fp.append(to)
        #         self.__fp.append(fl[i+2][1])
        tidx, token = self.token_next_by(i=[FunctionBlock, ProcedureBlock])
        while token:
            t.append(token)
            # t.append(self.token_next(tidx, skip_cm=True)[1])
            t_temp = self._fp(token)
            t += t_temp
            tidx, token = self.token_next_by(i=[FunctionBlock, ProcedureBlock], idx=tidx)
        return t  # return self.__fp

    def _fp(self, tk):
        t = []
        tidx, tk = tk.token_next_by(i=DeclareSection)
        if tk:
            tidx, token = tk.token_next_by(i=[FunctionBlock, ProcedureBlock])
            while token:
                t.append(token)
                t_temp = self._fp(token)
                t += t_temp
                tidx, token = tk.token_next_by(i=[FunctionBlock, ProcedureBlock], idx=tidx)
        return t

    @property
    def fpn(self):
        n = []
        for efp in self.fp:
            n.append(efp.get_my_name())
        return n

    @property
    def is_body(self):
        phidx, phtkn = self.token_next_by(i=PackageHeading)
        bidx, btkn = phtkn.token_next_by(m=(T.Keyword, 'BODY'))
        if btkn:
            return True
        return False


class PackageHeading(TokenList):
    """ Procedure Heading Class """
    M_OPEN = T.Keyword.DDL, "CREATE OR REPLACE"
    M_NEXT = T.Keyword, "PACKAGE"
    M_CLOSE = T.Keyword, ('IS', 'AS')


class FunctionHeading(TokenList):
    """Group procedure and function."""
    M_OPEN = T.Keyword, 'FUNCTION', False, True
    M_CLOSE = [(T.Keyword, ('IS', 'AS')), (T.Punctuation, ';'), (T.Punctuation, ','), ]

    def get_parameters(self):
        """Return a list of parameters."""
        fidx, func = self.token_next_by(i=Function)
        return func.get_parameters()
        # for token in func.tokens:
        #     if isinstance(token, IdentifierList):
        #         return token.get_identifiers()
        #     elif imt(token, i=(Function, Identifier), t=T.Literal):
        #         return [token, ]
        # return []


class ProcedureHeading(TokenList):
    """A function or procedure call."""
    M_OPEN = T.Keyword, 'PROCEDURE', False, True

    def get_parameters(self):
        """Return a list of parameters."""
        fidx, func = self.token_next_by(i=Function)
        return func.get_parameters()
        # parenthesis = self.tokens[-1]
        # for token in parenthesis.tokens:
        #     if isinstance(token, IdentifierList):
        #         return token.get_identifiers()
        #     elif imt(token, i=(Function, Identifier), t=T.Literal):
        #         return [token, ]
        # return []


class FunctionParam(TokenList):
    SEPARATOR = T.Punctuation, ","
    """ Group each params of function """

    def param_info(self):
        self.param_name = None
        self.in_ = None
        self.out_ = None
        self.nocopy_ = None
        self.data_type_ = None
        temp_i = 0
        for i, token in enumerate(self.flatten()):
            if not token.is_whitespace:
                if not self.param_name:
                    temp_i = i
                    self.param_name = token
                    continue
                if not self.in_ and imt(token, m=(T.Keyword, 'IN')):
                    temp_i = i
                    self.in_ = token
                    continue
                if not self.out_ and imt(token, m=(T.Keyword, 'OUT')):
                    temp_i = i
                    self.out_ = token
                    continue
                if self.out_ and token.value == 'NOCOPY':
                    temp_i = i
                    self.nocopy_ = token
                    continue
                if not self.data_type_ and imt(token, m=[(T.Keyword, 'DEFAULT')], t=T.Assignment):
                    _start = list(self.flatten())[temp_i + 2]
                    while _start.parent:
                        if _start.parent == self:
                            break
                        else:
                            _start = _start.parent

                    _end = list(self.flatten())[i - 2]
                    while _end.parent:
                        if _end.parent == self:
                            break
                        else:
                            _end = _end.parent

                    self.data_type_ = self.tokens[self.token_index(_start):self.token_index(_end) + 1]
                    # self.data_type_ = list(self.flatten())[temp_i + 2:i - 1]
                    # self.data_type_ = list(self.flatten())[i-1]
        if not self.data_type_:
            # Go to param
            _param = list(self.flatten())[temp_i + 2]
            while _param.parent:
                if _param.parent == self:
                    break
                else:
                    _param = _param.parent
            self.data_type_ = self.tokens[self.token_index(_param): len(self.tokens) + 1]
            # self.data_type_ = list(self.flatten())[temp_i + 2:i + 1]
            # self.data_type_ = list(self.flatten())[i]


class DeclareSection(TokenList):
    """ function declare section """
    M_OPEN = T.Keyword, ('IS', 'AS')
    SEPARATOR = T.Punctuation, ';'

    @property
    def declared_variables(self):
        """Return a list of variables."""
        params = []
        for token in self.tokens:
            if not (token.is_whitespace or token.match(T.Punctuation, ';')):
                params.append(token)
        return params

    def group_variables(self):
        stkn = self.token_first(skip_cm=True)
        if stkn:
            end, param = self.token_next_by(m=self.SEPARATOR)
            if param:
                while param:
                    gtkn = self.group_tokens(DataType, self.token_index(stkn), end - 1)
                    start, stkn = self.token_next(self.token_index(param), skip_cm=True)
                    if start:
                        end, param = self.token_next_by(m=self.SEPARATOR, idx=start)
                    else:
                        break


class DataType(TokenList):
    """ Param Data type"""

    def get_name(self):
        first = self.token_first(skip_cm=True)
        if isinstance(first, Assignment):
            first = first.token_first(skip_cm=True)
        if isinstance(first, Identifier):
            first = first.token_first(skip_cm=True)
        return first

    def get_type(self):
        last = self.token_last(skip_cm=True)
        if isinstance(last, Identifier):
            last = last.token_last(skip_cm=True)
        if isinstance(last, Assignment):
            last = last.token_last(skip_cm=True)
        return last


class For(TokenList):
    """A 'FOR' loop."""
    # M_OPEN = T.Keyword, ('FOR', 'FOREACH')
    M_OPEN = [(T.ForIn, r'FOR\s+\w+\s+IN\b', True), (T.Keyword, 'LOOP')]
    M_CLOSE = T.Keyword, 'END LOOP'

    @property
    def loop_idx(self):
        idx, lo = self.token_next_by(t=(T.Keyword, 'LOOP'))
        return idx

    def get_condition(self):
        return self.tokens[self.token_index(self.token_first(skip_cm=True)): self.loop_idx + 1]


class Comparison(TokenList):
    """A comparison used for example in WHERE clauses."""

    @property
    def left(self):
        return self.token_first(skip_cm=True)

    @property
    def right(self):
        return self.token_last(skip_cm=True)


class Comment(TokenList):
    """A comment."""

    def is_multiline(self):
        return self.tokens and self.tokens[0].ttype == T.Comment.Multiline


class Block(TokenList):
    """ Parent for function and procedure block"""

    def __init__(self, tokens=None):
        super(Block, self).__init__(tokens)
        self.referenced_by = []

    @property
    def references(self):
        _beginidx, _begintkn = self.token_next_by(i=Begin)
        _flist = self._get_all_functions(_begintkn.get_sublists())
        return _flist

    def _get_all_functions(self, l):
        fl = set()
        _package = self.get_ancestor(Package)
        fnp_lower = [efnp.lower() for efnp in _package.fpn]
        for su in l:
            if isinstance(su, Function):
                if isinstance(su.parent, Identifier):
                    fl.add(su.parent)
                elif su.name.lower() in fnp_lower:
                    fl.add(su)
            elif isinstance(su, Identifier) and isinstance(su.parent, (If, For, Begin)):
                fl.add(su)
            fl.update(self._get_all_functions(su.get_sublists()))
        return list(fl)


class FunctionBlock(Block):
    """ A function block """

    def get_my_name(self):
        fhid, fhtk = self.token_next_by(i=FunctionHeading)
        fid, ftk = fhtk.token_next_by(i=Function)
        if ftk:
            return ftk.name
        else:
            fid, ftk = fhtk.token_next_by(m=FunctionHeading.M_OPEN)
            if ftk:
                nid, ntkn = fhtk.token_next(idx=fid, skip_cm=True)
                return str(ntkn.value)
            return str(fhtk.parent.token_last().value)


class ProcedureBlock(Block):
    """ A procedure block """

    def get_my_name(self):
        phid, phtk = self.token_next_by(i=ProcedureHeading)
        fid, ftk = phtk.token_next_by(i=Function)
        if ftk:
            return ftk.name
        else:
            fid, ftk = phtk.token_next_by(m=ProcedureHeading.M_OPEN)
            if ftk:
                nid, ntkn = phtk.token_next(idx=fid, skip_cm=True)
                return str(ntkn.value)
            return str(phtk.parent.token_last().value)


class Where(TokenList):
    """A WHERE clause."""
    M_OPEN = T.Keyword, 'WHERE'
    M_CLOSE = T.Keyword, ('ORDER', 'GROUP', 'LIMIT', 'UNION', 'EXCEPT',
                          'HAVING', 'RETURNING', 'INTO', 'FOR UPDATE')


class Union(TokenList):
    """A WHERE clause."""
    M_DIVIDER = T.Keyword, ('UNION', 'UNION ALL')


class Case(TokenList):
    """A CASE statement with one or more WHEN and possibly an ELSE part."""
    M_OPEN = T.Keyword, 'CASE'
    M_CLOSE = T.Keyword, ('END', 'END CASE')

    def get_cases(self, skip_ws=False):
        """Returns a list of 2-tuples (condition, value).

        If an ELSE exists condition is None.
        """
        CONDITION = 1
        VALUE = 2

        ret = []
        mode = CONDITION

        for token in self.tokens:
            # Set mode from the current statement
            if token.match(T.Keyword, 'CASE'):
                continue

            elif skip_ws and token.ttype in T.Whitespace:
                continue

            elif token.match(T.Keyword, 'WHEN'):
                ret.append(([], []))
                mode = CONDITION

            elif token.match(T.Keyword, 'THEN'):
                mode = VALUE

            elif token.match(T.Keyword, 'ELSE'):
                ret.append((None, []))
                mode = VALUE

            elif token.match(T.Keyword, 'END'):
                mode = None

            # First condition without preceding WHEN
            if mode and not ret:
                ret.append(([], []))

            # Append token depending of the current mode
            if mode == CONDITION:
                ret[-1][0].append(token)

            elif mode == VALUE:
                ret[-1][1].append(token)

        # Return cases list
        return ret


class Function(TokenList):
    """A function or procedure call."""

    @property
    def name(self):
        return str(self.token_first(skip_cm=True))

    def get_parameters(self):
        """Return a list of parameters."""
        parenthesis = self.tokens[-1]
        # params = []
        # for token in parenthesis.tokens:
        #     if not (token.is_whitespace or token.match(T.Punctuation, ',')):
        #         params.append(token)
        for token in parenthesis.tokens[1:-1]:
            if isinstance(token, IdentifierList):
                return token.get_identifiers()
            elif imt(token, i=(Function, Identifier, FunctionParam), t=T.Literal):
                return [token, ]
        return []
        # return params


class Begin(TokenList):
    """A BEGIN/END block."""
    M_OPEN = T.Keyword, 'BEGIN'
    M_CLOSE = T.Keyword, 'END'


class Transaction(TokenList):
    """ A transaction block """
    M_CLOSE = T.Keyword.DML, ('COMMIT', 'ROLLBACK', 'ROLLBACK TO')

    # def __init__(self, tokens=None):
    #     super(Transaction, self).__init__(tokens)
    #     self.updated_transaction = False
    #
    # # def type_of_transaction(self, idx=0):
    # #     return self.token_next_by(m=self.M_CLOSE, idx=idx)
    #
    # def add_begin_and_end(self):
    #     w_0 = Token(T.Newline, '\n')
    #     begin = Token(T.Keyword, 'BEGIN')
    #     w_1 = Token(T.Newline, '\n')
    #
    #     self.insert_before(0, w_0)
    #     self.insert_before(1, begin)
    #     self.insert_before(2, w_1)
    #
    #     end = Token(T.Keyword, 'END')
    #     w_2 = Token(T.Newline, '\n')
    #     pun = Token(T.Punctuation, ";")
    #     w_3 = Token(T.Newline, '\n')
    #
    #     self.insert_after(self.tokens[-1], w_2)
    #     self.insert_after(self.tokens[-1], end)
    #     self.insert_after(self.tokens[-1], pun)
    #     self.insert_after(self.tokens[-1], w_3)
    #
    # def set_updated(self):
    #     self.updated_transaction = True
    #
    # @staticmethod
    # def update_text(token):
    #     for t in token.get_sublists():
    #         Transaction.update_text(t)
    #     tid, tok = Transaction.type_of_transaction(token)
    #     while tok:
    #         if tok.value == "ROLLBACK":
    #             token.pop(tid)
    #             updated_transaction = bplsqlparse.parse(cfg.replacer["ROLLBACK"])[0]
    #         elif tok.value == "COMMIT":
    #             token.pop(tid)
    #             updated_transaction = bplsqlparse.parse(cfg.replacer["COMMIT"])[0]
    #         else:
    #             print("There is a 'ROLLBACK TO' in this file")
    #             tid, tok = Transaction.type_of_transaction(token, tid)
    #             continue
    #
    #         for idx, tk in enumerate(updated_transaction.tokens):
    #             token.insert_after(tid - 1 + idx, tk)
    #
    #         tid, tok = Transaction.type_of_transaction(token, tid)
    #
    # @staticmethod
    # def type_of_transaction(token, idx=0):
    #     return token.token_next_by(m=Transaction.M_CLOSE, idx=idx)


class Operation(TokenList):
    """Grouping of operations"""

    @property
    def left(self):
        return self.token_first(skip_cm=True)

    @property
    def right(self):
        return self.token_last(skip_cm=True)

    @property
    def operator(self):
        return self.token_next_by(t=T.Operator)[1]


class ReturnType(TokenList):
    """ Grouping return and return type """
    M_OPEN = T.Keyword, 'RETURN'


class CursorDef(TokenList):
    M_OPEN = T.Keyword, 'CURSOR'
    M_MIDDLE = T.Keyword, 'IS'


class Exceptions(TokenList):
    M_OPEN = T.Keyword, 'EXCEPTION'
    M_CLOSE = T.Keyword, 'END'


class Exit(TokenList):
    """Tokens between comparisons"""
    M_OPEN = T.Keyword, 'EXIT'
    M_CLOSE = T.Punctuation, ';'

    class Condition(TokenList):
        """Grouping of Conditions inside"""

    def group_condition(self):
        _when_idx, _when_tkn = self.token_next_by(m=(T.Keyword, "WHEN"))
        if _when_tkn:
            _start = self.token_next(idx=_when_idx, skip_cm=True, skip_ws=True)[0]
            _end = self.token_index(self.token_last(skip_cm=True))
            self.group_tokens(self.Condition, start=_start, end=_end, include_end=False)

    @property
    def condition(self):
        return self.token_next_by(i=self.Condition)[1]


class Open(TokenList):
    M_OPEN = T.Keyword, 'OPEN'
    M_CLOSE = T.Punctuation, ';'


class NotFound(TokenList):
    """Tokens between comparisons"""
    M_OPEN = T.Operator, '%'
    M_CLOSE = [(T.Keyword, 'FOUND'), (T.Keyword, 'NOTFOUND'), (T.Keyword, 'ROWCOUNT')]
