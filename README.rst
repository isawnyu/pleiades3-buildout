Pleiades Buildout
=================

The buildout configuration files are:

buildout.cfg
  Libraries and eggs common to development and production

versions.cfg
  Pinned versions for Pleiades

devel.cfg
  Buildout for development

pleiades-production.cfg
  Buildout for Pleiades production server,
  including ZEO, nginx, varnish, & supervisor.

Pleiades package distributions are fetched from http://atlantides.org/eggcarton/.


Installation
------------

1. Clone the repo.
2. Run "virtualenv-2.7 --no-setuptools ." in the repo directory.
3. Run "bin/python bootstrap.py"
4. Run "bin/buildout -c devel.cfg"
5. Start Zope instance in foreground with "bin/instance fg"
6. Go to http://localhost:9080/manage
7. Click Add Plone Site and create a Plone site named `plone`
   including the `Pleiades Site Policy` and `Pleiades Theme` add-ons.
