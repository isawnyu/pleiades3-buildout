from __future__ import print_function

from Acquisition import aq_parent
import argparse
import json
import logging
from pleiades.dump import getSite, spoofRequest
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
from zExceptions import BadRequest

logger = logging.getLogger(__name__)

RX_SPACE = re.compile(r'[^\w\s]')
RX_UNDERSCORE = re.compile(r'\_')
RX_PLACE_URI = re.compile(r'^https://pleiades\.stoa\.org/places/(\d+)$')
RX_INTEGER = re.compile(r'^\d+$')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create new Pleiades places.')
    parser.add_argument('--dry-run', action='store_true', default=False,
                        dest='dry_run', help='No changes will be made.')
    parser.add_argument('--message', default="Workflow modified using the state_changer.py script from pleiades3-buildout.",
                        dest='message', help='Commit message.')
    parser.add_argument('--actor', default='admin',
                        dest='actor', help='Workflow actor. Defaults to "admin".')
    parser.add_argument('--state', default='published', dest='state', help='Desired end state. Defaults to "published".')
    parser.add_argument('--contents', dest='contents', default=False, action='store_true', help='include contents in transition? Defaults to False.')
    parser.add_argument('file', type=file, help='Path to file containing list of URIs to modify')
    parser.add_argument('-c', help='Optional Zope configuration file.')

    try:
        args = parser.parse_args()
    except IOError, msg:
        parser.error(str(msg))

    target_ids = args.file.readlines()  # expects a simple sequence of paths or uris; one per line
    target_ids = [tid.strip() for tid in target_ids]

    app = spoofRequest(app)
    site = getSite(app)
    workflow = getToolByName(site, "portal_workflow")
    membership = getToolByName(site, "portal_membership")

    done = 0
    states = ['drafting', 'pending', 'published']
    transitions = ['retract', 'submit', 'publish']
    for target in target_ids:
        
        path = target.replace('https://pleiades.stoa.org/', '')
        while path.startswith('/'):
            path = path[1:]
        
        try:
            content = site.restrictedTraverse(path.encode('utf-8'))
        except (KeyError, AttributeError):
            logger.error('Path not found: ' + path)
            sys.stderr.flush()
            continue

        status = workflow.getStatusOf("pleiades_entity_workflow", content)
        if status['review_state'] != args.state:
            while status['review_state'] != args.state:
                if args.state == 'drafting':
                    j = 0
                else:
                    j = states.index(status['review_state']) + 1
                workflow.doActionFor(content, transitions[j], comment=args.message)
                status = workflow.getStatusOf("pleiades_entity_workflow", content)
            content.reindexObject()
        state = status['review_state']
        if args.contents:
            for child in content.objectValues():
                child_path = '/'.join(child.getPhysicalPath()[2:])
                status = workflow.getStatusOf("pleiades_entity_workflow", child)
                if status['review_state'] != args.state:
                    while status['review_state'] != args.state:
                        if args.state == 'drafting':
                            j = 0
                        else:
                            j = states.index(status['review_state']) + 1
                        workflow.doActionFor(child, transitions[j], comment=args.message)
                        status = workflow.getStatusOf("pleiades_entity_workflow", child)
                    child.reindexObject()

        print(path + ', ' + state)
        for child in content.objectValues():
            child_state = workflow.getStatusOf("pleiades_entity_workflow", child)['review_state']
            child_path = '/'.join(child.getPhysicalPath()[2:])
            print(child_path + ', ' + child_state)

        done += 1
        if not args.dry_run and done % 100 == 0:
            transaction.commit()

    if args.dry_run:
        # abandon everything we've done, leaving the ZODB unchanged
        transaction.abort()
        print('Dry run. No changes made in Plone.')
    else:
        # make all remaining changes to the database
        transaction.commit()
        print('Workflow state changes and reindexing complete.')

