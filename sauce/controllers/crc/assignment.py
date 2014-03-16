# -*- coding: utf-8 -*-
'''CrudControllers for Sheet and Assignment entities

@see: :mod:`sauce.controllers.crc.base`

TODO: If possible, syntax highlighting for scaffold and template
TODO: tw2.dynforms to display scaffold field conditionally

@since: 12.11.2012
@author: moschlar
'''
#
## SAUCE - System for AUtomated Code Evaluation
## Copyright (C) 2013 Moritz Schlarb
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU Affero General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU Affero General Public License for more details.
##
## You should have received a copy of the GNU Affero General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from sauce.controllers.crc.base import FilterCrudRestController
from sauce.model import Sheet, Assignment
import sauce.lib.helpers as h

from webhelpers.html.tags import link_to

import tw2.bootstrap.forms as twb
try:
    from tw2.ace import AceWidget as SourceEditor
#    from tw2.codemirror import CodeMirrorWidget as SourceEditor
except ImportError:  # pragma: no cover
    from tw2.bootstrap.forms import TextArea as SourceEditor

import logging
log = logging.getLogger(__name__)

__all__ = ['SheetsCrudController', 'AssignmentsCrudController']


#--------------------------------------------------------------------------------


def _submissions(filler, obj):
    '''Display submission link button for Assignments or Sheets'''
    return (u'<a href="%s/submissions" style="white-space: pre;" class="btn btn-mini">'
        '<i class="icon-inbox"></i>&nbsp;Submissions</a>' % (obj.url))

#--------------------------------------------------------------------------------


class SheetsCrudController(FilterCrudRestController):
    '''CrudController for Sheets'''

    model = Sheet

    __table_options__ = {
        '__omit_fields__': [
            'id', 'description', 'event_id', 'event', 'teacher',
            '_teacher', 'teacher_id', '_url', '_start_time', '_end_time',
        ],
        '__field_order__': [
            'sheet_id', 'name', 'public',
            'start_time', 'end_time', 'assignments',
            'submissions',
        ],
        '__search_fields__': ['id', 'sheet_id', 'name', ('assignments', 'assignment_id')],
        '__xml_fields__': ['assignments', 'submissions'],
        'start_time': lambda filler, obj: h.strftime(obj.start_time, False),
        'end_time': lambda filler, obj: h.strftime(obj.end_time, False),
        'assignments': lambda filler, obj:
            ', '.join(link_to(ass.name, '../assignments/%d/edit' % ass.id)
                for ass in obj.assignments),
        'submissions': _submissions,
        '__base_widget_args__': {'sortList': [[1, 0]]},
    }
    __form_options__ = {
        '__omit_fields__': [
            'id', '_url', 'assignments', 'teacher', '_teacher',
        ],
        '__hide_fields__': ['event'],
        '__field_order__': [
            'id', 'sheet_id', 'name', 'description',
            'public', '_start_time', '_end_time',
        ],
        '__field_widget_args__': {
            '_start_time': {
                'help_text': u'Leave empty to use value from event',
            },
            '_end_time': {
                'help_text': u'Leave empty to use value from event',
            },
            'sheet_id': {
                'label': u'Sheet Id',
                'help_text': u'This id will be part of the url and has to be unique for the parent event',
            },
            'public': {
                'help_text': u'Make sheet visible for students',
            },
        },
        '__require_fields__': ['sheet_id'],
    }


class AssignmentsCrudController(FilterCrudRestController):
    '''CrudController for Assignments'''

    model = Assignment

    __table_options__ = {
        '__omit_fields__': [
            'id', 'event_id', '_event', '_url',
            'teacher_id', 'teacher',
            #'allowed_languages',
            '_teacher', 'description', 'tests',
            'show_compiler_msg',
            '_start_time', '_end_time',
            'lti',
            'submission_filename', 'submission_template',
            'submission_scaffold_show',
            'submission_scaffold_head', 'submission_scaffold_foot',
        ],
        '__field_order__': [
            'sheet_id', 'sheet', 'assignment_id', 'name',
            'public', 'start_time', 'end_time',
            'timeout', 'allowed_languages',
            'submissions',
        ],
        '__search_fields__': ['id', 'sheet_id', 'assignment_id', 'name'],
        '__xml_fields__': ['sheet', 'allowed_languages', 'submissions'],
        'start_time': lambda filler, obj: h.strftime(obj.start_time, False),
        'end_time': lambda filler, obj: h.strftime(obj.end_time, False),
        'sheet': lambda filler, obj:
            link_to(obj.sheet.name, '../sheets/%d/edit' % obj.sheet.id),
        'allowed_languages': lambda filler, obj:
            ', '.join(link_to(l.name, '/languages/%d' % l.id)
                for l in obj.allowed_languages),
        'submissions': _submissions,
        '__base_widget_args__': {'sortList': [[1, 0], [3, 0]]},
    }
    __form_options__ = {
        '__omit_fields__': [
            'id', 'tests', 'submissions', '_event', 'teacher', '_url', '_teacher',
            'lti',
        ],
        '__add_fields__': {
            'submission_note': twb.Label('submission_note', label='Note', css_class='bold',
                text='For obvious reasons, it might not be the best idea to '
                    'pre-define submission data here, '
                    'when multiple languages are allowed.'),
        },
        '__field_order__': [
            'id', 'sheet', 'assignment_id', 'name', 'description',
            'public', '_start_time', '_end_time',
            'timeout', 'allowed_languages', 'show_compiler_msg',
            'submission_note',
            'submission_filename', 'submission_template',
            'submission_scaffold_show',
            'submission_scaffold_head', 'submission_scaffold_foot',
        ],
        '__field_widget_types__': {
            'submission_template': SourceEditor,
            'submission_scaffold_head': SourceEditor,
            'submission_scaffold_foot': SourceEditor,
        },
        '__field_widget_args__': {
            'assignment_id': {
                'label': u'Assignment Id',
                'help_text': u'Will be part of the url and has to be unique for the parent sheet',
            },
            'public': {
                'help_text': u'Make assignment visible for students',
            },
            '_start_time': {
                'help_text': u'Leave empty to use value from sheet',
            },
            '_end_time': {
                'help_text': u'Leave empty to use value from sheet',
            },
            'timeout': {
                'help_text': u'Default timeout value for test cases, leave empty for no time limit',
            },
            'show_compiler_msg': {
                'help_text': u'Show error messages or warnings from the compiler run',
            },
            'submission_filename': {
                'help_text': u'Default filename for submission',
            },
            'submission_template': {
                'help_text': u'Template for submission source body',
                'css_class': 'span7', 'cols': 80, 'rows': 6,
            },
            'submission_scaffold_show': {
                'help_text': u'Whether to show head and foot scaffold to student',
            },
            'submission_scaffold_head': {
                'help_text': u'Enforced head for submission source',
                'css_class': 'span7', 'cols': 80, 'rows': 6,
            },
            'submission_scaffold_foot': {
                'help_text': u'Enforced foot for submission source',
                'css_class': 'span7', 'cols': 80, 'rows': 6,
            },
        },
        '__require_fields__': ['assignment_id', 'sheet'],
    }
