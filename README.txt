Pleiades Buildout
=================

The buildout configuration files are:

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

Also included are a bootstrap.py script for zc.buildout==1.4.4 and a directory
of patches.

The Pleiades buildout uses a patched version of ctypes at 
http://atlantides.org/eggcarton/ctypes-1.0.2-pleiades1.tar.gz.

Pleiades package distributions are at http://atlantides.org/eggcarton/.

Building
--------

1. Clone the repo.
2. Make a Python 2.4.6 virtualenv in the repo directory.
3. Run "bin/python bootstrap.py"
4. Run "bin/buildout install zope2"
5. Run "bin/buildout"

The two-step buildout is suggested in
http://maurits.vanrees.org/weblog/archive/2010/08/fake-version-pinning.

