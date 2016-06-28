# Run as a script, this dumps all published places to KML

if __name__ == '__main__':
    from Testing.makerequest import makerequest
    from pleiades.dump import getSite
    from pleiades.kml.dump import AllPlacesDocument, pt, main_macros, kml_macros

    site = getSite(app)
    context = makerequest(site)
    doc = pt(
        view=AllPlacesDocument(site), 
        context=context,
        request=context.REQUEST,
        macros={'kml_template': main_macros, 'kml_macros': kml_macros})
    sys.stdout.write(doc.encode('utf-8'))
    
