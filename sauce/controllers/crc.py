# -*- coding: utf-8 -*-
'''
Created on 15.04.2012

TODO: All these classes are a huge bunch of crappy spaghetti code...

@author: moschlar
'''

import os
import logging

from tg import expose, tmpl_context as c, request, flash, app_globals as g, lurl, abort
from tg.decorators import before_validate, cached_property, before_render, override_template
from tgext.crud import CrudRestController, EasyCrudRestController

#from tw2.forms import TextField, SingleSelectField, Label, TextArea, CheckBox
#from tw2.tinymce import TinyMCEWidget
import tw2.core as twc
import tw2.tinymce as twt
import tw2.bootstrap.forms as twb
import tw2.jqplugins.chosen.widgets as twjc
import sprox.widgets.tw2widgets.widgets as sw
from sprox.sa.widgetselector import SAWidgetSelector
from formencode.validators import PlainText
from sqlalchemy import desc as _desc
import sqlalchemy.types as sqlat
from sqlalchemy.orm import class_mapper
from webhelpers.html.tags import link_to
from webhelpers.html.tools import mail_to

from sauce.model import (DBSession, Event, Lesson, Team, User, Sheet,
                         Assignment, Test, NewsItem)
from sauce.widgets.datagrid import JSSortableDataGrid
from webhelpers.html.builder import literal
from sqlalchemy.orm.properties import RelationshipProperty

__all__ = ['TeamsCrudController', 'StudentsCrudController', 'TutorsCrudController',
    'TeachersCrudController', 'EventsCrudController', 'LessonsCrudController',
    'SheetsCrudController', 'AssignmentsCrudController', 'TestsCrudController',
    'NewsItemController']

log = logging.getLogger(__name__)


#--------------------------------------------------------------------------------


def set_password(user):
    '''Sets the password for user to a new autogenerated password and displays it via flash'''
    password = user.generate_password()
    flash('Password for User %s set to: %s' % (user.user_name, password), 'info')
    return password


class ChosenPropertyMultipleSelectField(twjc.ChosenMultipleSelectField, sw.PropertyMultipleSelectField):

    def _validate(self, value, state=None):
        # Fix inspired by twf.MultipleSelectionField
        if value and not isinstance(value, (list, tuple)):
            value = [value]
        return super(ChosenPropertyMultipleSelectField, self)._validate(value, state)


class ChosenPropertySingleSelectField(twjc.ChosenSingleSelectField, sw.PropertySingleSelectField):
    pass


class MyWidgetSelector(SAWidgetSelector):
    default_multiple_select_field_widget_type = ChosenPropertyMultipleSelectField
    default_single_select_field_widget_type = ChosenPropertySingleSelectField

    def __init__(self, *args, **kw):
        super(MyWidgetSelector, self).__init__(*args, **kw)
#        self.default_widgets.update({sqlat.DateTime: twb.CalendarDateTimePicker})


#--------------------------------------------------------------------------------


class FilteredCrudRestController(EasyCrudRestController):
    '''Generic base class for CrudRestControllers with filters'''
    
    def __init__(self, query_modifier=None, filters=[], filter_bys={},
                 menu_items={}, inject={}, btn_new=True, btn_delete=True,
                 path_prefix='..'):
        '''Initialize FilteredCrudRestController with given options
        
        Arguments:
        
        ``query_modifier``:
            A callable that may modify the base query from the model entity
            if you need to use more sophisticated query functions than
            filters
        ``filters``:
            A list of sqlalchemy filter expressions
        ``filter_bys``:
            A dict of sqlalchemy filter_by keywords
        ``menu_items``:
            A dict of menu_items for ``EasyCrudRestController``
        ``inject``:
            A dict of values to inject into POST requests before validation
        ``btn_new``:
            Whether the "New <Entity>" link shall be displayed on get_all
        ``path_prefix``:
            Url prefix for linked paths (``menu_items`` and inter-entity links)
            Default: ``..``
        '''
        
#        if not hasattr(self, 'table'):
#            class Table(JSSortableTableBase):
#                __entity__ = self.model
#            self.table = Table(DBSession)
        
        self.btn_new = btn_new
        self.btn_delete = btn_delete
        self.inject = inject
        
        self.__table_options__['__base_widget_type__'] = JSSortableDataGrid
        if '__base_widget_args__' in self.__table_options__:
            if 'headers' in self.__table_options__['__base_widget_args__']:
                self.__table_options__['__base_widget_args__']['headers'].update({0: { 'sorter': False} })
            else:
                self.__table_options__['__base_widget_args__'].update({'headers': {0: { 'sorter': False} }})
        else:
            self.__table_options__['__base_widget_args__'] = {'headers': {0: { 'sorter': False} }}
        
        self.__form_options__['__base_widget_type__'] = twb.HorizontalForm
        self.__form_options__['__widget_selector__'] = MyWidgetSelector()
        
        # Since DBSession is a scopedsession we don't need to pass it around,
        # so we just use the imported DBSession here
        super(FilteredCrudRestController, self).__init__(DBSession, menu_items)
        
        self.table_filler.path_prefix = path_prefix.rstrip('/')
        
        def custom_do_get_provider_count_and_objs(**kw):
            '''Custom getter function respecting provided filters and filter_bys
            
            Returns the result count from the database and a query object
            
            Mostly stolen from sprox.sa.provider and modified accordingly
            '''
            
            # Get keywords that are not filters
            limit = kw.pop('limit', None)
            offset = kw.pop('offset', None)
            order_by = kw.pop('order_by', None)
            desc = kw.pop('desc', False)
            
            qry = self.model.query
            
            if query_modifier:
                qry = query_modifier(qry)
            
            # Process pre-defined filters
            if filters:
                qry = qry.filter(*filters)
            if filter_bys:
                qry = qry.filter_by(**filter_bys)
            
            # Process filters from url
            kwfilters = kw
            exc = False
            try:
                kwfilters = self.table_filler.__provider__._modify_params_for_dates(self.model, kwfilters)
            except ValueError as e:
                log.info('Could not parse date filters', exc_info=True)
                flash('Could not parse date filters: %s.' % e.message, 'error')
                exc = True
            
            try:
                kwfilters = self.table_filler.__provider__._modify_params_for_relationships(self.model, kwfilters)
            except (ValueError, AttributeError) as e:
                log.info('Could not parse relationship filters', exc_info=True)
                flash('Could not parse relationship filters: %s. '
                      'You can only filter by the IDs of relationships, not by their names.' % e.message, 'error')
                exc = True
            if exc:
                # Since any non-parsed kwfilter is bad, we just have to ignore them all now
                kwfilters = {}
            
            for field_name, value in kwfilters.iteritems():
                try:
                    field = getattr(self.model, field_name)
                    if self.table_filler.__provider__.is_relation(self.model, field_name) and isinstance(value, list):
                        value = value[0]
                        qry = qry.filter(field.contains(value))
                    else:
                        typ = self.table_filler.__provider__.get_field(self.model, field_name).type
                        if isinstance(typ, sqlat.Integer):
                            value = int(value)
                            qry = qry.filter(field==value)
                        elif isinstance(typ, sqlat.Numeric):
                            value = float(value)
                            qry = qry.filter(field==value)
                        else:
                            qry = qry.filter(field.like('%%%s%%' % value))
                except:
                    log.warn('Could not create filter on query', exc_info=True)
            
            # Get total count
            count = qry.count()
            
            # Process ordering
            if order_by is not None:
                field = getattr(self.model, order_by)
                if desc:
                    field = _desc(field)
                qry = qry.order_by(field)
            
            # Process pager options
            if offset is not None:
                qry = qry.offset(offset)
            if limit is not None:
                qry = qry.limit(limit)
            
            return count, qry
        # Assign custom getter function to table_filler
        self.table_filler._do_get_provider_count_and_objs = custom_do_get_provider_count_and_objs
        
        self.table_filler.__actions__ = self.custom_actions
        
        #TODO: We need a custom get_obj function, too to respect the filters...
        #      Probably a custom SAProvider would suffice.
    
    def custom_actions(self, obj):
        """Display bootstrap-enabled action fields"""
        result, delete_modal = [], u''
        count = 0
        try:
            result.append(u'<a href="'+obj.url+'" class="btn btn-mini" title="Show">'
                u'<i class="icon-eye-open"></i></a>')
            count += 1
        except:
            pass
        try:
            primary_fields = self.table_filler.__provider__.get_primary_fields(self.table_filler.__entity__)
            pklist = u'/'.join(map(lambda x: unicode(getattr(obj, x)), primary_fields))
            result.append(u'<a href="'+pklist+'/edit" class="btn btn-mini" title="Edit">'
                u'<i class="icon-pencil"></i></a>')
        except:
            pass
        if self.btn_delete:
            result.append(
                u'<a class="btn btn-mini btn-danger" data-toggle="modal" href="#deleteModal%d" title="Delete">'
                u'  <i class="icon-remove icon-white"></i>'
                u'</a>' % (obj.id))
            related_relations = {}
            for prop in class_mapper(obj.__class__).iterate_properties:
                if isinstance(prop, RelationshipProperty):
                    if prop.cascade.delete:
                        r = getattr(obj, prop.key)
                        if r:
                            related_relations[prop.mapper.class_.__name__] =list(r)
            delete_modal = u'''
<div class="modal hide fade" id="deleteModal%d">
  <div class="modal-header">
    <button type="button" class="close" data-dismiss="modal">×</button>
    <h3>Are you sure?</h3>
  </div>
  <div class="modal-body">
    <p>
      This will delete "%s" from the database.<br />
''' % (obj.id, unicode(obj))
            if related_relations:
                delete_modal += u'The following numbers of related entities will be deleted, too: '
                delete_modal += u', '.join((k + u's: ' + unicode(len(related_relations[k])) for k in related_relations))
                delete_modal += u'<br /><small>Those are currently only <b>first-level</b> related entities! The real number of deletions can be higher!</small><br />'
            delete_modal += u'''You can not revert this step!
    </p>
  </div>
  <div class="modal-footer">
    <form method="POST" action="%s">
      <a href="#" class="btn" data-dismiss="modal">Cancel</a>
      <input type="hidden" name="_method" value="DELETE" />
      <button type="submit" class="btn btn-danger">
        <i class="icon-remove icon-white"></i>&nbsp;Delete&nbsp;"%s"
      </button>
    </form>
  </div>
</div>
''' % (pklist, unicode(obj))
        return literal('<div class="btn-group" style="width: %dpx;">'
            % (len(result) * 30) + ''.join(result) + '</div>' + delete_modal)

    @staticmethod
    def before_get_all(remainder, params, output):
        # Disable pagination for get_all
        output['value_list'].page_count = 0
        output['value_list'] = output['value_list'].original_collection
        c.paginators = []

        # Use my bootstrap-enabled template
        override_template(FilteredCrudRestController.get_all,
            'mako:sauce.templates.get_all')

        # And respect __search_fields__ as long as tgext.crud doesn't use them
        s = request.controller_state.controller
        if hasattr(s.table, '__search_fields__'):
            output['headers'] = []
            for field in s.table.__search_fields__:
                if isinstance(field, tuple):
                    output['headers'].append((field[0], field[1]))
                else:
                    output['headers'].append((field, field))
        try:
            c.btn_new = s.btn_new
        except AttributeError:
            c.btn_new = True

    @staticmethod
    def before_new(remainder, params, output):
        s = request.controller_state.controller
        if hasattr(s, 'btn_new') and not s.btn_new:
            abort(403)
        # Use my bootstrap-enabled template
        override_template(FilteredCrudRestController.new,
            'mako:sauce.templates.new')

    @staticmethod
    def before_edit(remainder, params, output):
        # Use my bootstrap-enabled template
        override_template(FilteredCrudRestController.edit,
            'mako:sauce.templates.edit')

    @cached_property
    def mount_point(self):
        return '.'

    @classmethod
    def injector(cls, remainder, params):
        '''Injects the objects from self.inject into params

        self.inject has to be a dictionary of key, object pairs
        '''
        # Get currently dispatched controller instance
        # Does not work, only returns last statically dispatch controller,
        # but we use _lookup in EventsController
        #s = dispatched_controller()
        s = request.controller_state.controller

        if hasattr(s, 'inject'):
            for i in s.inject:
                params[i] = s.inject[i]

# Register injection hook for POST requests
before_validate(FilteredCrudRestController.injector)\
    (FilteredCrudRestController.post)

# Register hook for get_all
before_render(FilteredCrudRestController.before_get_all)\
    (FilteredCrudRestController.get_all)
# Register hook for new
before_render(FilteredCrudRestController.before_new)\
    (FilteredCrudRestController.new)
# Register hook for edit
before_render(FilteredCrudRestController.before_edit)\
    (FilteredCrudRestController.edit)

#--------------------------------------------------------------------------------

def _email_team(filler, obj):
    return u'<a href="mailto:%s?subject=%%5BSAUCE%%5D" class="btn btn-mini"'\
        'onclick="return confirm(\'This will send an eMail to %d people. '\
        'Are you sure?\')">'\
        '<i class="icon-envelope"></i>&nbsp;eMail</a>' % (','.join(s.email_address for s in obj.students), len(obj.students))


class TeamsCrudController(FilteredCrudRestController):
    
    model = Team
    
    __table_options__ = {
        #'__omit_fields__': ['lesson_id'],
        '__field_order__': ['id', 'name', 'lesson_id', 'lesson', 'members', 'email'],
        '__search_fields__': ['id', 'lesson_id', 'name'],
        '__xml_fields__': ['lesson', 'members', 'email'],
        'lesson': lambda filler, obj: link_to(obj.lesson.name, '../lessons/%d/edit' % obj.lesson.id),
        'members': lambda filler, obj: ', '.join(link_to(student.display_name, '../students/%d/edit' % student.id) for student in obj.members),
        'email': _email_team,
        '__base_widget_args__': {'sortList': [[3, 0], [1, 0]]},
        }
    __form_options__ = {
        '__omit_fields__': ['id'],
        '__field_order__': ['id', 'name', 'lesson', 'members'],
        '__field_widget_types__': {'name': twb.TextField},
        '__field_widget_args__': {'students': {'size': 10}},
        }

#--------------------------------------------------------------------------------

def _new_password(filler, obj):
    return u'<a href="%d/password" class="btn btn-mini"'\
        'onclick="return confirm(\'This will generate a new, randomized '\
        'password for the User %s and show it to you. Are you sure?\')">'\
        '<i class="icon-random"></i> New password</a>' % (obj.id, obj.display_name)

def _email_address(filler, obj):
    return u'<a href="mailto:%s?subject=%%5BSAUCE%%5D" style="white-space: pre;" class="btn btn-mini">'\
        '<i class="icon-envelope"></i>&nbsp;'\
        '%s</a>' % (obj.email_address, obj.email_address)


class StudentsCrudController(FilteredCrudRestController):

    model = User

    __table_options__ = {
        '__omit_fields__': [
            'type', 'groups',
            'password', '_password',
            'last_name', 'first_name',
            'submissions',
            'tutored_lessons'
            ],
        '__field_order__': [
            'id', 'user_name',
            'display_name', 'email_address',
            'teams', '_lessons',
            'created', 'new_password'],
        '__search_fields__': [
            'id', 'user_name', 'email_address',
            ('teams', 'team_id'), ('lessons', 'lesson_id')],
#        '__headers__': {
#            'new_password': u'Password',
#            '_lessons': u'Lessons'},
        '__xml_fields__': ['_lessons', 'teams', 'email_address', 'new_password'],
        'created': lambda filler, obj: obj.created.strftime('%x %X'),
        'display_name': lambda filler, obj: obj.display_name,
        'new_password': _new_password,
        'email_address': _email_address,
        'teams': lambda filler, obj: ', '.join(link_to(team.name, '../teams/%d/edit' % team.id) for team in obj.teams),
        '_lessons': lambda filler, obj: ', '.join(link_to(lesson.name, '../lessons/%d/edit' % lesson.id) for lesson in obj._lessons),
        '__base_widget_args__': {
            'headers': {8: {'sorter': False}},
            'sortList': [[6, 0], [5, 0], [3, 0]]},
    }
    __form_options__ = {
        '__omit_fields__': [
            'id', 'type', 'groups',
            'created', 'display_name',
            'password', '_password',
            'submissions', 'tutored_lessons'],
        '__field_order__': [
            'id', 'user_name', 'last_name', 'first_name',
            'email_address',
            'teams', '_lessons',
        ],
        '__field_widget_types__': {
            'user_name': twb.TextField, 'email_address': twb.TextField,
            'last_name': twb.TextField, 'first_name': twb.TextField,
        },
        '__field_widget_args__': {
            'user_name': {'help_text': u'Desired user name for login'},
            'teams': {'help_text': u'These are the teams this student belongs to',
                      'size': 10},
            '_lessons': {'help_text': u'These are the lessons this students directly belongs to '
                         '(If he belongs to a team that is already in a lesson, this can be left empty)',
                      'size': 5},
        #TODO: Make this working somehow
        '__unique__fields__': ['email_address'],
        },
    }
    __setters__ = {
        'password': ('password', set_password),
    }


class TeachersCrudController(FilteredCrudRestController):

    model = User

    __table_options__ = {
        '__omit_fields__': [
            'id', 'type', 'groups',
            'password', '_password',
            'last_name', 'first_name',
            'submissions',
            '_lessons', 'teams',
            ],
        '__field_order__': [
            'id', 'user_name',
            'display_name', 'email_address',
            'tutored_lessons',
            'created', 'new_password'],
        '__search_fields__': [
            'id', 'user_name', 'email_address',
            ('tutored_lessons', 'lesson_id')],
#        '__headers__': {
#            'new_password': u'Password',
#            'tutored_lessons': u'Lessons'},
        '__xml_fields__': ['tutored_lessons', 'email_address', 'new_password'],
        'created': lambda filler, obj: obj.created.strftime('%x %X'),
        'display_name': lambda filler, obj: obj.display_name,
        'new_password': _new_password,
        'email_address': _email_address,
        'tutored_lessons': lambda filler, obj: ', '.join(link_to(lesson.name, '../lessons/%d/edit' % lesson.id) for lesson in obj.tutored_lessons),
        '__base_widget_args__': {
            'headers': {7: {'sorter': False}},
            'sortList': [[5, 0], [3, 0]]},
    }
    __form_options__ = {
        '__omit_fields__': [
            'id', 'type', 'groups',
            'created', 'display_name',
            'password', '_password',
            'submissions',
            '_lessons', 'teams'
        ],
        '__field_order__': [
            'id', 'user_name', 'last_name', 'first_name',
            'email_address',
            'tutored_lessons',
        ],
        '__field_widget_types__': {
            'user_name': twb.TextField, 'email_address': twb.TextField,
            'last_name': twb.TextField, 'first_name': twb.TextField,
        },
        '__field_widget_args__': {
            'user_name': {'help_text': u'Desired user name for login'},
            'tutored_lessons': {'help_text': u'These are the lessons this tutor teaches',
                'size': 10},
        #TODO: Make this working somehow
        '__unique__fields__': ['email_address'],
        },
    }
    __setters__ = {
        'password': ('password', set_password),
    }

TutorsCrudController = TeachersCrudController

#--------------------------------------------------------------------------------

class EventsCrudController(FilteredCrudRestController):
    
    model = Event
    
    __table_options__ = {
        '__omit_fields__': ['id', 'description', 'teacher_id', 'password',
                            'assignments', 'lessons', 'sheets', 'news',
                           ],
        '__field_order__': ['type', '_url', 'name', 'public',
                            'start_time', 'end_time', 'teacher', 'tutors'],
        '__search_fields__': ['id', '_url', 'name', 'teacher_id'],
#        '__headers__': {'_url': 'Url'},
        '__xml_fields__': ['teacher', 'tutors'],
        'start_time': lambda filler, obj: obj.start_time.strftime('%x %X'),
        'end_time': lambda filler, obj: obj.end_time.strftime('%x %X'),
        'teacher': lambda filler, obj: link_to(obj.teacher.display_name, '../tutors/%d/edit' % obj.teacher.id),
        'tutors': lambda filler, obj: ', '.join(link_to(tutor.display_name, '../tutors/%d/edit' % tutor.id) for tutor in obj.tutors),
        '__base_widget_args__': {'sortList': [[6, 1], [5, 1]]},
        }
    __form_options__ = {
        '__hide_fields__': ['teacher'],
        '__omit_fields__': ['id', 'assignments', 'sheets', 'news', 'lessons', 'password'],
        '__field_order__': ['id', 'type', '_url', 'name', 'description',
                            'public', 'start_time', 'end_time'],
        '__field_widget_types__': {'name': twb.TextField, 'description': twt.TinyMCEWidget,
                                   '_url': twb.TextField,
                                   'type': twjc.ChosenSingleSelectField,
                                  },
        '__field_validator_types__': {'_url': PlainText, },
        '__field_widget_args__': {
                                  'type': dict(options=[('course','Course'), ('contest','Contest')],
                                      value='course', prompt_text=None, required=True),
                                  'description': {'css_class': 'span6'},
                                  'start_time': {'date_format':'%d.%m.%Y %H:%M'},
                                  'end_time': {'date_format':'%d.%m.%Y %H:%M'},
                                  '_url': {'help_text': u'Will be part of the url, has to be unique and url-safe'},
                                  'public': {'help_text': u'Make event visible for students', 'default': True},
                                  'password': {'help_text': u'Password for student self-registration. Currently not implemented'},
                                 },
        '__require_fields__': ['_url'],
        }

class LessonsCrudController(FilteredCrudRestController):
    
    model = Lesson
    
    __table_options__ = {
        '__omit_fields__': ['id', 'event_id', 'event', '_url', '_members'],
        '__field_order__': ['lesson_id', 'name', 'tutor_id',
                            'tutor', 'teams', '_students'],
        '__search_fields__': ['id', 'lesson_id', 'name', 'tutor_id', ('teams','team_id'), ('_students','student_id')],
#        '__headers__': {'_students': 'Students'},
        '__xml_fields__': ['tutor', 'teams', '_students'],
        'tutor': lambda filler, obj: link_to(obj.teacher.display_name, '%s/teachers/%d/edit'
            % (filler.path_prefix, obj.teacher.id)),
        'teams': lambda filler, obj: ', '.join(link_to(team.name, '%s/teams/%d/edit'
            % (filler.path_prefix, team.id)) for team in obj.teams),
        '_students': lambda filler, obj: ', '.join(link_to(student.display_name, '%s/students/%d/edit'
            % (filler.path_prefix, student.id)) for student in obj._members),
        '__base_widget_args__': {'sortList': [[1, 0]]},
        }
    __form_options__ = {
        '__omit_fields__': ['id', '_url', 'teams', '_students'],
        '__hide_fields__': ['event'],  # If the field is omitted, it does not get validated!
        '__field_order__': ['id', 'lesson_id', 'name', 'tutor'],
        '__field_widget_types__': {'name': twb.TextField},
        '__field_widget_args__': {
                                  'lesson_id': {'label': u'Lesson Id', 'help_text': u'This id will be part of the url and has to be unique for the parent event'},
                                  'teams': {'size': 10},
                                 },
        }
    

class SheetsCrudController(FilteredCrudRestController):
    
    model = Sheet
    
    __table_options__ = {
        '__omit_fields__': ['id', 'description', 'event_id', 'event', 'teacher',
                            '_teacher', 'teacher_id', '_url', '_start_time', '_end_time'],
        '__field_order__': ['sheet_id', 'name', 'public',
                            'start_time', 'end_time', 'assignments'],
        '__search_fields__': ['id', 'sheet_id', 'name', ('assignments', 'assignment_id')],
        '__xml_fields__': ['assignments'],
        'start_time': lambda filler, obj: obj.start_time.strftime('%x %X'),
        'end_time': lambda filler, obj: obj.end_time.strftime('%x %X'),
        'assignments': lambda filler, obj: ', '.join(link_to(ass.name, '../assignments/%d/edit' % ass.id) for ass in obj.assignments),
        '__base_widget_args__': {'sortList': [[1, 0]]},
        }
    __form_options__ = {
        '__omit_fields__': ['id', '_url', 'assignments', 'teacher', '_teacher'],
        '__hide_fields__': ['event'],
        '__field_order__': ['id', 'sheet_id', 'name', 'description',
                            'public', '_start_time', '_end_time'],
        '__field_widget_types__': {
                                   'name': twb.TextField, 'description': twt.TinyMCEWidget,
                                  },
        '__field_widget_args__': {
                                  '_start_time': {'help_text': u'Leave empty to use value from event',
                                      'default': u'', 'date_format':'%d.%m.%Y %H:%M'},
                                  '_end_time': {'help_text': u'Leave empty to use value from event',
                                      'default': u'', 'date_format':'%d.%m.%Y %H:%M'},
                                  'description': {'css_class': 'span6'},
                                  #'description':{'mce_options': mce_options_default},
                                  'sheet_id': {'label': u'Sheet Id', 'help_text': u'This id will be part of the url and has to be unique for the parent event'},
                                  'public': {'help_text': u'Make sheet visible for students', 'default': True},
                                  #'assignments': {'size': 10},
                                 },
        '__require_fields__': ['sheet_id'],
        }

class AssignmentsCrudController(FilteredCrudRestController):
    
    model = Assignment
    
    __table_options__ = {
        '__omit_fields__': ['id', 'event_id', '_event', '_url',
                            'teacher_id', 'teacher', 'allowed_languages',
                            '_teacher', 'description', 'tests',
                            'submissions', 'show_compiler_msg',
                            '_start_time', '_end_time'],
        '__field_order__': ['sheet_id', 'sheet', 'assignment_id', 'name',
                            'public', 'start_time', 'end_time',
                            'timeout'],
        '__search_fields__': ['id', 'sheet_id', 'assignment_id', 'name'],
        '__xml_fields__': ['sheet'],
        'start_time': lambda filler, obj: obj.start_time.strftime('%x %X'),
        'end_time': lambda filler, obj: obj.end_time.strftime('%x %X'),
        'sheet': lambda filler, obj: link_to(obj.sheet.name, '../sheets/%d/edit' % obj.sheet.id),
        '__base_widget_args__': {'sortList': [[1, 0], [3, 0]]},
        }
    __form_options__ = {
        '__omit_fields__': ['id', 'tests', 'submissions', '_event', 'teacher', '_url', '_teacher'],
        '__field_order__': ['id', 'sheet', 'assignment_id', 'name', 'description',
                            'public', '_start_time', '_end_time',
                            'timeout', 'allowed_languages', 'show_compiler_msg'],
        '__field_widget_types__': {
                                   'name': twb.TextField, 'description': twt.TinyMCEWidget,
                                  },
        '__field_widget_args__': {
                                  'assignment_id': {'label': u'Assignment Id', 'help_text': u'Will be part of the url and has to be unique for the parent sheet'},
                                  'description': {'css_class': 'span6'},
                                  '_start_time': {'help_text': u'Leave empty to use value from event',
                                      'default': u'', 'date_format':'%d.%m.%Y %H:%M'},
                                  '_end_time': {'help_text': u'Leave empty to use value from event',
                                      'default': u'', 'date_format':'%d.%m.%Y %H:%M'},
                                  'timeout': {'help_text': u'Default timeout value for test cases, leave empty for no time limit'},
                                  'allowed_languages': {'size': 6},
                                  'show_compiler_msg': {'help_text': u'Show error messages or warnings from the compiler run', 'default': True},
                                  'public': {'help_text': u'Make assignment visible for students', 'default': True},
                                 },
        '__require_fields__': ['assignment_id',
                               'sheet',
                               ],
        '__base_widget_type__': twb.HorizontalForm,
        }

#--------------------------------------------------------------------------------

class TestsCrudController(FilteredCrudRestController):
    
    model = Test
    
    __table_options__ = {
        '__omit_fields__': ['input_data', 'output_data', 'input_filename', 'output_filename',
                            'ignore_case', 'ignore_returncode', 'show_partial_match',
                            'splitlines', 'split', 'comment_prefix', 'separator',
                            'parse_int', 'parse_float', 'float_precision', 'sort',
                            'user_id', 'user', 'testruns'],
        '__field_order__': ['id', 'assignment_id', 'assignment', 'visible', '_timeout', 'argv',
                            'input_type', 'output_type'],
        '__search_fields__': ['id', 'assignment_id'],
#        '__headers__': {'_timeout': 'Timeout'},
        '__xml_fields__': ['assignment'],
        'assignment': lambda filler, obj: link_to(obj.assignment.name, '../assignments/%d/edit' % obj.assignment.id),
        '__base_widget_args__': {'sortList': [[2, 0], [1, 0]]},
        }
    __form_options__ = {
        '__omit_fields__': ['id', 'testruns'],
        '__hide_fields__': ['user'],
        '__add_fields__': {
                           'docs': twb.Label('docs', text='Please read the <a href="%s">' % lurl('/docs/tests') +
                                              'Test configuration documentation</a>!', css_class='bold'),
                           'ignore_opts': twb.Label('ignore_opts', text='Output ignore options', css_class='label'),
                           'split_opts': twb.Label('split_opts', text='Output splitting options', css_class='label'),
                           'parse_opts': twb.Label('parse_opts', text='Output parsing options', css_class='label'),
                           },
        '__field_order__': ['id', 'docs', 'assignment', 'visible',
                            'input_data', 'output_data',
                            'input_type', 'output_type',
                            'input_filename', 'output_filename',
                            '_timeout', 'argv',
                            'ignore_opts',
                            'ignore_case', 'comment_prefix', 'ignore_returncode', 'show_partial_match',
                            'split_opts',
                            'splitlines', 'split', 'separator', 'sort',
                            'parse_opts',
                            'parse_int', 'parse_float', 'float_precision'],
        '__field_widget_types__': {
                                   'argv': twb.TextField,
                                   'input_filename': twb.TextField, 'output_filename': twb.TextField,
                                   'input_type': twjc.ChosenSingleSelectField,
                                   'output_type': twjc.ChosenSingleSelectField,
#                                   'input_data': FileField, 'output_data': FileField,
                                   'input_data': twb.TextArea, 'output_data': twb.TextArea,
                                  },
        '__field_widget_args__': {
                                  'argv': {'help_text': u'''
Command line arguments

Possible variables are:
    {path}: Absolute path to temporary working directory
    {infile}: Full path to test input file
    {outfile}: Full path to test output file
                                  '''},
                                  'visible': {'help_text': u'Whether test is shown to users or not', 'default': True},
                                  '_timeout': {'help_text': u'Timeout value, leave empty to use value from assignment'},
                                  'input_type': dict(options=[('stdin','stdin'), ('file','file')], value='stdin', prompt_text=None),
                                  'output_type': dict(options=[('stdout','stdout'), ('file','file')], value='stdout', prompt_text=None),
#                                  'input_data': dict(help_text=u'Warning, this field always overwrites database entries'),
#                                  'output_data': dict(help_text=u'Warning, this field always overwrites database entries'),
                                  'separator': {'help_text': u'The separator string used for splitting and joining, default is None (whitespace)'},
                                  'ignore_case': {'help_text': u'Call .lower() on output before comparison', 'default': True},
                                  'ignore_returncode': {'help_text': u'Ignore test process returncode', 'default': True},
                                  'comment_prefix': {'help_text': u'Ignore all lines that start with comment_prefix',},
                                  'show_partial_match': {'help_text': u'Recognize partial match and show to user', 'default': True},
                                  'splitlines': {'help_text': u'Call .splitlines() on full output before comparison', 'default': False},
                                  'split': {'help_text': u'Call .split() on full output of output before comparison or on each line from .splitlines() if splitlines is set'},
                                  'parse_int': {'help_text': u'Parse every substring in output to int before comparison', 'default': False},
                                  'parse_float': {'help_text': u'Parse every substring in output to float before comparison', 'default': False},
                                  'float_precision': {'help_text': u'''The precision (number of decimal digits) to compare for floats'''},
                                  'sort': {'help_text': u'''Sort output and test data before comparison
Parsing is performed first, if enabled
Results depends on whether splitlines and/or split are set:
if split and splitlines:
    2-dimensional array in which only the second dimension 
    is sorted (e.g. [[3, 4], [1, 2]])
if only split or only splitlines:
    1-dimensional list is sorted by the types default comparator
    ''', 'default': False},
                                 },
        }

#--------------------------------------------------------------------------------

class NewsItemController(FilteredCrudRestController):
    
    model = NewsItem
    
    __table_options__ = {
        '__omit_fields__': ['event_id', 'user_id', 'user'],
        '__field_order__': ['id', 'date', 'subject', 'message', 'public'],
        'date': lambda filler, obj: obj.date.strftime('%x %X'),
        '__base_widget_args__': {'sortList': [[6, 0], [2, 0]]},
        }
    __form_options__ = {
        '__omit_fields__': ['id'],
        '__hide_fields__': ['user'],
        '__field_order__': ['id', 'date', 'event', 'subject', 'message', 'public'],
        '__field_widget_types__': {'subject': twb.TextField},
        '__field_widget_args__': {'date': {'date_format': '%d.%m.%Y %H:%M'},
                                  'event': {'help_text': u'If an event is set, the NewsItem will be shown on the event page; '
                                            'if no event is set, the NewsItem is shown on the news page'},
                                  },
        }
