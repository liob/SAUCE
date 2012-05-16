# -*- coding: utf-8 -*-
"""The base Controller API.

@author: moschlar
"""

import logging

from tg import TGController, tmpl_context as c, url
from tg.render import render
from tg import request
from tg.i18n import ugettext as _, ungettext
import sauce.model as model
from sauce.lib.helpers import link, link_to

log = logging.getLogger(__name__)

__all__ = ['BaseController']

class BaseController(TGController):
    """
    Base class for the controllers in the application.

    Your web application should have one of these. The root of
    your application is used to compute URLs used by your app.

    """

    def __call__(self, environ, start_response):
        """Invoke the Controller"""
        # TGController.__call__ dispatches to the Controller method
        # the request is routed to. This routing information is
        # available in environ['pylons.routes_dict']

        # Fill tmpl_context with user data for convenience
        request.identity = c.identity = environ.get('repoze.who.identity')
        
        try:
            request.user = request.identity.get('user')
        except:
            request.user = None
        finally:
            try:
                request.permissions = request.identity.get('permissions')
            except AttributeError:
                request.permissions = []
            request.student = None
            request.teacher = None
            if isinstance(request.user, model.Student):
                request.student = request.user
            elif isinstance(request.user, model.Teacher):
                request.teacher = request.user
            c.user = request.user
            c.student = request.student
            c.teacher = request.teacher
        
        # Initialize other tmpl_context variables
        c.breadcrumbs = []
        c.navigation = []
        
        return TGController.__call__(self, environ, start_response)

def do_navigation_links(event):
    '''Build list of links for event administration navigation'''
    
    nav = []
    
    if request.teacher == event.teacher or 'manage' in request.permissions:
        sub = [link(u'Event %s: %s' % (event._url, event.name), event.url + '/admin')]
        sub.append(link(u'Administration', event.url + '/admin'))
        sub.append(link(u'eMail to Students', 'mailto:%s?subject=[SAUCE]'
                        % (','.join('%s' % (s.email_address) for s in event.students)),
                        onclick='return confirm("This will send an eMail to %d people. Are you sure?")' % (len(event.students))
                        ))
        nav.append(sub)
    for lesson in event.lessons:
        if request.teacher == lesson.teacher or request.teacher == event.teacher or 'manage' in request.permissions:
            sub = [link(u'Lesson %d: %s' % (lesson.lesson_id, lesson.name), event.url+'/lessons/%d' % (lesson.lesson_id))]
            sub.append(link(u'Administration', event.url+'/lessons/%d' % (lesson.lesson_id)))
            sub.append(link(u'Submissions', event.url+'/lessons/%d/submissions' % (lesson.lesson_id)))
            sub.append(link(u'eMail to Students', 'mailto:%s?subject=[SAUCE]'
                            % (','.join('%s' % (s.email_address) for s in lesson.students)),
                            onclick='return confirm("This will send an eMail to %d people. Are you sure?")' % (len(lesson.students))
                            ))
            nav.append(sub)
    
    return nav
