.. _analyze:

Analyzing the Parsed Statement
==============================

When the :meth:`~bplsqlparse.parse` function is called the returned value
is a tree-ish representation of the analyzed statements. The returned
objects can be used by applications to retrieve further information about
the parsed SQL.


Base Classes
------------

All returned objects inherit from these base classes.
The :class:`~bplsqlparse.sql.Token` class represents a single token and
:class:`~bplsqlparse.sql.TokenList` class is a group of tokens.
The latter provides methods for inspecting its child tokens.

.. autoclass:: bplsqlparse.sql.Token
   :members:

.. autoclass:: bplsqlparse.sql.TokenList
   :members:


SQL Representing Classes
------------------------

The following classes represent distinct parts of a SQL statement.

.. autoclass:: bplsqlparse.sql.Statement
   :members:

.. autoclass:: bplsqlparse.sql.Comment
   :members:

.. autoclass:: bplsqlparse.sql.Identifier
   :members:

.. autoclass:: bplsqlparse.sql.IdentifierList
   :members:

.. autoclass:: bplsqlparse.sql.Where
   :members:

.. autoclass:: bplsqlparse.sql.Case
   :members:

.. autoclass:: bplsqlparse.sql.Parenthesis
   :members:

.. autoclass:: bplsqlparse.sql.If
   :members:

.. autoclass:: bplsqlparse.sql.For
   :members:

.. autoclass:: bplsqlparse.sql.Assignment
   :members:

.. autoclass:: bplsqlparse.sql.Comparison
   :members:

