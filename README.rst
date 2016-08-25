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

1. Install the libgeos prerequisite. (On OSX, this can be done with homebrew; the recipe is called "geos")
2. Clone the repos
3. Create a Python 2.7 virtual environment and activate it
4. In the clone, checkout the jazkarta-plone4 branch
5. Run "bin/python bootstrap.py"
6. Run "bin/buildout -c devel.cfg"
7. An admin user is created by default. If you need to create an additional  login with admin powers, do: bin/instance adduser <name> <password>
6. Start Zope instance in foreground with "bin/instance fg"
7. Go to http://localhost:9080
8. Authenticate with an administrative user account
9. Click Add Plone Site and create a Plone site named `plone`
   including the `Pleiades Site Policy` and `Pleiades Theme` add-ons.
