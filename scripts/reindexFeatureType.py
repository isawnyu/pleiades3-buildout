import logging
import time
import transaction
from datetime import timedelta

from pleiades.dump import getSite, spoofRequest
from pleiades.policy.setuphandlers import update_rolemap
from Products.CMFCore.utils import getToolByName

BATCH_SIZE = 100

if __name__ == '__main__':
    start = time.time()
    count = 0
    app = spoofRequest(app)
    try:
        site = getSite(app)
    except AttributeError:
        if 'plone' in app.objectIds():
            site = app['plone']
        else:
            site = app['Plone']
    catalog = getToolByName(site, "portal_catalog")
    place_brains = catalog.unrestrictedSearchResults(portal_type="Place")
    print('Reindexing getFeatureType for {} Place objects'.format(
        len(place_brains)))
    for brain in place_brains:
        try:
            obj = brain._unrestrictedGetObject()
        except (AttributeError, KeyError):
            print("Could not get object for brain %s", brain.getPath())
            continue
        catalog.reindexObject(obj, idxs=['getFeatureType'], update_metadata=1)
        count += 1
        if count % BATCH_SIZE == 0:
            transaction.commit()
            print('Reindexed {} Place objects'.format(count))
    transaction.commit()
    end = time.time()
    print('Made final commit after reindexing {} Place objects in {}'.format(
        count, timedelta(seconds=end - start)
    ))
