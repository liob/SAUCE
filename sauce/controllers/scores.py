# -*- coding: utf-8 -*-
"""Scores controller module"""

# turbogears imports
from tg import expose, request
#from tg import redirect, validate, flash

# third party imports
#from tg.i18n import ugettext as _
#from repoze.what import predicates

# project specific imports
from sauce.lib.base import BaseController
from sauce.model import DBSession, metadata, Submission, Assignment

reward = -1
penalty = 20

class ScoresController(BaseController):
    #Uncomment this line if your controller requires an authenticated user
    #allow_only = authorize.not_anonymous()
    
    @expose('sauce.templates.scores')
    def index(self, event_id=3):
        
        if request.student and request.student.events:
            event_id = request.student.events[-1].id
        
        submissions = DBSession.query(Submission).join(Assignment).filter(Assignment.event_id == event_id).all()
        
        students = []
        assignments = []
        
        for submission in submissions:
            if not submission.student in students:
                # Initialize student score
                submission.student.score = 0
                submission.student.count = 0
                students.append(submission.student)
            
            if submission.complete and submission.testrun:
                if submission.testrun.result:
                    if not submission.assignment in assignments:
                        # Count reward only for first correct solution
                        submission.student.score += int((submission.testrun.date - submission.assignment.start_time).seconds/60)
                        submission.student.count += 1
                        assignments.append(submission.assignment)
                else:
                    # But penalty for every uncorrect solution
                    submission.student.score += penalty
        
        # Sort students
        students = sorted(sorted(students, key=lambda student: student.score), key=lambda student: student.count, reverse=True)
        
        teams = []
        
        for student in students:
            if student.team:
                if not student.team in teams:
                    student.team.score = 0
                    student.team.count = 0
                    teams.append(student.team)
                student.team.score += student.score
                student.team.count += student.count
        
        # Sort teams
        teams = sorted(sorted(teams, key=lambda team: team.score), key=lambda team: team.count, reverse=True)
        
        return dict(page='scores', students=students, teams=teams)
