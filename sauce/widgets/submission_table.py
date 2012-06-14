'''
Created on 14.04.2012

@author: moschlar
'''

import logging
from random import choice

from tg import request, flash, url

from tgext.crud.utils import SortableTableBase
from sprox.formbase import AddRecordForm, EditableForm, Field
from sprox.tablebase import TableBase
from sprox.fillerbase import TableFiller
#from sprox.dojo.formbase import DojoAddRecordForm # renders TableForm to ugly at the moment, Issue #9

from sauce.model import DBSession, Event, Lesson, Sheet, Assignment, Test, Submission, Student, Team, User
from sauce.lib.helpers import cut, link
from sqlalchemy.sql.expression import desc as _desc

from sauce.widgets.datagrid import JSSortableDataGrid
from webhelpers.html import literal

log = logging.getLogger(__name__)


def _actions(filler, subm):
    result = [u'<a href="%s/show" class="btn btn-mini" title="Show">'
        '<i class="icon-eye-open"></i></a>' % (subm.url)]
    if (subm.assignment.is_active
        and hasattr(request, 'user') and request.user == subm.user):
        result.append(u'<a href="%s/edit" class="btn btn-mini" title="Edit">'
            '<i class="icon-pencil"></i></a>' % (subm.url))
    if hasattr(request, 'teacher') and request.teacher:
        result.append(u'<a href="%s/judge" class="btn btn-mini" title="Judge">'
            '<i class="icon-tag"></i></a>' % (subm.url))
    return literal('<div class="btn-group" style="width: %dpx;">'
        % (len(result)*30) + ''.join(result) + '</div>')


class SubmissionTable(TableBase):
    __model__ = Submission
    __omit_fields__ = ['source', 'assignment_id', 'language_id', 'user_id',
                       'testruns', 'filename', 'complete']
    __field_order__ = ['id', 'user', 'assignment', 'language', 'created',
        'modified', 'result', 'judgement', 'grade']
    __add_fields__ = {'result': None, 'grade': None}
    __base_widget_type__ = JSSortableDataGrid
    __base_widget_args__ = {'sortList': [[3, 0], [7, 1]]}


class SubmissionTableFiller(TableFiller):
    __model__ = Submission
    __omit_fields__ = ['source', 'assignment_id', 'language_id', 'user_id',
                       'testruns', 'filename', 'complete']
    __add_fields__ = {'result': None, 'grade': None}
    __actions__ = _actions

    def assignment(self, obj):
        try:
            return obj.assignment.link
        except AttributeError:
            log.warn('Submission %d has no assignment', obj.id)
            return u'<span class="label label-inverse">None</a>'

    def user(self, obj):
        try:
            if obj.user == request.user:
                return u'<em>%s</em>' % obj.user.display_name
            else:
                return obj.user.display_name
        except AttributeError:
            log.warn('Submission %d has no user', obj.id)
            return u'<span class="label label-inverse">None</a>'

    def result(self, obj):
        if obj.result is not None:
            if obj.result:
                return u'<span class="label label-success">Success</a>'
            else:
                return u'<span class="label label-important">Failed</a>'
        else:
            return u'<span class="label">None</a>'

    def judgement(self, obj):
        if obj.judgement:
            return u'<a href="%s/judge" class="label label-info">Yes</a>' % (obj.url)
        else:
            return u'<a href="%s/judge" class="label">No</a>' % (obj.url)

    def grade(self, obj):
        if obj.judgement and obj.judgement.grade is not None:
            return u'<span class="badge badge-info">%s</span>' % unicode(obj.judgement.grade)
        else:
            return u''

    def created(self, obj):
        return obj.created.strftime('%x %X')

    def modified(self, obj):
        return obj.modified.strftime('%x %X')

    def __init__(self, *args, **kw):
        self.lesson = kw.pop('lesson', None)
        super(SubmissionTableFiller, self).__init__(*args, **kw)

    def _do_get_provider_count_and_objs(self, **kw):
        '''Custom getter function respecting lesson
        
        Returns the result count from the database and a query object
        '''
        
        qry = Submission.query
        
        # Process lesson filter
        if self.lesson:
            #TODO: This query in sql
            qry = qry.join(Submission.user).filter(User.id.in_((s.id for s in self.lesson.students)))
        
        # Process filters from url
        kwfilters = kw
        exc = False
        try:
            kwfilters = self.__provider__._modify_params_for_dates(self.__model__, kwfilters)
        except ValueError as e:
            log.info('Could not parse date filters', exc_info=True)
            flash('Could not parse date filters: %s.' % e.message, 'error')
            exc = True
        
        try:
            kwfilters = self.__provider__._modify_params_for_relationships(self.__model__, kwfilters)
        except (ValueError, AttributeError) as e:
            log.info('Could not parse relationship filters', exc_info=True)
            flash('Could not parse relationship filters: %s. '
                  'You can only filter by the IDs of relationships, not by their names.' % e.message, 'error')
            exc = True
        if exc:
            # Since non-parsed kwfilters are bad, we just have to ignore them now
            kwfilters = {}
        
        for field_name, value in kwfilters.iteritems():
            field = getattr(self.__model__, field_name)
            try:
                if self.__provider__.is_relation(self.__model__, field_name) and isinstance(value, list):
                    value = value[0]
                    qry = qry.filter(field.contains(value))
                else: 
                    qry = qry.filter(field==value)
            except:
                log.warn('Could not create filter on query', exc_info=True)
        
        # Get total count
        count = qry.count()
        
        return count, qry
