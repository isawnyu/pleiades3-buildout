import transaction
import argparse

from Products.CMFCore.utils import getToolByName

from pleiades.dump import getSite, spoofRequest


if __name__ == '__main__':
    app = spoofRequest(app)
    site = getSite(app)

    catalog = getToolByName(site, "portal_catalog")
    places = catalog(portal_type='Place')

    total = 0
    for brain in places:
        refs = brain.connectsWith
        brefs = brain.hasConnectionsWith
        for oid in (refs + brefs):
            if len(oid) == 32:
                break
        else:
            # Clean refs
            continue
        place = brain.getObject()
        # Provide a simple single index to speed things up
        catalog.reindexObject(place, idxs=['getNameAttested'],
                              update_metadata=1)
        total += 1
        if total % 100 == 0:
            transaction.commit()
            print "Migrating ... {} connections".format(total)

    transaction.commit()
    print "Migrated {} total connections.".format(total)
