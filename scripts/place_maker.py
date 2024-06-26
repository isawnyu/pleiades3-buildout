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

def make_name_id(name):
    this_id = name.split(',')[0].strip()
    this_id = RX_SPACE.sub('', this_id)
    this_id = RX_UNDERSCORE.sub('-', this_id)
    this_id = this_id.lower().strip()
    this_id = '-'.join(this_id.split())
    while '--' in this_id:
        this_id = this_id.replace('--', '-')
    this_id = this_id.strip('-')
    return safe_unicode(this_id)


def populate_names(place_data, plone_context, args):
    names = []
    for name in place_data['names']:
        new_id = make_name_id(name['nameTransliterated'])
        plone_context.invokeFactory(
            'Name',
            id=new_id,
            nameTransliterated=name['nameTransliterated'],
            title=name['nameTransliterated'])
        name_obj = plone_context[new_id]
        event = name_obj.workflow_history['pleiades_entity_workflow'][0]
        event['comments'] = args.message
        if args.actor != 'admin':
            event['actor'] = args.actor
        for k, v in name.items():
            if k in ['title']:
                continue
            populate_field(name_obj, k, v)
        set_attribution(name_obj, args)

def make_location(location_data, plone_context, new_id):
    try:
        plone_context.invokeFactory(
            'Location',
            id=new_id,
            title=location_data['title'],
            geometry=json.dumps(location_data['geometry'])
        )
    except BadRequest:
        return None
    else:
        return plone_context[new_id]

def populate_locations(place_data, plone_context, args):
    i = 0
    for location in place_data['locations']:
        i += 1
        try:
            new_id = location['id']
        except KeyError:
            new_id = make_name_id(location['title'])
        location_obj = make_location(location, plone_context, new_id)
        if location_obj is None:
            new_id = '-'.join((new_id, str(i)))
            location_obj = make_location(location, plone_context, new_id)
        if location_obj is None:
            raise BadRequest('The id "{}" is invalid - it is already in use.'.format(new_id))
        event = location_obj.workflow_history['pleiades_entity_workflow'][0]
        event['comments'] = args.message
        if args.actor != 'admin':
            event['actor'] = args.actor
        for k, v in location.items():
            if k in ['title', 'geometry', 'id']:
                continue
            elif k == 'accuracy':
                val = v
                if val.startswith('/'):
                    val = val[1:]
                acc_obj = site.restrictedTraverse(val.encode('utf-8'))
                location_obj.setAccuracy([acc_obj.UID()])
            else:
                populate_field(location_obj, k, v)
        set_attribution(location_obj, args)

def populate_field(content, k, v):
    if k == 'references':
        key = 'referenceCitations'
    else:
        key = k
    field = content.getField(key)
    if field is None:
        raise RuntimeError(
            'content.getField() returned None for field '
            '"{}"'.format(k))

    if k == 'title':
        content.setTitle(v)
    elif k == 'description':
        content.setDescription(v)
    elif k == 'references':
        field.resize(len(v), content)
        content.setReferenceCitations(v)
    elif k == 'attestations':
        field.resize(len(v), content)
        content.setAttestations(v)
    elif k == 'geometry':
        val = json.dumps(v, indent=4)
        content.setGeometry(val)
    else:
        try:
            field.set(content, v)
        except ReferenceException:
            print(
                'Invalid reference on field "{}". Skipping.'.format(k))


def set_attribution(content, args):
    if args.creators:
        populate_field(content, 'creators', args.creators)
    else:
        populate_field(content, 'creators', ['admin'])
    if args.contributors:
        populate_field(content, 'contributors', args.contributors)


def set_tags(content, args):
    if args.subjects:
        vals = ' '.join(args.subjects)
        if ',' in vals:
            vals = vals.split(',')
        else:
            vals = [vals]
        for val in vals:
            populate_field(content, 'subject', val)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create new Pleiades places.')
    parser.add_argument('--dry-run', action='store_true', default=False,
                        dest='dry_run', help='No changes will be made.')
    parser.add_argument('--nolist', action='store_true', default=False,
                        dest='nolist', help='Do not output list of places.')
    parser.add_argument('--message', default="Created using the place_maker.py script from pleiades3-buildout.",
                        dest='message', help='Commit message.')
    parser.add_argument('--actor', default='admin',
                        dest='actor', help='Workflow actor. Defaults to "admin".')
    parser.add_argument('--owner', default='admin',
                        dest='owner', help='Content owner. Defaults to "admin"')
    parser.add_argument('--groups',
                        default=[],
                        dest='groups', 
                        type=lambda s: re.split(r' |,\s*', s),
                        help='Group names. Separated by spaces or commas.')
    parser.add_argument('--creators', 
                        default=[],
                        dest='creators',
                        type=lambda s: re.split(r' |,\s*', s),
                        help='Creators. Separated by spaces or commas.')
    parser.add_argument('--contributors', 
                        default=[],
                        dest='contributors', 
                        type=lambda s: re.split(r' |,\s*', s),
                        help='Contributors. Separated by spaces or commas.')
    parser.add_argument('--tags', default=[], dest='subjects', nargs='+',
                        help='Tags (subjects). Separate multiple tags with commas.')
    parser.add_argument('file', type=file, help='Path to JSON import file')
    parser.add_argument('-c', help='Optional Zope configuration file.')
    try:
        args = parser.parse_args()
    except IOError, msg:
        parser.error(str(msg))

    new_places = json.loads(args.file.read())

    app = spoofRequest(app)
    site = getSite(app)
    workflow = getToolByName(site, "portal_workflow")
    membership = getToolByName(site, "portal_membership")

    # create places and subordinate names and locations
    loaded_ids = {}
    connections_pending = {}
    done = 0
    sys.stderr.flush()
    print('Loading {} new places '.format(len(new_places)))
    sys.stdout.flush()
    for place in new_places:
        content_type = 'Place'
        path = 'places'
        content = site.restrictedTraverse(path.encode('utf-8'))
        new_id = content.generateId(prefix='')
        content.invokeFactory(
            'Place',
            id=new_id,
            title=place['title'])
        loaded_ids[place['title']] = new_id
        content = content[new_id]
        event = content.workflow_history['pleiades_entity_workflow'][0]
        event['comments'] = args.message
        if args.actor != 'admin':
            event['actor'] = args.actor
        for k, v in place.items():
            if k in ['locations', 'names', 'connections', 'title']:
                continue  # address these after the place is created in plone
            populate_field(content, k, v)
        set_attribution(content, args)
        set_tags(content, args)

        # create names
        if len(place['names']) > 0:
            populate_names(place, content, args)

        # create locations
        if len(place['locations']) > 0:
            populate_locations(place, content, args)

        # store connection info to create later
        # (we may need other places to be in plone in order to create cnxn)
        if len(place['connections']) > 0:
            connections_pending[new_id] = place['connections']
        
        content.reindexObject()

        done += 1
        if not args.dry_run and done % 100 == 0:
            transaction.commit()

    # create connections
    pprint(loaded_ids, indent=4)
    path_base = 'places/'
    done = 0
    for place_id, connections in connections_pending.items():
        from_path = path_base + place_id
        from_place = site.restrictedTraverse(from_path.encode('utf-8'))
        for connection in connections:
            connection_key = connection['connection']
            m = RX_PLACE_URI.match(connection_key)
            if m:
                to_id = m.group(1)
            else:
                try:
                    to_id = loaded_ids[connection_key]
                except KeyError:
                    m = RX_INTEGER.match(connection_key)
                    if m:
                        to_id = connection_key
                    else:
                        logger.error('Invalid connection key: "{}"'.format(connection_key))
                        continue
            to_path = path_base + to_id
            to_place = site.restrictedTraverse(to_path.encode('utf-8'))
            rtype = connection['relationshipType']
            cnxn_id = make_name_id(to_place.Title())
            if cnxn_id in from_place.objectIds():
                raise RuntimeError(
                    'Connection id collision: {}'.format(cnxn_id))
            from_place.invokeFactory('Connection', id=cnxn_id)
            cnxn_obj = from_place[cnxn_id]
            cnxn_obj.setConnection([to_place.UID()])
            cnxn_obj.setTitle(to_place.Title())
            cnxn_obj.setRelationshipType(rtype)
            event = cnxn_obj.workflow_history['pleiades_entity_workflow'][0]
            event['comments'] = args.message
            if args.actor != 'admin':
                event['actor'] = args.actor
            set_attribution(cnxn_obj, args)

            to_place.reindexObject()

        from_place.reindexObject()

        done += 1
        if not args.dry_run and done % 100 == 0:
            transaction.commit()

    # ownership and group permissions
    for title, place_id in loaded_ids.items():
        place_path = path_base + place_id
        place_obj = site.restrictedTraverse(place_path.encode('utf-8'))
        member = membership.getMemberById(args.owner)
        user = member.getUser()
        place_obj.changeOwnership(user, recursive=True)
        place_obj.manage_setLocalRoles(args.owner, ["Owner",])
        for group in args.groups:
            place_obj.manage_setLocalRoles(
                group, ['Reader', 'Editor', 'Contributor'])
        place_obj.reindexObjectSecurity()

    if args.dry_run:
        # abandon everything we've done, leaving the ZODB unchanged
        transaction.abort()
        print('Dry run. No changes made in Plone.')
    else:
        # make all remaining changes to the database
        transaction.commit()
        print('Place creation and reindexing complete.')

    # output a list of all the places that have been created
    if not args.nolist:
        for title, new_id in loaded_ids.items():
            print('"{}", "{}"'.format(
                new_id, title
            ))

