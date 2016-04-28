import sys
from optparse import OptionParser

from pleiades.dump import dump_catalog, places_schema, getSite, spoofRequest

if __name__ == '__main__':
    # places.py --extras pleiades_wsuids=
    parser = OptionParser()
    parser.add_option(
        "-c", "--collection-path", dest="collection_path",
        help="Workspace id")
    parser.add_option(
        "-e", "--extras", dest="extras",
        help="Extra query parameters")
    parser.add_option(
        "-u", "--user", dest="user",
        help="Run script as user")

    arg_start = [i for (i, v) in enumerate(sys.argv) if '.py' in v][0]
    opts, args = parser.parse_args(sys.argv[arg_start:])

    kw = {}
    
    if opts.extras:
        for params in opts.extras.split(';'):
            k, v = params.split('=')
            kw[k] = v.split(',')

    if opts.collection_path:
        kw.update(collection_path=opts.collection_path)

    app = spoofRequest(app)
    site = getSite(app)
    
    dump_catalog(site, 'Place', places_schema, **kw)

