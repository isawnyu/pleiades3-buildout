import logging
import transaction

from pleiades.dump import getSite, spoofRequest
from pleiades.policy.setuphandlers import update_rolemap
from Products.CMFPlone.log import log


if __name__ == '__main__':
    app = spoofRequest(app)
    try:
        site = getSite(app)
    except AttributeError:
        if 'plone' in app.objectIds():
            site = app['plone']
        else:
            site = app['Plone']
    update_rolemap(site)
    transaction.commit()
    log('Made final commit', severity=logging.WARNING)
