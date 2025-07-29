# -*- coding: utf-8 -*-
from __future__ import print_function
import argparse
import sys
import transaction
import gc

from zope.component.hooks import setSite
from Products.CMFCore.utils import getToolByName


DARE_2_LOCATION_TYPE_VALUE = u"associated modern"


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=""
        "Update the LocationType field on published locations which "
        "references the 'DARE Precision 2' Positional Accuracy Assessment"
    )
    parser.add_argument("--dry-run", action="store_true", help="Enable dry run mode")
    # Deal with run script wrapping. We're passed a -c flag we don't use:
    parser.add_argument("-c", type=str, help=argparse.SUPPRESS)

    parsed = parser.parse_args()

    return parsed.dry_run


def show_progress():
    """Add a dot to the console so user can tell we're doing something"""
    sys.stdout.write(".")
    sys.stdout.flush()


def process_location(location, dry_run):
    obj = location.getObject()
    object_path = '/'.join(obj.getPhysicalPath()[2:])

    try:
        accuracy = obj.getAccuracy()
        if accuracy and accuracy.id == "dare-2":
            if DARE_2_LOCATION_TYPE_VALUE in obj.locationType:
                result = {
                    "status": "unneeded",
                    "result": object_path
                }
            else:
                result = {
                    "status": "successes",
                    "result": {
                        "old_value": obj.locationType,
                        "path": object_path
                    }
                }
                if not dry_run:
                    obj.locationType = (DARE_2_LOCATION_TYPE_VALUE,)
                    obj.reindexObject()
        else:
            return None
    except Exception as e:
        result = {
            "status": "problems",
            "result": {
                "path": object_path,
                "msg": str(e)
            }
        }
    del obj
    return result

def main(app):
    if 'Plone' in app.objectIds():
        site = app.unrestrictedTraverse('/Plone')
    elif 'plone' in app.objectIds():
        site = app.unrestrictedTraverse('/plone')
    else:
        raise RuntimeError("No Plone site found at '/Plone' or '/plone'")
    setSite(site)
    is_dry_run = parse_arguments()

    print("Dry Run:", is_dry_run)
    results = {"successes": [], "problems": [], "unneeded": []}

    portal_catalog = getToolByName(site, "portal_catalog")
    query = {"portal_type": "Location", "review_state": "published"}
    b_start = 0
    b_size = 50

    while True:
        batch = portal_catalog.searchResults(
            query,
            batch=True,
            b_start=b_start,
            b_size=b_size
        )

        if not batch:
            break

        batch_results = {"successes": [], "problems": [], "unneeded": []}
        for location in batch:
            result = process_location(location, is_dry_run)
            if result:
                batch_results[result["status"]].append(result["result"])
            del location

        results["successes"].extend(batch_results["successes"])
        results["problems"].extend(batch_results["problems"])
        results["unneeded"].extend(batch_results["unneeded"])

        if batch_results["successes"]:
            if not is_dry_run:
                transaction.commit()
            app._p_jar.cacheMinimize()
            gc.collect()

        show_progress()
        b_start += b_size

    print(
        "Done!\n\nUPDATES: {:,} records were updated successfully!".format(
            len(results["successes"])
        )
    )
    for result in results["successes"]:
        print("{}: '{}' ==> '{}'".format(result["path"], result["old_value"], (DARE_2_LOCATION_TYPE_VALUE,)))
    print("\n")

    if results["unneeded"]:
        print(
            "REDUNDANT: {:,} records were skipped because changes were already applied.".format(
                len(results["unneeded"])
            )
        )
        for result in results["unneeded"]:
            print(result)
        print("\n")

    if results["problems"]:
        print(
            "PROBLEMS: {:,} records were skipped due to problems:".format(
                len(results["problems"])
            )
        )
        for problem in results["problems"]:
            print("{}: {}".format(problem["path"], problem["msg"]))
        print("\n")

    if is_dry_run:
        print("🙅 NO CHANGES APPLIED to the database (--dry-run selected)")
    else:
        print("✅ changes were committed to the database")


if __name__ == "__main__":
    try:
        main(app)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
