# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import six
from sqlalchemy import (
        Column, Text, Integer, Float, Boolean,
        PrimaryKeyConstraint, ForeignKeyConstraint)


# Internal

def convert_table(prefix, table):
    """Convert high-level table name to database name.
    """
    return prefix + table


def restore_table(prefix, table):
    """Restore database table name to high-level name.
    """
    if table.startswith(prefix):
        return table.replace(prefix, '', 1)
    return None


def convert_schema(prefix, table, schema):  # noqa
    """Convert JSONTableSchema schema to SQLAlchemy columns and constraints.
    """

    # Init
    columns = []
    constraints = []

    # Mapping
    mapping = {
        'string': Text(),
        'integer': Integer(),
        'number': Float(),
        'boolean': Boolean(),
    }

    # Fields
    for field in schema['fields']:
        try:
            column_type = mapping[field['type']]
        except KeyError:
            message = 'Type %s is not supported' % field['type']
            raise TypeError(message)
        nullable = not field.get('constraints', {}).get('required', False)
        column = Column(field['name'], column_type, nullable=nullable)
        columns.append(column)

    # Primary key
    pk = schema.get('primaryKey', None)
    if pk is not None:
        if isinstance(pk, six.string_types):
            pk = [pk]
        constraint = PrimaryKeyConstraint(*pk)
        constraints.append(constraint)

    # Foreign keys
    fks = schema.get('foreignKeys', [])
    for fk in fks:
        fields = fk['fields']
        if isinstance(fields, six.string_types):
            fields = [fields]
        resource = fk['reference']['resource']
        if resource == 'self':
            resource = table
        elif resource == '<table>':
            resource = convert_table(prefix, fk['reference']['table'])
        else:
            message = 'Supported only "self" and "<table>" references.'
            raise ValueError(message)
        references = fk['reference']['fields']
        if isinstance(references, six.string_types):
            references = [references]
        joiner = lambda reference: '.'.join([resource, reference])  # noqa
        references = list(map(joiner, references))
        constraint = ForeignKeyConstraint(fields, references)
        constraints.append(constraint)

    return (columns, constraints)


def restore_schema(prefix, table, columns, constraints):  # noqa
    """Convert SQLAlchemy columns and constraints to JSONTableSchema schema.
    """

    # Init
    schema = {}

    # Mapping
    mapping = {
        Text: 'string',
        Integer: 'integer',
        Float: 'number',
        Boolean: 'boolean',
    }

    # Fields
    fields = []
    for column in columns:
        try:
            field_type = [value for col_type, value in mapping.items()
                          if isinstance(column.type, col_type)][0]
        except IndexError:
            message = 'Type %s is not supported' % column.type
            raise TypeError(message)
        field = {'name': column.name, 'type': field_type}
        if not column.nullable:
            field['constraints'] = {'required': True}
        fields.append(field)
    schema['fields'] = fields

    # Primary key
    pk = []
    for constraint in constraints:
        if isinstance(constraint, PrimaryKeyConstraint):
            for column in constraint.columns:
                pk.append(column.name)
    if len(pk) > 0:
        if len(pk) == 1:
            pk = pk.pop()
        schema['primaryKey'] = pk

    # Foreign keys
    fks = []
    for constraint in constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            fields = []
            reftable = None
            resource = None
            references = []
            for element in constraint.elements:
                fields.append(element.parent.name)
                references.append(element.column.name)
                if element.column.table.name == table:
                    resource = 'self'
                else:
                    reftable = restore_table(
                            prefix, element.column.table.name)
            if len(fields) == len(references) == 1:
                fields = fields.pop()
                references = references.pop()
            fk = {
                'fields': fields,
                'reference': {
                    'fields': references,
                }
            }
            if resource is not None:
                fk['reference']['resource'] = resource
            if reftable is not None:
                fk['reference']['resource'] = '<table>'
                fk['reference']['table'] = reftable
            fks.append(fk)
    if len(fks) > 0:
        schema['foreignKeys'] = fks

    return schema