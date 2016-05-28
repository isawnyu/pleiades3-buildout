import re
import sys
import transaction
from optparse import OptionParser

from zope.component import getUtility
from plone.registry.interfaces import IRegistry

from Products.CMFCore.utils import getToolByName

from pleiades.dump import getSite, spoofRequest
from pleiades.vocabularies.interfaces import IPleiadesSettings
from pleiades.vocabularies.vocabularies import get_vocabulary


if __name__ == '__main__':
    app = spoofRequest(app)
    site = getSite(app)

    vocabularies = site['vocabularies']
    to_migrate = vocabularies['time-periods']

    wf_tool = getToolByName(site, "portal_workflow")
    registry = getUtility(IRegistry)
    settings = registry.forInterface(IPleiadesSettings, False)

    new_terms = []
    for term in to_migrate.objectValues():
        id = term.id
        title = term.Title()
        desc = term.Description()
        min = None
        max = None
        m = re.search(
            r"\[\[(-{0,1}\d*\.{0,1}\d*)\s*,\s*(-{0,1}\d*\.{0,1}\d*)\]\]",
            desc)
        if m is not None:
            min = int(m.group(1))
            max = int(m.group(2))
        state = wf_tool.getInfoFor(term, 'review_state', '')
        hidden = state != 'published' and state != 'drafting'
        new_terms.append(dict(id=unicode(id),
                                title=title.decode('utf-8'),
                                description=desc.decode('utf-8'),
                                lower_bound=min,
                                upper_bound=max,
                                same_as=None,
                                hidden=hidden))
        print id, title, desc, min, max, hidden
    settings.time_periods = new_terms
    transaction.commit()
