
from optparse import OptionParser

from pleiades.dump import dump_catalog, names_schema, getSite, spoofRequest

if __name__ == '__main__':
    # names.py --extras pleiades_wsuids=
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
    parser.add_option(
        "-x", "--include-features", dest="include_features", default=False,
        action="store_true", help="Run script as user")

    opts, args = parser.parse_args(sys.argv[1:])

    kw = {}
    
    if opts.extras:
        for params in opts.extras.split(';'):
            k, v = params.split('=')
            kw[k] = v.split(',')

    if opts.collection_path:
        kw.update(collection_path=opts.collection_path)
    if opts.include_features:
        kw.update(include_features=opts.include_features)

    app = spoofRequest(app)
    site = getSite(app)
    
    dump_catalog(site, 'Name', names_schema, **kw)

