from __future__ import print_function

from Acquisition import aq_parent
import argparse
from datetime import datetime
import io
import json
from os.path import abspath, isdir, join, realpath
from pleiades.dump import getSite, spoofRequest
from plone.app.iterate.interfaces import ICheckinCheckoutPolicy
from pprint import pprint, pformat
from Products.Archetypes.exceptions import ReferenceException
from Products.CMFCore.utils import getToolByName
import random
import re
import sys
from time import sleep
import transaction
from webdav.Lockable import ResourceLockedError


OUT_INDENT = ' '*8
OUT_ERROR_PREFIX = '!'
ref_fields = [
    'access_uri',
    'bibliographic_uri',
    'citation_detail',
    'formatted_citation',
    'short_title',
    'alternate_uri',
    'other_identifier',
    'type',
    'identifier'
]
SLEEP_INTERVAL = 0.0


def outerr(what, level=0):
    out(what=what, where='stderr', level=level)


def out(what, where='stdout', level=0):
    indent = OUT_INDENT * level
    if where == 'stdout':
        print('{}{}'.format(indent, what))
    elif where == 'stderr':
        if indent >= OUT_ERROR_PREFIX:
            indent = indent[:len(OUT_ERROR_PREFIX)]
        print(
            '{}{} {}'.format(indent, OUT_ERROR_PREFIX, what),
            file=sys.stderr)

rx_place_path = re.compile(
    r'^https?://pleiades\.stoa\.org/(?P<internal>places/\d+)/?$')
rx_domain = re.compile(r'^https?://(?P<domain>[\.a-z\-]+)(:\d+)?/.*$')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Update Pleiades content.')
    parser.add_argument('--dry-run', action='store_true', default=False,
                        dest='dry_run', help='No changes will be made.')
    parser.add_argument('--workflow', choices=['publish', 'review', 'draft'],
                        default='draft', required=True,
                        help='Direct edit, or set as review or draft.')
    parser.add_argument('--message', default="Added reference (batch)",
                        help='Commit message.')
    parser.add_argument('--owner', help='Content owner. Defaults to "admin"')
    parser.add_argument('--contributors',  default=[],
                        nargs='*', help='Contributors. Separated by spaces.')
    parser.add_argument('--json_file',
                        type=file, required=True,
                        help='Path to JSON import file')
    parser.add_argument('-c', help='Optional Zope configuration file.')
    parser.add_argument('--sleep', default=SLEEP_INTERVAL, type=float,
                        help='sleep interval in seconds')
    parser.add_argument('--report_dir',
                        help='Optional report output directory')
    parser.add_argument('--limit', type=int, help='Only do this many changes.')

    try:
        args = parser.parse_args()
    except IOError, msg:
        parser.error(str(msg))

    new_place_references = json.loads(args.json_file.read())

    app = spoofRequest(app)
    site = getSite(app)

    workflow = getToolByName(site, "portal_workflow")
    membership = getToolByName(site, "portal_membership")

    if args.dry_run:
        out('This is a dry run, so nothing will be changed.')
        if args.sleep > 0.0:
            out('Sleep interval of {} is being ignored.'.format(args.sleep))
    if args.report_dir:
        report_dir = abspath(realpath(args.report_dir))
        if isdir(report_dir):
            out('Result reports will be written to {}'.format(report_dir))
        else:
            raise ValueError(
                'Specified report_dir ({}) is not a directory.'
                ''.format(report_dir))
    else:
        out('No --report_dir specified. Result reporting will be suppressed.')
    out(
        'Starting batch reference creation ({} places will have new '
        'references added).'
        ''.format(len(new_place_references)))

    change_note = args.message
    failures = {}
    successes = {}
    quantity = 0
    if args.limit:
        quantity_limit = args.limit
    else:
        quantity_limit = len(new_place_references) + 1
    for pid, place_refs in new_place_references.items():
        if quantity >= quantity_limit:
            out((
                'Quantity limit ({}) exceeded. Finishing.'
                ''.format(quantity_limit)))
            break
        quantity += 1
        out('\n{} new references for: {}'.format(len(place_refs), pid))

        # get the place
        m = rx_place_path.match(pid)
        if m is None:
            raise ValueError('Cannot parse "{}" for pid path.'.format(pid))
        pid_path = m.group('internal')
        try:
            content = site.restrictedTraverse(pid_path.encode('utf-8'))
        except (KeyError, AttributeError):
            outerr(
                'Could not find pid_path="{}". Skipping this reference.'
                ''.format(pid_path))
            failures[pid] = 'not found: "{}"'.format(pid_path)
            continue
        out(
            'Found {} with title "{}" at {}'
            ''.format(content.portal_type, content.Title(), pid),
            level=1)

        # make sure the place is already published
        status = workflow.getStatusOf("pleiades_entity_workflow", content)
        review_state = status and status.get(
            'review_state', 'unknown') or 'unknown'
        if review_state != 'published':
            outerr(
                'Unexpected workflow state: "{}." Skipping.'
                ''.format(review_state),
                level=1)
            failures[pid] = 'not published: "{}"'.format(review_state)
            continue
        else:
            print('\tPlace is currently published, as expected.')

        # make sure the place doesn't have a working copy
        # this is a crummy hack
        # we'd be better off testing for a lock on the content item and also
        # shouldn't there be some sort of explicit relationship between the
        # content item and its working copy?
        wc_path = pid_path.split('/')
        wc_path[-1] = 'copy_of_{}'.format(wc_path[-1])
        wc_path = '/'.join(wc_path)
        try:
            site.restrictedTraverse(wc_path.encode('utf-8'))
        except (KeyError, AttributeError):
            pass
        else:
            outerr(
                'There is already a working copy for this resource. '
                'Skipping.', level=1)
            failures[pid] = 'working copy exists: {}'.format(wc_path)
            continue

        # iterate through new references to make sure they are valid before
        # adding them (i.e., test to see if there is already a reference
        # to this work)
        valid = []
        for i, ref in enumerate(place_refs):
            out(
                'Handling {} of {} references: "{} {}"'
                ''.format(
                    i+1, len(place_refs), ref['short_title'],
                    ref['citation_detail']),
                level=1)
            m = rx_domain.match(ref['access_uri'])
            if m is None:
                outerr(
                    'Could not determine domain in access uri = "{}". '
                    'Skipping reference.'.format(ref['access_uri']),
                    level=1)
                failures[pid] = (
                    'malformed access_uri: "{}"'.format(ref['access_uri']))
                continue
            new_domain = m.group('domain')
            field = content.getField('referenceCitations')
            current_refs = field.get(content)
            skip = False
            for current_ref in current_refs:
                access_uri = current_ref['access_uri'].strip()
                if access_uri != '':
                    m = rx_domain.match(current_ref['access_uri'])
                    if m is None:
                        out(
                            'Warning: could not determine domain in a '
                            'reference already in the content item: "{}". '
                            'Trying simple substring matching.'
                            ''.format(access_uri), level=1)
                        if new_domain in access_uri:
                            outerr(
                                'There is already a reference to a page in '
                                'this domain. Skipping this reference.',
                                level=1)
                            skip = True
                            break
                    else:
                        this_domain = m.group('domain')
                        if this_domain == new_domain:
                            outerr(
                                'There is already an access_uri with the '
                                'desired domain: "{}". Skipping this ref.'
                                ''.format(access_uri),
                                level=1)
                            skip = True
                            break
            if skip:
                failures[pid] = (
                    'existing reference to domain: "{}"'.format(access_uri))
                outerr(
                    'There is already an existing reference to the domain '
                    '({}) involved in this reference. Skipping.'
                    ''.format(new_domain))
                continue
            out(
                'This new reference is cleared for addition; i.e., there '
                'does not appear to be any conflicting reference already in '
                'place.', level=1)
            valid.append(i)

        # add the valid references
        if len(valid) > 0:

            # check out a working copy and get a dictionary of the current
            # references
            container = aq_parent(content)
            policy = ICheckinCheckoutPolicy(content)
            working_copy = policy.checkout(container)
            out(
                'Checked out working copy: {}'
                ''.format(working_copy.absolute_url_path()), level=1)
            field = working_copy.getField('referenceCitations')
            old_values = field.getRaw(working_copy)
            values = {k: v for k, v in old_values.items() if k != 'size'}
            old_size = field.getSize(working_copy)

            # sometimes the references array field returns additional
            # values beyond its "size" that are either empty or repeats
            # kill them with fire and impunity
            if old_size < len(values):
                # print(
                #     '>>> old_size = {}; len(values) = {}'
                #     ''.format(old_size, len(values)))
                # print(
                #     '>>> initial content of values:\n\n{}'
                #     ''.format(pformat(values, indent=4)))
                out(
                    'Removing {} spurious ghost references from working copy'
                    ''.format(len(values) - old_size), level=1)
                for i in range(old_size, len(values)):
                    # print('>>> i = {}'.format(i))
                    key = (
                        'referenceCitations:{}'
                        ''.format(str(i).zfill(3)))
                    # print('>>> delete key="{}"'.format(key))
                    del values[key]
                if old_size < len(values):
                    msg = (
                        'len(values) = {} is still bigger than {}\n\n{}'
                        ''.format(
                            len(values), old_size, pformat(values, indent=4)))
                    raise RuntimeError(msg)
                # print(
                #     '>>> new content of values: \n\n{}'
                #     ''.format(pformat(values, indent=4)))

            # who knows what other madness might lurk in the hearts of Plones
            if old_size > len(values):
                raise RuntimeError(
                    'size mismatch: old_size={} but len(values)={}'
                    ''.format(old_size, len(values)))

            # add new, valid references to the references dictionary
            for i, ref in enumerate(place_refs):
                if i in valid:
                    this_ref = dict(ref)
                    for f in ref_fields:
                        try:
                            this_ref[f]
                        except KeyError:
                            if f == 'type':
                                this_ref[f] = 'seeFurther'
                            else:
                                this_ref[f] = ''
                        else:
                            this_ref[f] = ref[f]
                    key = (
                        'referenceCitations:{}'
                        ''.format(str(len(values)).zfill(3)))
                    values[key] = this_ref
            if len(values) > old_size + len(valid):
                raise RuntimeError('values is huge: {}'.format(len(values)))

            # replace the values in the working copy's references ArrayField
            # with the dictionary copy we're manipulating
            field.resize(len(values), working_copy)
            working_copy.update(referenceCitations=values)
            out(
                'Added {} references to working copy (there were originally '
                '{} references, now there are {}).'
                ''.format(len(values)-old_size, old_size, len(values)),
                level=1)

            # make additional modifications to the working copy as specified
            # on the command line
            if args.contributors:
                old_contributors = list(working_copy.Contributors())
                contributors = list(old_contributors)
                for contributor in args.contributors:
                    contributors.append(contributor)
                contributors = list(set(contributors))
                contributors = [
                    (c, membership.getMemberById(c))
                    for c in contributors]
                sortable = []
                for member_id, member_data in contributors:
                    if member_data is None:
                        name_parts = member_id.lower().split()
                    else:
                        full_name = member_data.getProperty('fullname').lower()
                        name_parts = full_name.split()
                    if len(name_parts) == 1:
                        sortable.append((member_id, name_parts[0], ''))
                    elif len(name_parts) == 2:
                        sortable.append(
                            (member_id, name_parts[1], name_parts[0]))
                    elif len(name_parts) == 3:
                        sortable.append(
                            (member_id, '{} {}'.format(name_parts[1],
                             name_parts[2]), name_parts[0]))
                    elif len(name_parts) == 4:
                        sortable.append(
                            (member_id, '{} {}'.format(name_parts[2],
                             name_parts[3]), '{} {}'.format(name_parts[0],
                             name_parts[1])))
                    else:
                        sortable.append(
                            (member_id, ' '.join(
                                name_parts[1:]), name_parts[0]))
                sortable.sort(key=lambda c: c[2])
                sortable.sort(key=lambda c: c[1])
                contributors = [c[0] for c in sortable]
                working_copy.setContributors(contributors)
                delta = [c for c in contributors if c not in old_contributors]
                out(
                    'Set contributors to {} (added {}).'
                    ''.format(contributors, delta), level=1)
            if args.owner:
                member = membership.getMemberById(args.owner)
                user = member.getUser()
                working_copy.changeOwnership(user, recursive=False)
                working_copy.manage_setLocalRoles(args.owner, ['Owner'])
                working_copy.reindexObjectSecurity()
                out('Set owner to {}'.format(args.owner),
                    level=1)

            # handle working copy workflow transitions as specified on the
            # command line
            if args.workflow == 'review':
                workflow.doActionFor(
                    working_copy, 'submit', comment=change_note)
                out('Set workflow state to review.',
                    level=1)
            elif args.workflow == 'publish':
                policy = ICheckinCheckoutPolicy(working_copy)
                policy.checkin(change_note)
                out('Checked in working copy.',
                    level=1)

            if not args.dry_run:
                transaction.commit()
                if args.sleep > 0.0 or SLEEP_INTERVAL > 0.0:
                    if quantity % 100 == 0:
                        interval = max(args.sleep, SLEEP_INTERVAL) * 10.0
                        if interval > 0.0:
                            out('Sleeping for {} seconds'.format(interval))
                            sleep(interval)
                            out('Awake!')
                    else:
                        interval = random.uniform(0.0, args.sleep)
                        if interval > 0.0:
                            out('Sleeping for {} seconds'.format(interval))
                            sleep(interval)
                            out('Awake!')

            successes[pid] = {
                'new_references': [
                    ref for i, ref in enumerate(place_refs) if i in valid],
            }
            if args.contributors:
                successes[pid]['new_contributors'] = delta
            if args.owner:
                successes[pid]['new_owner'] = args.owner
            if args.workflow == 'publish':
                successes[pid]['status'] = 'checked in working copy'
            else:
                successes[pid]['status'] = (
                    'working copy moved to {} status'.format(args.workflow))
                successes[pid]['working_copy'] = wc_path

    if args.report_dir:
        success_path = join(report_dir, 'successes.json')
        with io.open(success_path, 'w', encoding='utf-8') as f:
            data = json.dumps(
                successes, f, indent=4, ensure_ascii=False, sort_keys=True)
            f.write(unicode(data))
        del f
        out('wrote {}'.format(success_path))
        failure_path = join(report_dir, 'failures.json')
        with io.open(failure_path, 'w', encoding='utf-8') as f:
            data = json.dumps(
                failures, f, indent=4, ensure_ascii=False, sort_keys=True)
            f.write(unicode(data))
        del f
        out('wrote {}'.format(failure_path))


