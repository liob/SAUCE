# -*- coding: utf-8 -*-
'''
Created on 12.11.2012

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

from tg import flash, config, request
from tg.decorators import before_render

from sauce.controllers.crc.base import FilterCrudRestController
from sauce.model import Team, User, Lesson

from webhelpers.html.tags import link_to

import logging
log = logging.getLogger(__name__)

__all__ = ['TeamsCrudController', 'StudentsCrudController', 'TutorsCrudController']


def _email_team(filler, obj):
    return u'<a href="mailto:%s?subject=%%5BSAUCE%%5D" class="btn btn-mini"'\
        'onclick="return confirm(\'This will send an eMail to %d people. '\
        'Are you sure?\')">'\
        '<i class="icon-envelope"></i>&nbsp;eMail</a>' % (
            ','.join(s.email_address for s in obj.students), len(obj.students))


class TeamsCrudController(FilterCrudRestController):

    model = Team

    __table_options__ = {
        #'__omit_fields__': ['lesson_id'],
        '__field_order__': ['id', 'name', 'lesson_id', 'lesson', 'members', 'email'],
        '__search_fields__': ['id', 'lesson_id', 'name'],
        '__xml_fields__': ['lesson', 'members', 'email'],
        'lesson': lambda filler, obj: \
            link_to(obj.lesson.name, '../lessons/%d/edit' % obj.lesson.id),
        'members': lambda filler, obj: \
            ', '.join(link_to(student.display_name, '../students/%d/edit' % student.id) \
                for student in obj.members),
        'email': _email_team,
        '__base_widget_args__': {'sortList': [[3, 0], [1, 0]]},
    }
    __form_options__ = {
        '__omit_fields__': ['id'],
        '__field_order__': ['id', 'name', 'lesson', 'members'],
        '__dropdown_field_names__': ['user_name', '_name', 'name', 'title'],
    }


#--------------------------------------------------------------------------------


def set_password(user):
    '''Sets the password for user to a new autogenerated password and displays it via flash'''
    password = user.generate_password()
    flash('Password for User %s set to: %s' % (user.user_name, password), 'info')
    return password


def _new_password(filler, obj):
    if config.get('externalauth', False):
        return u'<a href="#" class="btn btn-mini disabled"'\
            'onclick="return alert(\'Password changes are disabled because '\
            'external authentication is used!\')">'\
            '<i class="icon-random"></i> New password</a>'
    else:
        return u'<a href="%d/password" class="btn btn-mini"'\
            'onclick="return confirm(\'This will generate a new, randomized '\
            'password for the User %s and show it to you. Are you sure?\')">'\
            '<i class="icon-random"></i> New password</a>' % (obj.id, obj.display_name)


def _email_address(filler, obj):
    return u'<a href="mailto:%s?subject=%%5BSAUCE%%5D" style="white-space: pre;" class="btn btn-mini">'\
        '<i class="icon-envelope"></i>&nbsp;%s</a>' % (obj.email_address, obj.email_address)


class StudentsCrudController(FilterCrudRestController):

    model = User
    menu_item = u'Student'

    __table_options__ = {
        '__omit_fields__': [
            'type', 'groups',
            'password', '_password',
            '_last_name', '_first_name',
            'created',
            'submissions', 'judgements',
            'tutored_lessons', 'teached_events',
        ],
        '__field_order__': [
            'id',
            'user_name',
            '_display_name',
            'email_address',
            'teams', '_lessons',
            'new_password',
        ],
        '__search_fields__': [
            'id', 'user_name', 'email_address',
            ('teams', 'team_id'), ('lessons', 'lesson_id'),
        ],
#        '__headers__': {
#            'new_password': u'Password',
#            '_lessons': u'Lessons'},
        '__xml_fields__': ['email_address', 'teams', '_lessons', 'new_password'],
        'email_address': _email_address,
        'teams': lambda filler, obj: \
            ', '.join(link_to(team.name, '../teams/%d/edit' % team.id) \
                    for team in obj.teams if team in filler.query_modifiers['teams'](Team.query)),
        '_lessons': lambda filler, obj: \
            ', '.join(link_to(lesson.name, '../lessons/%d/edit' % lesson.id) \
                    for lesson in obj._lessons if lesson in filler.query_modifiers['_lessons'](Lesson.query)),
        'new_password': _new_password,
        '__base_widget_args__': {
            'headers': {8: {'sorter': False}},
            'sortList': [[6, 0], [5, 0], [3, 0]],
        },
    }
    __form_options__ = {
        '__omit_fields__': [
            'id',
            'type', 'groups',
            'display_name',
            '_first_name', '_last_name',
            'password', '_password',
            'created',
            'submissions', 'judgements',
            'tutored_lessons', 'teached_events',
            'teams', '_lessons',
        ],
        '__field_order__': [
            'id',
            'user_name', '_display_name',
            'email_address',
#            'teams', '_lessons',
        ],
    }
    __setters__ = {
        'password': ('password', set_password),
    }


class TutorsCrudController(FilterCrudRestController):

    model = User
    menu_item = u'Tutor'

    __table_options__ = {
        '__omit_fields__': [
            'type', 'groups',
            'password', '_password',
            '_last_name', '_first_name',
            'created',
            'submissions', 'judgements',
            'teached_events',
            '_lessons', 'teams',
            ],
        '__field_order__': [
            'id',
            'user_name',
            '_display_name',
            'email_address',
            'tutored_lessons',
            'new_password'
        ],
        '__search_fields__': [
            'id', 'user_name', 'email_address',
            ('tutored_lessons', 'lesson_id')],
#        '__headers__': {
#            'new_password': u'Password',
#            'tutored_lessons': u'Lessons'},
        '__xml_fields__': ['email_address', 'tutored_lessons', 'new_password'],
        'email_address': _email_address,
        'tutored_lessons': lambda filler, obj: \
            ', '.join(link_to(lesson.name, '../lessons/%d/edit' % lesson.id) \
                for lesson in obj.tutored_lessons if lesson in filler.query_modifiers['tutored_lessons'](Lesson.query)),
        'new_password': _new_password,
        '__base_widget_args__': {
            'headers': {7: {'sorter': False}},
            'sortList': [[5, 0], [3, 0]],
        },
    }
    __form_options__ = {
        '__omit_fields__': [
            'id',
            'type', 'groups',
            '_last_name', '_first_name',
            'display_name',
            'password', '_password',
            'created',
            'submissions', 'judgements',
            '_lessons', 'teams',
            'tutored_lessons', 'teached_events',
        ],
        '__field_order__': [
            'id',
            'user_name', '_display_name',
            'email_address',
#            'tutored_lessons',
        ],
    }
    __setters__ = {
        'password': ('password', set_password),
    }


class TeachersCrudController(TutorsCrudController):

    menu_item = u'Teacher'

    def __init__(self, *args, **kw):
        from warnings import warn
        warn('TeachersCrudController used', DeprecationWarning)
        super(TeachersCrudController, self).__init__(*args, **kw)


def warn_externalauth(self, *args, **kw):
    if config.get('externalauth', False):
        s = request.controller_state.controller
        if s.model == User:
            flash('Profile changes are not possible because external authentication is used!', 'error')


before_render(warn_externalauth)(StudentsCrudController.edit)
before_render(warn_externalauth)(TutorsCrudController.edit)
before_render(warn_externalauth)(TeachersCrudController.edit)
