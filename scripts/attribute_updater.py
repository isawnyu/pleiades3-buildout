from __future__ import print_function

from Acquisition import aq_parent
import argparse
import json
import logging
from pleiades.dump import getSite, spoofRequest
from plone.app.iterate.interfaces import ICheckinCheckoutPolicy
from pprint import pprint
from Products.Archetypes.exceptions import ReferenceException
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import safe_unicode
from Products.PleiadesEntity.content.interfaces import IWork
from Products.validation import validation
import re
import string
import sys
import transaction

logger = logging.getLogger('attribute updater')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Update attributes on Pleiades content.')
    parser.add_argument('--dry-run', action='store_true', default=False,
                        dest='dry_run', help='No changes will be made.')
    parser.add_argument('--message', default="Editorial adjustment (batch)",
                        dest='message', help='Commit message.')
    parser.add_argument('--owner', help='Content owner. Defaults to "admin"')
    parser.add_argument('file', type=file, help='Path to JSON import file')
    parser.add_argument('-c', help='Optional Zope configuration file.')
    parser.add_argument('--limit', default=0, dest='limit', help='limit changes')
    try:
        args = parser.parse_args()
    except IOError, msg:
        parser.error(str(msg))

    updates = json.loads(args.file.read())

    app = spoofRequest(app)
    site = getSite(app)
    workflow = getToolByName(site, "portal_workflow")
    membership = getToolByName(site, "portal_membership")
    repository = getToolByName(site, "portal_repository")

    total = 0
    limit = int(args.limit)
    done = []
    for oid, changes in updates.items():
        print('Changing {}'.format(oid))
        total += 1
        opath = 'places/{}'.format(oid)
        obj = site.restrictedTraverse(opath.encode('utf-8'))
        for attr, value in changes.items():
            field = obj.getField(attr)
            old_values = field.getRaw(obj)
            field.set(obj, value)
        repository.save(obj, args.message)
        obj.reindexObject()
        done.append(opath)
        if not args.dry_run:
            if total % 100 == 0:
                transaction.commit()
        if total == limit:
            logger.warning(
                'Hit change limit={}. Discarding remaining changes.'
                ''.format(args.limit))
            break

    if args.dry_run:
        # abandon everything we've done, leaving the ZODB unchanged
        transaction.abort()
        print('Dry run. No changes made in Plone.')
    else:
        # make all remaining changes to the database
        transaction.commit()
        print('Updates complete.')
        for opath in done:
            print(opath)
