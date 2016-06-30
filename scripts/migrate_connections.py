import re
import sys
import transaction
from optparse import OptionParser

from zope.component import getUtility
from plone.registry.interfaces import IRegistry

from Products.CMFCore.utils import getToolByName

from pleiades.dump import getSite, spoofRequest
from pleiades.vocabularies.interfaces import IPleiadesSettings
from pleiades.vocabularies.vocabularies import get_vocabulary


if __name__ == '__main__':
    app = spoofRequest(app)
    site = getSite(app)

    catalog = getToolByName(site, "portal_catalog")
    places = catalog(portal_type='Place')

    for brain in places:
        place = brain.getObject()
        old_connections = place.getConnections()
        migrated = 0
        for connection in old_connections:
            new_id = connection.getId()
            if new_id not in place.objectIds():
                place.invokeFactory('Connection', new_id)
                place[new_id].setConnection([connection.UID()])
                place[new_id].setTitle([connection.Title()])
                place[new_id].reindexObject()
                migrated += 1
        place.setConnections([])
        place.setConnections_from([])
        place.reindexObject()
        print "Migrated {} connections for {}".format(migrated, place.Title())

    transaction.commit()
