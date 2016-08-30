import transaction

from Products.CMFCore.utils import getToolByName
from Products.PleiadesEntity.content.interfaces import IWork
from Products.validation import validation

from pleiades.dump import getSite, spoofRequest


FNAMES = ('referenceCitations', 'primaryReferenceCitations')
BIB_SITES = ('worldcat.org', 'atlantides.org', 'openlibrary.org', 'zotero.org')
TRANSACTION_COUNT = 100

if __name__ == '__main__':
    app = spoofRequest(app)
    site = getSite(app)
    p_jar = site._p_jar

    catalog = getToolByName(site, "portal_catalog")
    brains = catalog(object_provides=IWork.__identifier__)

    total = 0
    for brain in brains:
        migrated = 0
        all_refs = 0
        obj = brain.getObject()
        for fname in FNAMES:
            field = obj.getField(fname, None)
            if field is None:
                continue
            refs = field.getRaw(obj)
            all_refs += len(refs)
            updated_refs = []
            for key in refs.keys():
                if key == 'size':
                    continue
                entry = refs[key]
                updated_refs.append(entry)
                if entry.get('range'):
                    entry['formatted_citation'] = entry['range']
                    del entry['range']
                    migrated += 1
                elif not entry.get('formatted_citation'):
                    entry['formatted_citation'] = getattr(
                        obj, '%s|%s|range' % (fname, key), ''
                    )
                    print("Updated citation for {} to '{}' using {}".format(
                        '/'.join(obj.getPhysicalPath()),
                        entry['formatted_citation'],
                        '%s|%s|range' % (fname, key)))
                    migrated += 1

                identifier = entry.get('identifier', '')
                if validation.validate('isURL', identifier) != 1:
                    entry['identifier'] = identifier.strip()
                    continue
                if not identifier.strip():
                    entry['identifier'] = ''
                    continue

                if (entry.get('bibliographic_uri', '').strip() or
                        entry.get('access_uri', '').strip()):
                    migrated += 1
                    continue

                for site_name in BIB_SITES:
                    if site_name in identifier:
                        entry['bibliographic_uri'] = identifier
                        break
                else:
                    entry['access_uri'] = identifier

                entry['identifier'] = ''
                migrated += 1

            if migrated and updated_refs:
                field.set(obj, updated_refs)
        total += 1
        if total % TRANSACTION_COUNT == 0:
            transaction.commit()
            p_jar.cacheMinimize()

    transaction.commit()
    print "Migrated references for {} objects.".format(total)
