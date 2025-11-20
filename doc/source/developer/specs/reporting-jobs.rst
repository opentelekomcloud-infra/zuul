Reporting Jobs
==============

.. warning:: This is not authoritative documentation.  These features
   are not currently available in Zuul.  They may change significantly
   before final implementation, or may never be fully completed.

The following document describes a new type of job designed to be run
during the reporting phase in Zuul.

Introduction
------------

Zuul uses pipelines to describe workflow operations.  Pipelines
utilize a number of concepts: triggers determine what items are
enqueued into a pipeline, jobs are run for the items in the pipeline,
and reporters send results based on the outcome of jobs.

The reporting phase is critical because in a "gate" pipeline (which is
Zuul's main purpose) one of the reporters is responsible for actually
causing the change being tested to merge.  It executes the atomic
state transition which changes Zuul's speculative future state into
the actual present state.  Originally, and still typically, the only
thing that changes in that instant is the merging of a single commit
into a single repository.  But there are some exceptions.

With circular dependencies, multiple commits may be merged during the
reporting phase of a single item.  To accomplish this, Zuul attempts
to leave feedback on all the changes in the cycle first, and after
completing that it then instructs the code review system(s) to merge
the changes.  It's as close to a two-phase commit as we can get
without being able to roll back.

One code review system in particular, Gerrit, can do even more during
that instant where Zuul is merging the change(s) for a queue item.
Due to Gerrit's superproject subscription feature, at the moment a
change is merged to a project, any superprojects in Gerrit (that is,
projects with .gitmodules files that reference the target project as a
submodule) may have their .gitmodules files updated to point at the
commit sha of the newly merged change.  This allows for a near atomic
update of not only the project whose change is being merged, but the
superproject that consumes it.

Users of other systems have expressed a desire for a similar behavior,
but lacking support for that behavior in the code review systems
themselves, they naturally look to Zuul as an option.  The same is
true for users of project composition systems other than git
submodules, such as the "repo" tool from Android.  The only current
option is to have an external system monitor Zuul and then perform the
update as quickly as possible.

However, this introduces a race condition that can affect Zuul itself.
Consider the following sequence:

* Change A completes testing in the gate pipeline and is merged
* External system observes the merging of change A and starts updating the superproject
* User approves change B and it is enqueued into Zuul
* Zuul performs a repo state job to fix the state of all repos for change B
* External system completes the update of the superproject

At the end of this process, Zuul may run jobs for change B with repo
states that include change A as merged into the subproject but without
the superproject being updated to account for that.

Since performing this update is a workload involving git repos, and
Zuul is quite good at running arbitrary workloads involving git repos,
this is a proposal for a new kind of Zuul job to accommodate this need.

Proposal
--------

The key to running this kind of workload is that it must happen after
the completion of the report to the code review system where the
change is merged, but before Zuul resumes processing of that pipeline.
It must be fast, because Zuul will not be able to make any changes to
the pipeline until the job is complete.

One of the main benefits of running this kind of workflow in Zuul is
that users will benefit from the logging and accessibility that Zuul
provides for all jobs.  Rather than having a critical part of the
development process happen in an external tool which may not be
visible to developers, by running it in a Zuul job, we should be able
to see the whole process as easily as we see the rest of the software
development.

To that end, the job should be included in the buildset that is
reported to the SQL database, though it will have run too late to be
included in the reports to the code review systems.  The result of the
job may still affect the result of the buildset.  If the job fails,
the buildset would switch from SUCCESS to FAILURE and the changes
behind it will reconfigure themselves just as if the merge operation
itself failed.  That will allow them to run with the most accurate
information possible, and prevent the propagation of errors to changes
further back in the queue.

Implementation
--------------

The Zuul pipeline manager will be adjusted to do the following:

* Report the change to all configured pipeline reporters
* If the buildset was successful, start any reporter jobs configured for the buildset
* Wait for those jobs to complete: this means that no processing of any items behind the head will happen until the jobs are complete
* If the buildset failed after running the reporter jobs, cancel jobs behind the head
* Record the buildset result in the SQL database
* Continue processing the pipeline

It will be recommended that users only configure reporter jobs with
empty nodesets, for speed, but it will not be a requirement.

User Interface
--------------

We will introduce a new job attribute to configure reporting jobs:

.. code-block:: yaml

   - job:
       name: update-superproject
       reporting: true

When such a job is added to a project-pipeline config, the new
behavior will be enabled.

Because this pauses Zuul's operation, we should not, by default, allow
untrusted projects to configure reporting jobs themselves (but they
can be have reporting jobs configured on them from a trusted project).
A reporting job may be added to a project-pipeline config in a project
stanza that appears in a trusted project.  Because we also allow some
untrusted projects to configure other unstrusted projects, we should
allow those to configure this behavior as well.  We will add a tenant
configuration option to allow an untrusted project to configure
reporting jobs on itself, and if it is also allowed to configure other
projects, on them as well.  For example:

.. code-block:: yaml

   - tenant:
       name: tenant-one
       source:
         gerrit:
           config-projects:
             - common-config
           untrusted-projects:
             - superproject:
                 allow-reporting-jobs: true
                 configure-projects:
                   - submodule1
                   - submodule2
             - submodule1
             - submodule2

This would allow the "superproject" project to configure reporting
jobs on itself or the "submodule1" or "submodule2" projects.  The
"common-config" project can configure reporting jobs on any project.
The "submodule1" and "submodule2" projects would not be able to
configure their own reporting jobs.

In order to limit repositories prepared by the executor, the job
definition will be updated to accept new attributes "include-projects"
and "exclude-projects":

.. code-block:: yaml

   - job:
       name: update-superproject
       reporting: true
       require-projects:
         - superproject
       include-projects:
         - superproject

This will only checkout the superproject within the update-superproject job.

Limitations
-----------

This approach addresses a race in a "gate" pipeline, but if Zuul has
other pipelines that trigger when a change is merged, there will be no
way to tell them to wait until the superproject is updated.  Users
will need to understand this limitation, or, configure such pipelines
to act on updates to the superproject only.

Alternatives
------------

The desired behavior has been prototyped using the MQTT reporter.  The
change at https://review.opendev.org/957608 updates the MQTT reporter
to optionally wait for a response.  This has enabled the evaluation of
the general principle described here.  The MQTT reporter was chosen
for this experiment because today it is the reporter of choice for
systems that react to Zuul.  However, using the MQTT reporter for this
is not ideal because it requires users to write, run, and maintain an
external service.  The results of that service are not as visible to
users as Zuul jobs are.  It also requires some difficult decisions
about timeouts since there is only a loose coupling between Zuul and
the external service over MQTT.

Another alternative would be an HTTP-based reporter.  In this case, we
could have Zuul perform an HTTP POST operation and wait for the
results.  This is a tighter coupling between Zuul and the external
service which addresses one of the shortcomings of the MQTT method.
The other shortcomings remain.

Due to the desirability of tighter integration with the buildset,
discoverability of result logs, and obviating the need to create a new
service, we elect not to pursue these alternatives.
