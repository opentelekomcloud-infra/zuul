:title: About Zuul

.. _about-zuul:

About Zuul
==========

Zuul is a Project Gating System. That’s like a CI or CD system, but
the focus is on testing the future state of code repositories.

A gating system doesn’t just test a proposed change; it tests the proposed
future state of multiple branches and repositories with any number of
in-flight changes and their dependencies. And the same playbooks used to
test software can also be used to deploy it.

How Zuul Works
--------------
Zuul operates as a service that:
* Listens for events from supported code-review systems
* Schedules and executes jobs based on those events
* Reports the results back to the code-review platform

The primary developer interface is the code-review system (or systems) itself, 
integrating seamlessly into existing workflows. In addition, Zuul provides
a web interface for monitoring pipeline activity, viewing build details,
and understanding job results.

Multi-Tenant Architecture
-------------------------
Zuul is designed to be deployed as a single shared installation that can
serve multiple projects, teams, or organizations. Its multi-tenant
capabilities allow you to define:
* Strong isolation between projects, if required
* Shared resources and pipelines where appropriate

Integration with Code-Review Systems
------------------------------------
Zuul supports a wide range of git based code review systems, and can work with
multiple systems at the same time—even enabling cross-system integration of
projects. See :ref:`drivers` section of the documentation for a complete list.

Nodepool: Resource Provisioning
-------------------------------
Zuul uses a companion component, `Nodepool`_ to provide the compute
resources to run jobs.  Nodepool works with:
* Cloud providers
* Kubernetes clusters
* Containers
* Statically defined nodes
* Mixed environments, operating simultaneously

Job Execution with Ansible
--------------------------
Because Zuul is designed from the ground up to run jobs in a multi-node environment (whether
those nodes are bare metal machines, VMs, Kubernetes clusters, or containers), Zuul’s job definition
language needs to support orchestrating tasks on multiple nodes. Zuul uses Ansible for this. Ansible
is well-known and easy to learn and use. Some existing Ansible playbooks and roles may be able to
be used directly with Zuul (but some restrictions apply, so not all will).

However, knowledge or use of Ansible is not required for Zuul – it is quite simple for Zuul’s
embedded Ansible to run any shell script or any other program. Zuul’s library of standard jobs even
includes a job that will run a specified shell script, so it’s possible to use Zuul without writing any
Ansible at all.

Open Source and Community-Driven
--------------------------------
Zuul is an open source project actively developed and maintained by a
vibrant community.  We welcome your `support and contribution
<https://zuul-ci.org/community.html>`__.

.. toctree::
   :hidden:

   concepts
   gating

_`Nodepool`: https://zuul-ci.org/docs/nodepool/
