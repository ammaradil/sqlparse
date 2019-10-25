# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andi Albrecht, albrecht.andi@gmail.com
#
# This module is part of python-bplsqlparse and is released under
# the BSD License: https://opensource.org/licenses/BSD-3-Clause

from bplsqlparse import sql
from bplsqlparse import tokens as T
from bplsqlparse.utils import recurse, imt

T_NUMERICAL = (T.Number, T.Number.Integer, T.Number.Float)
T_STRING = (T.String, T.String.Single, T.String.Symbol)
T_NAME = (T.Name, T.Name.Placeholder)

# These are the set of special keywords which can be used as a function name and as a keyword
SPECIAL_KEYWORDS = [(T.Keyword, 'CURSOR'), (T.Keyword.DML, 'REPLACE')]


class grouping:
    def __init__(self):
        pass

    def _group_matching(self, tlist, cls):
        """Groups Tokens that have beginning and end."""
        opens = []
        tidx_offset = 0
        for idx, token in enumerate(list(tlist)):
            tidx = idx - tidx_offset

            if token.is_whitespace:
                # ~50% of tokens will be whitespace. Will checking early
                # for them avoid 3 comparisons, but then add 1 more comparison
                # for the other ~50% of tokens...
                continue

            if token.is_group and not isinstance(token, cls):
                # Check inside previously grouped (ie. parenthesis) if group
                # of different type is inside (ie, case). though ideally  should
                # should check for all open/close tokens at once to avoid recursion
                # n = grouping()
                self._group_matching(token, cls)
                continue

            if token.match(*cls.M_OPEN):
                opens.append(tidx)

            elif token.match(*cls.M_CLOSE):
                try:
                    open_idx = opens.pop()
                except IndexError:
                    # this indicates invalid sql and unbalanced tokens.
                    # instead of break, continue in case other "valid" groups exist
                    continue
                close_idx = tidx
                tlist.group_tokens(cls, open_idx, close_idx)
                tidx_offset += close_idx - open_idx

    def group_brackets(self, tlist):
        self._group_matching(tlist, sql.SquareBrackets)

    def group_parenthesis(self, tlist):
        self._group_matching(tlist, sql.Parenthesis)

    def group_openlooptag(self, tlist):
        self._group_matching(tlist, sql.OpenLoopTag)

    def group_case(self, tlist):
        self._group_matching(tlist, sql.Case)

    def group_if(self, tlist):
        self._group_matching(tlist, sql.If)

    def group_select(self, tlist):
        opens = []
        tidx_offset = 0
        for idx, token in enumerate(list(tlist)):
            tidx = idx - tidx_offset

            if token.is_whitespace:
                # ~50% of tokens will be whitespace. Will checking early
                # for them avoid 3 comparisons, but then add 1 more comparison
                # for the other ~50% of tokens...
                continue

            if token.is_group and not isinstance(token, sql.Select):
                # Check inside previously grouped (ie. parenthesis) if group
                # of different type is inside (ie, case). though ideally  should
                # should check for all open/close tokens at once to avoid recursion
                # n = grouping()
                self.group_select(token)
                continue

            if token.match(*sql.Select.M_OPEN):
                opens.append(tidx)

            else:
                for matcher in sql.Select.M_CLOSE:
                    if token.match(*matcher):
                        try:
                            open_idx = opens.pop()
                        except IndexError:
                            # this indicates invalid sql and unbalanced tokens.
                            # instead of break, continue in case other "valid" groups exist
                            break
                        close_idx = tidx
                        if matcher[1].upper() == "UNION" or matcher[1].upper() == "UNION ALL":
                            close_idx = tlist.token_prev(idx=tidx, skip_cm=True)[0]
                        tlist.group_tokens(sql.Select, open_idx, close_idx)
                        tidx_offset += close_idx - open_idx
                        break
                continue
        if len(opens) == 1 and isinstance(tlist, sql.Parenthesis):
            tlist.group_tokens(sql.Select, opens.pop(), len(tlist.tokens) - 2)

    def group_dml(self, tlist):
        self._group_matching(tlist, sql.DML_Operation)

    def group_for(self, tlist):
        opens = []
        tidx_offset = 0
        cls = sql.For
        in_for = False
        for idx, token in enumerate(list(tlist)):
            tidx = idx - tidx_offset

            if token.is_whitespace:
                # ~50% of tokens will be whitespace. Will checking early
                # for them avoid 3 comparisons, but then add 1 more comparison
                # for the other ~50% of tokens...
                continue

            if token.is_group and not isinstance(token, cls):
                # Check inside previously grouped (ie. parenthesis) if group
                # of different type is inside (ie, case). though ideally  should
                # should check for all open/close tokens at once to avoid recursion
                # n = grouping()
                self.group_for(token)
                continue

            matched = False
            for matcher in cls.M_OPEN:
                if token.match(*matcher):
                    if token.ttype == T.ForIn:
                        matched = True
                        in_for = True
                        opens.append(tidx)
                    else:
                        if not in_for:
                            matched = True
                            opens.append(tidx)
                        else:
                            matched = True
                            in_for = False
                    break

            if not matched and token.match(*cls.M_CLOSE):
                try:
                    open_idx = opens.pop()
                except IndexError:
                    # this indicates invalid sql and unbalanced tokens.
                    # instead of break, continue in case other "valid" groups exist
                    continue
                close_idx = tidx
                tlist.group_tokens(cls, open_idx, close_idx)
                tidx_offset += close_idx - open_idx

    def group_begin(self, tlist):
        self._group_matching(tlist, sql.Begin)

    def group_exit(self, tlist):
        self._group_matching(tlist, sql.Exit)

    def group_open(self, tlist):
        self._group_matching(tlist, sql.Open)

    def group_typecasts(self, tlist):
        def match(token):
            return token.match(T.Punctuation, '::')

        def valid(token):
            return token is not None

        def post(tlist, pidx, tidx, nidx):
            return pidx, nidx

        valid_prev = valid_next = valid
        self._group(tlist, sql.Identifier, match, valid_prev, valid_next, post)

    def group_period(self, tlist):
        def match(token):
            return token.match(T.Punctuation, '.')

        def valid_prev(token):
            sqlcls = sql.SquareBrackets, sql.Identifier, sql.Function
            ttypes = T.Name, T.String.Symbol
            return imt(token, i=sqlcls, t=ttypes)

        def valid_next(token):
            # issue261, allow invalid next token
            return True

        def post(tlist, pidx, tidx, nidx):
            # next_ validation is being performed here. issue261
            sqlcls = sql.SquareBrackets, sql.Function
            ttypes = T.Name, T.String.Symbol, T.Wildcard
            next_ = tlist[nidx] if nidx is not None else None
            valid_next = imt(next_, i=sqlcls, t=ttypes)

            return (pidx, nidx) if valid_next else (pidx, tidx)

        self._group(tlist, sql.Identifier, match, valid_prev, valid_next, post)

    def group_as(self, tlist):
        def match(token):
            return token.is_keyword and token.normalized == 'AS'

        def valid_prev(token):
            return (token.normalized == 'NULL' or not token.is_keyword) \
                   and not isinstance(token, (sql.FunctionHeading, sql.ProcedureHeading)) \
                   and not isinstance(token, sql.Comment)

        def valid_next(token):
            ttypes = T.DML, T.DDL
            return not imt(token, t=ttypes) and token is not None

        def post(tlist, pidx, tidx, nidx):
            return pidx, nidx

        self._group(tlist, sql.Identifier, match, valid_prev, valid_next, post)

    def group_assignment(self, tlist):
        def match(token):
            return token.match(T.Assignment, ':=')

        def valid(token):
            return token is not None

        def post(tlist, pidx, tidx, nidx):
            m_semicolon = T.Punctuation, ';'
            snidx, _ = tlist.token_next_by(m=m_semicolon, idx=nidx)
            if snidx:
                nidx = snidx - 1
            return pidx, nidx

        valid_prev = valid_next = valid
        self._group(tlist, sql.Assignment, match, valid_prev, valid_next, post)

    def group_notfound(self, tlist, cls=sql.NotFound):
        opens = []
        tidx_offset = 0
        for idx, token in enumerate(list(tlist)):
            tidx = idx - tidx_offset

            if token.is_whitespace:
                # ~50% of tokens will be whitespace. Will checking early
                # for them avoid 3 comparisons, but then add 1 more comparison
                # for the other ~50% of tokens...
                continue

            if token.is_group and not isinstance(token, cls):
                # Check inside previously grouped (ie. parenthesis) if group
                # of different type is inside (ie, case). though ideally  should
                # should check for all open/close tokens at once to avoid recursion
                # n = grouping()
                self.group_notfound(token, cls)
                opens = None
                continue

            if token.match(*cls.M_OPEN):
                _prev_idx, _prev_tkn = tlist.token_prev(tidx, skip_cm=True)
                if _prev_tkn and (_prev_tkn.ttype == sql.T.Name
                                  or isinstance(_prev_tkn, sql.Identifier)
                                  or _prev_tkn.ttype == sql.T.Keyword):
                    opens = _prev_idx
            elif imt(token, m=cls.M_CLOSE) and opens:
                close_idx = tidx
                tlist.group_tokens(cls, opens, close_idx)
                tidx_offset += close_idx - opens
            else:
                opens = None

    def group_comparison(self, tlist):
        sqlcls = (sql.Parenthesis, sql.Function, sql.Identifier, sql.Operation, sql.NotFound)
        ttypes = T_NUMERICAL + T_STRING + T_NAME + (T.Keyword, T.Name.Builtin) + (T.Name.Negative,)

        def match(token):
            return token.ttype == T.Operator.Comparison

        def valid(token):
            if imt(token, t=ttypes, i=sqlcls):
                return True
            elif token and token.is_keyword:
                return True
            else:
                return False

        def post(tlist, pidx, tidx, nidx):
            return pidx, nidx

        valid_prev = valid_next = valid
        self._group(tlist, sql.Comparison, match,
                    valid_prev, valid_next, post, extend=False)

    @recurse(sql.Identifier)
    def group_identifier(self, tlist):
        ttypes = (T.String.Symbol, T.Name)

        tidx, token = tlist.token_next_by(t=ttypes)
        while token:
            tlist.group_tokens(sql.Identifier, tidx, tidx)
            tidx, token = tlist.token_next_by(t=ttypes, idx=tidx)

    def group_arrays(self, tlist):
        sqlcls = sql.SquareBrackets, sql.Identifier, sql.Function
        ttypes = T.Name, T.String.Symbol

        def match(token):
            return isinstance(token, sql.SquareBrackets)

        def valid_prev(token):
            return imt(token, i=sqlcls, t=ttypes)

        def valid_next(token):
            return True

        def post(tlist, pidx, tidx, nidx):
            return pidx, tidx

        self._group(tlist, sql.Identifier, match,
                    valid_prev, valid_next, post, extend=True, recurse=False)

    def group_operator(self, tlist):
        ttypes = T_NUMERICAL + T_STRING + T_NAME
        sqlcls = (sql.SquareBrackets, sql.Parenthesis, sql.Function,
                  sql.Identifier, sql.Operation)

        def match(token):
            return imt(token, t=(T.Operator, T.Wildcard))

        def valid(token):
            return imt(token, i=sqlcls, t=ttypes)

        def post(tlist, pidx, tidx, nidx):
            tlist[tidx].ttype = T.Operator
            return pidx, nidx

        valid_prev = valid_next = valid
        self._group(tlist, sql.Operation, match,
                    valid_prev, valid_next, post, extend=False)

    def group_identifier_list(self, tlist):
        m_role = T.Keyword, ('null', 'role')
        sqlcls = (sql.Function, sql.Case, sql.Identifier, sql.Comparison,
                  sql.IdentifierList, sql.Operation, sql.FunctionParam)
        ttypes = (T_NUMERICAL + T_STRING + T_NAME + (T.Keyword, T.Comment, T.Wildcard))

        def match(token):
            return token.match(T.Punctuation, ',')

        def valid(token):
            return imt(token, i=sqlcls, m=m_role, t=ttypes)

        def post(tlist, pidx, tidx, nidx):
            return pidx, nidx

        valid_prev = valid_next = valid
        self._group(tlist, sql.IdentifierList, match,
                    valid_prev, valid_next, post, extend=True, skip_cm=True)

    @recurse(sql.Comment)
    def group_comments(self, tlist):
        tidx, token = tlist.token_next_by(t=T.Comment)
        while token:
            eidx, end = tlist.token_not_matching(
                lambda tk: imt(tk, t=T.Comment) or tk.is_whitespace, idx=tidx)
            if end is not None:
                eidx, end = tlist.token_prev(eidx, skip_ws=False)
                tlist.group_tokens(sql.Comment, tidx, eidx)

            tidx, token = tlist.token_next_by(t=T.Comment, idx=tidx)

    @recurse(sql.FunctionBlock)
    def group_function_block(self, tlist):
        start, token = tlist.token_next_by(i=sql.FunctionHeading)

        while token:
            _nidx, _next = tlist.token_next(idx=start, skip_cm=True, skip_ws=True)
            # if _next.value.upper() == 'RETURN':
            #     _rtypeidx, _rtype = tlist.token_next(idx=_nidx, skip_cm=True, skip_ws=True)
            #     _nid, _ntk = tlist.token_next(idx=_rtypeidx, skip_cm=True, skip_ws=True)
            if _next and (_next.value.upper() == 'IS' or _next.value.upper() == 'AS'):
                while self._internal_fun_proc_grouping(tlist, _nidx):
                    continue
                bid, btoken = tlist.token_next_by(i=sql.Begin, idx=_nidx)
                if btoken:
                    end, etoken = tlist.token_next(idx=bid, skip_cm=True, skip_ws=True)
                    if etoken:
                        # if token.value == ';':
                        #     tlist.group_tokens(sql.FunctionBlock, start, end)
                        # elif token.ttype == T.Name:
                        #     end, token = tlist.token_next(idx=end, skip_cm=True, skip_ws=True)
                        #     if token.value == ';':
                        #         tlist.group_tokens(sql.FunctionBlock, start, end)
                        # else:
                        #     tlist.group_tokens(sql.FunctionBlock, start, end)
                        tlist.group_tokens(sql.FunctionBlock, start, end)
                    else:
                        tlist.group_tokens(sql.FunctionBlock, start, bid)

            start, token = tlist.token_next_by(i=sql.FunctionHeading, idx=start)

    def _internal_fun_proc_grouping(self, tlist, _nidx):
        bid, btoken = tlist.token_next_by(i=sql.Begin, idx=_nidx)
        if btoken:
            ph_temp_id, ph_temp_tk = tlist.token_next_by(i=sql.ProcedureHeading, idx=_nidx)
            fh_temp_id, fh_temp_tk = tlist.token_next_by(i=sql.FunctionHeading, idx=_nidx)
            if ph_temp_tk and fh_temp_tk and ph_temp_id < bid and fh_temp_id < bid:
                diff_ph = ph_temp_id - _nidx
                diff_fh = fh_temp_id - _nidx

                if diff_ph < diff_fh:
                    _nidx, _next = tlist.token_next(idx=ph_temp_id, skip_cm=True, skip_ws=True)
                    if _next.value.upper() == 'IS' or _next.value.upper() == 'AS':
                        self._internal_fun_proc_grouping(tlist, _nidx)
                        bid, token = tlist.token_next_by(i=sql.Begin, idx=_nidx)
                        if token:
                            end, token = tlist.token_next(idx=bid, skip_cm=True, skip_ws=True)
                            tlist.group_tokens(sql.ProcedureBlock, ph_temp_id, end)
                            return True
                elif diff_ph > diff_fh:
                    _nidx, _next = tlist.token_next(idx=fh_temp_id, skip_cm=True, skip_ws=True)
                    if _next.value.upper() == 'IS' or _next.value.upper() == 'AS':
                        self._internal_fun_proc_grouping(tlist, _nidx)
                        bid, token = tlist.token_next_by(i=sql.Begin, idx=_nidx)
                        if token:
                            end, token = tlist.token_next(idx=bid, skip_cm=True, skip_ws=True)
                            tlist.group_tokens(sql.FunctionBlock, fh_temp_id, end)
                            return True

            elif ph_temp_tk and ph_temp_id < bid:
                _nidx, _next = tlist.token_next(idx=ph_temp_id, skip_cm=True, skip_ws=True)
                if _next.value.upper() == 'IS' or _next.value.upper() == 'AS':
                    self._internal_fun_proc_grouping(tlist, _nidx)
                    bid, token = tlist.token_next_by(i=sql.Begin, idx=_nidx)
                    if token:
                        end, token = tlist.token_next(idx=bid, skip_cm=True, skip_ws=True)
                        tlist.group_tokens(sql.ProcedureBlock, ph_temp_id, end)
                        return True

            elif fh_temp_tk and fh_temp_id < bid:
                _nidx, _next = tlist.token_next(idx=fh_temp_id, skip_cm=True, skip_ws=True)
                if _next.value.upper() == 'IS' or _next.value.upper() == 'AS':
                    self._internal_fun_proc_grouping(tlist, _nidx)
                    bid, token = tlist.token_next_by(i=sql.Begin, idx=_nidx)
                    if token:
                        end, token = tlist.token_next(idx=bid, skip_cm=True, skip_ws=True)
                        tlist.group_tokens(sql.FunctionBlock, fh_temp_id, end)
                        return True
        return False

    @recurse(sql.ProcedureBlock)
    def group_procedure_block(self, tlist):
        start, token = tlist.token_next_by(i=sql.ProcedureHeading)

        while token:
            _nidx, _next = tlist.token_next(idx=start, skip_cm=True, skip_ws=True)
            if _next and (_next.value.upper() == 'IS' or _next.value.upper() == 'AS'):
                while self._internal_fun_proc_grouping(tlist, _nidx):
                    continue
                bid, btoken = tlist.token_next_by(i=sql.Begin, idx=_nidx)
                if btoken:
                    end, etoken = tlist.token_next(idx=bid, skip_cm=True, skip_ws=True)
                    if etoken:
                        send, stoken = tlist.token_next(idx=end, skip_cm=True, skip_ws=True)
                        if stoken and stoken.value == ';':
                            tlist.group_tokens(sql.ProcedureBlock, start, send)
                        else:
                            tlist.group_tokens(sql.ProcedureBlock, start, end)
                        # tlist.group_tokens(sql.ProcedureBlock, start, end)
                    else:
                        tlist.group_tokens(sql.ProcedureBlock, start, bid)
                        # tlist.group_tokens(sql.ProcedureBlock, start, end)

            start, token = tlist.token_next_by(i=sql.ProcedureHeading, idx=start)

    @recurse(sql.FunctionParam)
    def group_function_params(self, tlist):
        funidx, functkn = tlist.token_next_by(i=sql.Function)

        while functkn:
            prnidx, prntkn = functkn.token_next_by(i=sql.Parenthesis)
            if prntkn:
                oidx, otkn = prntkn.token_next_by(m=sql.Parenthesis.M_OPEN)
                start, stkn = prntkn.token_next(oidx, skip_cm=True)
                end, param = prntkn.token_next_by(m=sql.FunctionParam.SEPARATOR)
                if param:
                    while param:
                        prntkn.group_tokens(sql.FunctionParam, start, prntkn.token_prev(end, skip_cm=True)[0])
                        start = prntkn.token_next(prntkn.token_index(param), skip_cm=True)[0]
                        end, param = prntkn.token_next_by(m=sql.FunctionParam.SEPARATOR, idx=start)
                    cidx, ctkn = prntkn.token_next_by(m=sql.Parenthesis.M_CLOSE)
                    end, etkn = prntkn.token_prev(cidx, skip_cm=True)
                    prntkn.group_tokens(sql.FunctionParam, start, end)
                else:
                    cidx, ctkn = prntkn.token_next_by(m=sql.Parenthesis.M_CLOSE)
                    end, etkn = prntkn.token_prev(cidx, skip_cm=True)
                    prntkn.group_tokens(sql.FunctionParam, start, end)

            funidx, functkn = tlist.token_next_by(i=sql.Function, idx=funidx)
            # funidx, functkn = tlist.token_next_by(i=sql.Function)
            #
            # while functkn:
            #     prnidx, prntkn = functkn.token_next_by(i=sql.Parenthesis)
            #     if prntkn:
            #         start = 1
            #         end, param = prntkn.token_next_by(m=sql.FunctionParam.SEPARATOR)
            #         if param:
            #             while param:
            #                 start = prntkn.token_index(prntkn.group_tokens(sql.FunctionParam, start, end - 1)) + 2
            #                 end, param = prntkn.token_next_by(m=sql.FunctionParam.SEPARATOR, idx=start)
            #             prntkn.group_tokens(sql.FunctionParam, start, len(prntkn.tokens) - 2)
            #         else:
            #             prntkn.group_tokens(sql.FunctionParam, start, len(prntkn.tokens) - 2)
            #
            #     funidx, functkn = tlist.token_next_by(i=sql.Function, idx=funidx)

    @recurse(sql.DeclareSection)
    def group_declare_section(self, tlist):
        funidx, functkn = tlist.token_next_by(i=[sql.FunctionBlock, sql.ProcedureBlock])

        while functkn:
            sidx, stkn = functkn.token_next_by(m=sql.DeclareSection.M_OPEN)
            if stkn:
                bid, btkn = functkn.token_next_by(i=sql.Begin)
                if sidx + 2 <= bid - 2:
                    nid, next_ = functkn.token_next(idx=sidx, skip_cm=True)
                    if not next_ == btkn:
                        functkn.group_tokens(sql.DeclareSection, nid, bid - 2)

            funidx, functkn = tlist.token_next_by(i=[sql.FunctionBlock, sql.ProcedureBlock], idx=funidx)

    @recurse(sql.Where)
    def group_where(self, tlist):
        tidx, token = tlist.token_next_by(m=sql.Where.M_OPEN)
        while token:
            eidx, end = tlist.token_next_by(m=sql.Where.M_CLOSE, idx=tidx)

            if end is None:
                end = tlist._groupable_tokens[-1]
            else:
                end = tlist.tokens[eidx - 1]
            # TODO: convert this to eidx instead of end token.
            # i think above values are len(tlist) and eidx-1
            eidx = tlist.token_index(end)
            tlist.group_tokens(sql.Where, tidx, eidx)
            tidx, token = tlist.token_next_by(m=sql.Where.M_OPEN, idx=tidx)

    @recurse(sql.Union)
    def group_union(self, tlist):
        tidx, token = tlist.token_next_by(m=sql.Union.M_DIVIDER)
        while token:
            pid, ptk = tlist.token_prev(idx=tidx, skip_cm=True)
            nid, ntk = tlist.token_next(idx=tidx, skip_cm=True)
            extend = False
            if isinstance(ptk, sql.Union):
                extend = True
            tidx, token = tlist.token_next_by(m=sql.Union.M_DIVIDER, idx=tlist.token_index(
                tlist.group_tokens(sql.Union, pid, nid, extend=extend)))

    @recurse()
    def group_aliased(self, tlist):
        I_ALIAS = (sql.Parenthesis, sql.Function, sql.Case, sql.Identifier,
                   sql.Operation, sql.Comparison)

        tidx, token = tlist.token_next_by(i=I_ALIAS, t=T.Number)
        while token:
            nidx, next_ = tlist.token_next(tidx)
            if isinstance(next_, sql.Identifier):
                tlist.group_tokens(sql.Identifier, tidx, nidx, extend=True)
            tidx, token = tlist.token_next_by(i=I_ALIAS, t=T.Number, idx=tidx)

    @recurse(sql.Function)
    def group_functions(self, tlist):
        # has_create = False
        # has_table = False
        # for tmp_token in tlist.tokens:
        #     if tmp_token.value == 'CREATE':
        #         has_create = True
        #     if tmp_token.value == 'TABLE':
        #         has_table = True
        # if has_create and has_table:
        #     return

        tidx, token = tlist.token_next_by(t=T.Name, m=SPECIAL_KEYWORDS)
        while token:
            nidx, next_ = tlist.token_next(tidx, skip_cm=True)
            if isinstance(next_, sql.Parenthesis):
                tlist.group_tokens(sql.Function, tidx, nidx)
            tidx, token = tlist.token_next_by(t=T.Name, m=SPECIAL_KEYWORDS, idx=tidx)

    @recurse(sql.ProcedureHeading)
    def group_procedure_heading(self, tlist):
        proid, token = tlist.token_next_by(m=sql.ProcedureHeading.M_OPEN)
        while token:
            tidx, token = tlist.token_next(proid, skip_ws=True, skip_cm=True)
            if token.ttype == T.Name:
                nidx, next_ = tlist.token_next(tidx)
                if isinstance(next_, sql.Parenthesis):
                    tlist.group_tokens(sql.ProcedureHeading, proid, nidx)
                elif next_.value.upper() == "IS" or next_.value.upper() == "AS":
                    tlist.group_tokens(sql.ProcedureHeading, proid, tidx)
            proid, token = tlist.token_next_by(m=sql.ProcedureHeading.M_OPEN, idx=proid)

    @recurse(sql.FunctionHeading)
    def group_function_heading(self, tlist):
        # self._group_matching(tlist, sql.FunctionHeading)
        proid, token = tlist.token_next_by(m=sql.FunctionHeading.M_OPEN)
        while token:
            tidx, nto = tlist.token_next(proid, skip_ws=True, skip_cm=True)
            if nto and nto.ttype == T.Name:
                nidx, next_ = tlist.token_next(tidx)
                if isinstance(next_, sql.Parenthesis):
                    # tlist.group_tokens(sql.FunctionHeading, proid, nidx)
                    nidx, next_ = tlist.token_next(idx=nidx, skip_cm=True)
                cnidx, cnext_ = tlist.token_next_by(m=sql.FunctionHeading.M_CLOSE, idx=nidx)
                if cnext_:
                    tlist.group_tokens(sql.FunctionHeading, proid, cnidx - 1)
                elif isinstance(next_.parent, sql.Parenthesis):
                    tlist.group_tokens(sql.FunctionHeading, proid, len(next_.parent.tokens) - 2)
            proid, token = tlist.token_next_by(m=sql.FunctionHeading.M_OPEN, idx=proid)

    @recurse(sql.ReturnType)
    def group_function_return_type(self, tlist):
        fhid, fhtk = tlist.token_next_by(i=sql.FunctionHeading)
        while fhtk:
            rid, rtk = fhtk.token_next_by(m=sql.ReturnType.M_OPEN)
            if rtk:
                tid, ttk = fhtk.token_next(idx=rid)
                fhtk.group_tokens(sql.ReturnType, rid, tid)
            fhid, fhtk = tlist.token_next_by(i=sql.FunctionHeading, idx=fhid)

    @recurse(sql.Statement)
    def flatter_statement_class(self, tlist):
        stmid, stmt = tlist.token_next_by(i=sql.Statement)

        while stmt:
            self._flatter_statement_class(stmt, stmid)
            stmid, stmt = tlist.token_next_by(i=sql.Statement, idx=stmid)

    def _flatter_statement_class(self, stmt, stmid):
        if isinstance(stmt, sql.Statement) and len(stmt.tokens) == 1:
            stmt.parent.pop(stmid)
            stmt.parent.insert_before(stmid, stmt.tokens[0])
            self._flatter_statement_class(stmt.tokens[0], stmid)
        elif stmt.is_group:
            for sid, stkn in enumerate(stmt.tokens):
                if isinstance(stkn, sql.Statement):
                    self._flatter_statement_class(stkn, sid)
                elif stkn.is_group:
                    self._flatter_statement_class(stkn, sid)

    @recurse(sql.Identifier)
    def flatter_identifier_class(self, tlist):
        stmid, stmt = tlist.token_next_by(i=sql.Identifier)

        while stmt:
            self._flatter_identifier_class(stmt, stmid)
            stmid, stmt = tlist.token_next_by(i=sql.Identifier, idx=stmid)

    def _flatter_identifier_class(self, stmt, stmid):
        if isinstance(stmt, sql.Identifier) and len(stmt.tokens) == 1:
            stmt.parent.pop(stmid)
            stmt.parent.insert_before(stmid, stmt.tokens[0])
            self._flatter_identifier_class(stmt.tokens[0], stmid)
        elif stmt.is_group:
            for sid, stkn in enumerate(stmt.tokens):
                if isinstance(stkn, sql.Identifier):
                    self._flatter_identifier_class(stkn, sid)
                elif stkn.is_group:
                    self._flatter_identifier_class(stkn, sid)

    @recurse(sql.Transaction)
    def group_transaction(self, tlist):
        bindx, token = tlist.token_next_by(i=sql.Begin)
        while token:
            self._group_transaction(token)
            bindx, token = tlist.token_next_by(i=sql.Begin, idx=bindx)

    def _group_transaction(self, btkn):
        tidx_offset = 0
        pidx, prev_, is_commit = None, None, False
        start_idx = 0
        if isinstance(btkn, sql.Begin):
            start_idx = 1
        elif isinstance(btkn, sql.For):
            start_idx = btkn.loop_idx + 1

        for idx, token in enumerate(list(btkn)):
            tidx = idx - tidx_offset

            if token.is_whitespace:
                continue

            if token.is_group and not isinstance(token, sql.Transaction):
                if self._group_transaction(token):
                    if isinstance(token, sql.If):
                        grp = btkn.group_tokens(sql.Transaction, tidx, tidx + 1)
                    if not isinstance(btkn, sql.If):
                        grp = btkn.group_tokens(sql.Transaction, start_idx, tidx - 1)
                        start_idx = btkn.token_index(grp)
                        start_idx += 3
                        tidx_offset += tidx - start_idx
                        tidx_offset += 2
                        if isinstance(token, sql.If):
                            start_idx = start_idx - 1
                            tidx_offset = tidx_offset + 1
                    is_commit = True
                continue

            if imt(token, m=sql.Transaction.M_CLOSE):
                to_idx, next_ = btkn.token_next(tidx)
                if next_.value == ';':
                    if not isinstance(btkn, sql.If):
                        grp = btkn.group_tokens(sql.Transaction, start_idx, to_idx)
                        start_idx = btkn.token_index(grp)
                        start_idx += 1
                        tidx_offset += to_idx - start_idx
                        tidx_offset += 1
                    is_commit = True
                continue

        return is_commit

    def group_order(self, tlist):
        """Group together Identifier and Asc/Desc token"""
        tidx, token = tlist.token_next_by(t=T.Keyword.Order)
        while token:
            pidx, prev_ = tlist.token_prev(tidx)
            if imt(prev_, i=sql.Identifier, t=T.Number):
                tlist.group_tokens(sql.Identifier, pidx, tidx)
                tidx = pidx
            tidx, token = tlist.token_next_by(t=T.Keyword.Order, idx=tidx)

    @recurse()
    def align_comments(self, tlist):
        tidx, token = tlist.token_next_by(i=sql.Comment)
        while token:
            pidx, prev_ = tlist.token_prev(tidx)
            if isinstance(prev_, sql.TokenList):
                tlist.group_tokens(sql.TokenList, pidx, tidx, extend=True)
                tidx = pidx
            tidx, token = tlist.token_next_by(i=sql.Comment, idx=tidx)

    @recurse(sql.Package)
    def group_package(self, tlist):
        # pidx, ptoken = tlist.token_next_by(m=sql.PackageHeading.M_OPEN)
        # while ptoken:
        #     tidx, token = tlist.token_next_by(m=sql.PackageHeading.M_NEXT)
        #     if token:
        #         last = tlist.parent.token_last(skip_cm=True)
        #         tlist.parent.group_tokens(sql.Statement, 0, tlist.parent.token_index(last), extend=True)
        #         aidx, token = tlist.token_next_by(m=sql.PackageHeading.M_CLOSE)
        #         tlist.group_tokens(sql.PackageHeading, tidx, aidx)
        #         tlist.group_tokens(sql.Package, pidx, len(tlist.tokens))  # .get_fp()
        #         # print tlist
        #     pidx, ptoken = tlist.token_next_by(m=sql.PackageHeading.M_OPEN, idx=pidx)

        tidx_offset = 0
        for idx, token in enumerate(list(tlist)):
            tidx = idx - tidx_offset

            if token.is_whitespace:
                continue

            if token.is_group and not isinstance(token, sql.Package):
                self.group_package(token)

            if not isinstance(token, sql.Package) and imt(token, m=sql.PackageHeading.M_OPEN):
                iidx, itoken = tlist.token_next_by(m=sql.PackageHeading.M_NEXT, idx=tidx)
                if itoken:
                    last = tlist.parent.token_last(skip_cm=True)
                    tlist.parent.group_tokens(sql.Statement, 0, tlist.parent.token_index(last), extend=True)
                    aidx, token = tlist.token_next_by(m=sql.PackageHeading.M_CLOSE)
                    tlist.group_tokens(sql.PackageHeading, iidx, aidx)
                    tlist.group_tokens(sql.Package, tidx, len(tlist.tokens))  # .get_fp()
                continue

    @recurse(sql.CursorDef)
    def group_cursor_def(self, tlist):
        tidx, token = tlist.token_next_by(m=sql.CursorDef.M_OPEN)
        while token:
            nid, ntk = tlist.token_next(idx=tidx)
            if isinstance(ntk, sql.Function) or ntk.ttype == T.Name:
                isid, istk = tlist.token_next_by(m=sql.CursorDef.M_MIDDLE, idx=nid)
                nidx, ntkn = tlist.token_next(idx=isid, skip_cm=True)
                if isinstance(ntkn, sql.Union) or isinstance(ntkn, sql.Select):
                    tlist.group_tokens(sql.CursorDef, tidx, nidx)
            tidx, token = tlist.token_next_by(m=sql.CursorDef.M_OPEN, idx=tidx)

    def group_exceptions(self, tlist):
        def match(token):
            return token.is_keyword and (token.match(*sql.Exceptions.M_OPEN) or token.match(*sql.Exceptions.M_CLOSE))

        def valid_prev(token):
            return token.is_keyword and token.match(*sql.Exceptions.M_OPEN)

        def valid_next(token):
            return token is not None and token.is_keyword and token.match(*sql.Exceptions.M_CLOSE)

        def post(tlist, pidx, tidx):
            return pidx, tlist.token_prev(tidx, skip_cm=True)[0]

        tidx_offset = 0
        pidx, prev_ = None, None
        for idx, token in enumerate(list(tlist)):
            tidx = idx - tidx_offset

            if token.is_whitespace:
                continue

            if token.is_group and not isinstance(token, sql.Exceptions):
                self.group_exceptions(token)

            if match(token):
                if prev_ and valid_prev(prev_) and valid_next(token):
                    from_idx, to_idx = post(tlist, pidx, tidx)
                    grp = tlist.group_tokens(sql.Exceptions, from_idx, to_idx)

                    tidx_offset += to_idx - from_idx
                    pidx, prev_ = from_idx, grp
                    continue

                pidx, prev_ = tidx, token

    def group(self, stmt):
        for func in [
            self.group_comments,

            self.group_package,

            self.group_brackets,
            self.group_parenthesis,
            self.group_dml,
            self.group_select,
            self.group_case,
            self.group_openlooptag,
            self.group_if,
            self.group_for,
            self.group_begin,

            self.group_exit,

            self.group_procedure_heading,
            self.group_function_heading,

            self.group_function_return_type,

            self.group_functions,
            self.group_where,

            self.group_union,

            self.group_period,
            self.group_arrays,
            self.group_identifier,
            self.group_order,
            self.group_typecasts,
            self.group_operator,
            self.group_notfound,
            self.group_comparison,
            self.group_as,
            self.group_aliased,
            self.group_assignment,

            self.align_comments,
            self.group_function_params,
            self.group_identifier_list,

            self.flatter_statement_class,
            self.flatter_identifier_class,

            self.group_cursor_def,

            # self.group_procedure_heading,
            self.group_procedure_block,

            # self.group_function_heading,
            self.group_function_block,

            self.group_declare_section,

            self.group_exceptions,

            # self.group_transaction,

            self.group_open
        ]:
            func(stmt)
        return stmt

    def _group(self, tlist, cls, match,
               valid_prev=lambda t: True,
               valid_next=lambda t: True,
               post=None,
               extend=True,
               recurse=True,
               skip_cm=False
               ):
        """Groups together tokens that are joined by a middle token. ie. x < y"""

        tidx_offset = 0
        pidx, prev_ = None, None
        for idx, token in enumerate(list(tlist)):
            tidx = idx - tidx_offset

            if token.is_whitespace:
                continue

            if recurse and token.is_group and not isinstance(token, cls):
                self._group(token, cls, match, valid_prev, valid_next, post, extend, skip_cm=skip_cm)

            if match(token):
                nidx, next_ = tlist.token_next(tidx, skip_cm=skip_cm)
                if prev_ and valid_prev(prev_) and valid_next(next_):
                    from_idx, to_idx = post(tlist, pidx, tidx, nidx)
                    grp = tlist.group_tokens(cls, from_idx, to_idx, extend=extend)

                    tidx_offset += to_idx - from_idx
                    pidx, prev_ = from_idx, grp
                    continue

            pidx, prev_ = tidx, token
