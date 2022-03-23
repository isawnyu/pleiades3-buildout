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
2. Clone this buildout repo from the HTTPS or SSH links at https://github.com/isawnyu/pleiades3-buildout
3. Create a Python 2.7 virtual environment and activate it
4. In the clone, make sure you have checked out the `master` branch
5. Run "python bootstrap.py --setuptools-version=42.0.2 --buildout-version=2.13.4"
   (These versions should match what you find in versions.cfg; update this instruction if they don't!)
6. Run "bin/buildout -c devel.cfg"
7. An admin user is created by default. If you need to create an additional login with admin powers, do: ``bin/instance adduser <name> <password>``
8. Start Zope instance in foreground with "bin/instance fg"
9. Go to http://localhost:9080
10. Authenticate with an administrative user account
11. Click Add Plone Site and create a Plone site named `plone` 
12. Include the `Pleiades Site Policy` and `Pleiades Theme` add-ons.

As an alternative to creating an empty site, you may want to `scp` the Data.fs.old (it is big)
and blobs (they are minimal) from the staging server.
