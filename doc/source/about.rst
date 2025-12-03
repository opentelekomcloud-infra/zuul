:title: About Zuul

.. _about-zuul:

About Zuul
==========

Zuul is a Project Gating System similar to a CI/CD system, but
with a stronger focus on validating the future state of code repositories.

Instead of only testing a proposed change, Zuul evaluates the combined
effect of multiple in-flight changes across branches and repositories, 
including their dependencies. This ensures that what is merged will work 
reliably in the integrated future environment.

Zuul models this by:
* Testing proposed changes in the context of other active changes
* Predicting the future state of repositories
* Reusing the same playbooks for both testing and deployment

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
Zuul supports a wide range of code review systems, and can work with multiple
systems at the same time—even enabling cross-system integration of 
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
Since Zuul is designed for multi-node job execution - across bare metal
machines, VMs, Kubernetes clusters, or containers - it uses Ansible as 
its job execution engine.  Ansible is widely known, easy to learn and
suitable for orchestrating complex workflows. 

While existing Ansible playbooks can often be reused, some limitations apply.
Importantly, knowledge of Ansible is not required to use Zuul. The 
standard library of jobs includes a generic job capable of simply running
shell scripts or arbitrary commands, making it fully possible to use Zuul 
without writing any Ansible at all.

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
