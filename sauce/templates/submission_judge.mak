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

<%inherit file="local:templates.submission" />
<%namespace file="local:templates.submission" import="details" />

## TODO: Make full=false work with correct line numbers
${details(submission, full=False)}

<h2>Judgement</h2>
${c.judgement_form.display(options) | n}

##TODO: Show corrected source code results
##% if compilation:
##  ${details.compilation(compilation)}
##% endif

##% if submission.testruns:
##  ${lists.testruns(submission.testruns)}
##% endif

