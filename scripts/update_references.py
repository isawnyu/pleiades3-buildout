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
        obj = brain.getObject()
        for fname in FNAMES:
            field = obj.getField(fname, None)
            if field is None:
                continue
            refs = field.get(obj)
            all_refs = len(refs)
            for entry in refs:
                identifier = entry.get('identifier')
                if validation.validate('isURL', identifier) != 1:
                    continue
                if (entry.get('bibliographic_uri').strip() or
                        entry.get('access_uri').strip()):
                    continue
                for site_name in BIB_SITES:
                    if site_name in identifier:
                        entry['bibliographic_uri'] = identifier
                        break
                else:
                    entry['access_uri'] = identifier
                migrated += 1
            if migrated:
                field.set(obj, refs)
        print "Migrated {} references of {} for {}".format(
            migrated, all_refs, brain.getPath())
        total += 1
        if total % TRANSACTION_COUNT == 0:
            transaction.commit()
            p_jar.cacheMinimize()

    transaction.commit()
    print "Migrated references for {} objects.".format(total)
