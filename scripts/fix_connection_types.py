import transaction
import argparse

from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import safe_unicode

from pleiades.dump import getSite, spoofRequest


if __name__ == '__main__':
    app = spoofRequest(app)
    site = getSite(app)

    catalog = getToolByName(site, "portal_catalog")
    connections = catalog(portal_type='Connection')

    total = 0
    for brain in connections:
        conn = brain.getObject()
        if isinstance(getattr(conn, 'relationshipType', None), (list, tuple)):
            conn.relationshipType = conn.relationshipType and safe_unicode(conn.relationshipType[0]) or None
            total += 1
            print "bad conneciton type {}".format(brain.getPath())

    transaction.commit()
    print "Fixed {} total connections.".format(total)
