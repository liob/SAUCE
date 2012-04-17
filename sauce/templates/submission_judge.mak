<%inherit file="local:templates.master"/>
<%namespace file="local:templates.details" name="details" />
<%namespace file="local:templates.lists" name="lists" />

% if breadcrumbs:
  <%def name="body_class()">class="navbar_left"</%def>
% endif

<%def name="title()">
  Submission
</%def>

<h2>Submission 
% if submission and hasattr(submission, 'id'):
  ${submission.id}
% endif
</h2>

${details.submission(submission, source)}

  ${c.form(c.options, child_args=c.child_args) | n}

##% if submission.judgement:
##  ${details.judgement(submission.judgement, corrected_source, diff)}
##% endif

% if compilation:
  ${details.compilation(compilation)}
% endif

% if submission.testruns:
  ${lists.testruns(submission.testruns)}
% endif
