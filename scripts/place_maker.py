from __future__ import print_function

from Acquisition import aq_parent
import argparse
import json
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


RX_SPACE = re.compile(r'[^\w\s]')
RX_UNDERSCORE = re.compile(r'\_')
FALLBACK_IDS = {
    'City wall of Dura-Europos': '15685985'  # production
}


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
        for k, v in name.items():
            if k in ['title']:
                continue
            populate_field(name_obj, k, v)
        set_attribution(name_obj, args)


def populate_locations(place_data, plone_context, args):
    dflt = ['title', 'geometry']
    for location in place_data['locations']:
        new_id = make_name_id(location['title'])
        plone_context.invokeFactory(
            'Location',
            id=new_id,
            title=location['title'],
            geometry=json.dumps(location['geometry'])
        )
        location_obj = plone_context[new_id]
        for k, v in location.items():
            if k in ['title', 'geometry']:
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
        populate_field(content, 'subject', args.subjects)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create new Pleiades places.')
    parser.add_argument('--dry-run', action='store_true', default=False,
                        dest='dry_run', help='No changes will be made.')
    parser.add_argument('--nolist', action='store_true', default=False,
                        dest='nolist', help='Do not output list of places.')
    parser.add_argument('--message', default="Editorial adjustment (batch)",
                        dest='message', help='Commit message.')
    parser.add_argument('--owner', default='admin',
                        dest='owner', help='Content owner. Defaults to "admin"')
    parser.add_argument('--groups', nargs='+', default=[],
                        dest='groups', help='Group names. Separated by spaces.')
    parser.add_argument('--creators', nargs='+', default=[],
                        dest='creators', help='Creators. Separated by spaces.')
    parser.add_argument('--contributors', default=[],
                        dest='contributors', nargs='+', help='Contributors. Separated by spaces.')
    parser.add_argument('--tags', default=[], dest='subjects', nargs='+',
                        help='Tags (subjects). Separated by spaces.')
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
            try:
                to_id = loaded_ids[connection['connection']]
            except KeyError:
                to_id = FALLBACK_IDS[connection['connection']]
                rtype = 'part_of_physical'
            else:
                rtype = connection['relationshipType']
            cnxn_id = make_name_id(connection['connection'])
            if cnxn_id in from_place.objectIds():
                raise RuntimeError(
                    'Connection id collision: {}'.format(cnxn_id))
            to_path = path_base + to_id
            to_place = site.restrictedTraverse(to_path.encode('utf-8'))
            from_place.invokeFactory('Connection', id=cnxn_id)
            cnxn_obj = from_place[cnxn_id]
            cnxn_obj.setConnection([to_place.UID()])
            cnxn_obj.setTitle(connection['connection'])
            cnxn_obj.setRelationshipType(rtype)
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

