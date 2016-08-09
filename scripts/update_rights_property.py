import transaction
from Products.CMFCore.utils import getToolByName
from pleiades.dump import getSite, spoofRequest

if __name__ == '__main__':
    app = spoofRequest(app)
    site = getSite(app)

    catalog = getToolByName(site, "portal_catalog")

    places = catalog(portal_type='Place')
    names = catalog(portal_type='Name')
    locations = catalog(portal_type='Location')
    connections = catalog(portal_type='Connection')
    
    for content_type in [places, names, locations, connections]:
        total = 0
        ct_type = content_type[0].getObject().Type().lower()
        print "===================================================="
        print "updating {}s".format(ct_type)
        print "===================================================="
        for brain in content_type:
            ct = brain.getObject()
            ct.setRights(ct.Rights()) # just resave the rights field. silly solution but works.
            total += 1
            if total % 100 == 0:
                transaction.commit()
                print "TRANSACTION COMMIT: {} {}s processed of {}".format(total, ct_type, len(content_type))

        transaction.commit()
        print "Updated the rights field of {} {} objects.".format(total, ct_type)
