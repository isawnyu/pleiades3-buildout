Pleiades Buildout
=================

The buildout configuration file are:

buildout.cfg
  Libraries and eggs common to development and production

devel.cfg
  Development libraries and eggs

plone336.cfg
  Versions for Plone 3.3.6

discussion.cfg
  A known good set of eggs for plone.app.discussion 1.0

versions.cfg
  Pinned versions for Pleiades

pleiades-production.cfg
  Production libraries and eggs, ZEO server and clients, nginx balancer,
  Varnish cache, and supervisor.

To install, first run

  $ buildout install zope2

Then

  $ buildout

as suggested in http://maurits.vanrees.org/weblog/archive/2010/08/fake-version-pinning.

