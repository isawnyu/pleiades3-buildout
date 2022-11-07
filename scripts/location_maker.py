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


def set_attribution(content, creators, contributors):
    if creators is not None:
        populate_field(content, 'creators', creators)
    if contributors is not None:
        populate_field(content, 'contributors', contributors)


def set_tags(content, args):
    if args.subjects:
        vals = ' '.join(args.subjects)
        if ',' in vals:
            vals = vals.split(',')
        else:
            vals = [vals]
        for val in vals:
            populate_field(content, 'subject', val)

def make_loc_id(loc_title):
    this_id = loc_title.split(',')[0].strip()
    this_id = RX_SPACE.sub('', this_id)
    this_id = RX_UNDERSCORE.sub('-', this_id)
    this_id = this_id.lower().strip()
    this_id = '-'.join(this_id.split())
    while '--' in this_id:
        this_id = this_id.replace('--', '-')
    this_id = this_id.strip('-')
    return safe_unicode(this_id)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create new Pleiades places.')
    parser.add_argument('--dry-run', action='store_true', default=False,
                        dest='dry_run', help='No changes will be made.')
    parser.add_argument('--nolist', action='store_true', default=False,
                        dest='nolist', help='Do not output list of locations.')
    parser.add_argument('--message', default="Created using the location_maker.py script from pleiades3-buildout.",
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

    new_locations = json.loads(args.file.read())

    app = spoofRequest(app)
    site = getSite(app)
    workflow = getToolByName(site, "portal_workflow")
    membership = getToolByName(site, "portal_membership")

    # create locations
    done = 0
    sys.stderr.flush()
    print('Loading {} new locations '.format(len(new_locations)))
    sys.stdout.flush()

    loaded_paths = []
    for loc_path, location in new_locations.items():
        content_type = 'Location'
        path_parts = loc_path.split("/")
        parent_path = "/".join(path_parts[:-1])
        loc_id = path_parts[-1]
        parent = site.restrictedTraverse(parent_path.encode('utf-8'))
        try:
            new_id = location['id']
        except KeyError:
            new_id = make_loc_id(location['title'])
        location_obj = make_location(location, parent, new_id)
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

        attr_args = {
            "creators": None,
            "contributors": None
        }
        for k in ["creators", "contributors"]:
            try:
                location[k]
            except KeyError:
                if args["k"]:
                    attr_args = args["k"]
        if attr_args:
            set_attribution(location_obj, **attr_args)

        location_obj.reindexObject()
        parent.reindexObject()

        done += 1
        if not args.dry_run and done % 100 == 0:
            transaction.commit()

        loaded_paths.append(loc_path)


    # ownership and group permissions
    for loc_path in loaded_paths:
        loc_obj = site.restrictedTraverse(loc_path.encode('utf-8'))
        member = membership.getMemberById(args.owner)
        user = member.getUser()
        loc_obj.changeOwnership(user, recursive=True)
        loc_obj.manage_setLocalRoles(args.owner, ["Owner",])
        for group in args.groups:
            loc_obj.manage_setLocalRoles(
                group, ['Reader', 'Editor', 'Contributor'])
        loc_obj.reindexObjectSecurity()

    if args.dry_run:
        # abandon everything we've done, leaving the ZODB unchanged
        transaction.abort()
        print('Dry run. No changes made in Plone.')
    else:
        # make all remaining changes to the database
        transaction.commit()
        print('Location creation and reindexing complete.')

    # output a list of all the locations that have been created
    if not args.nolist:
        for new_path in loaded_paths:
            print(new_path)

