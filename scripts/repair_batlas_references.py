# -*- coding: utf-8 -*-
from __future__ import print_function
import argparse
import itertools
import json
import sys
import transaction

from pleiades.dump import getSite, spoofRequest


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Repair old-style and idiosyncratic BAtlas references on Place objects"
    )
    parser.add_argument("input_file", type=str, help="The JSON input file name")
    parser.add_argument("--dry-run", action="store_true", help="Enable dry run mode")
    # Deal with run script wrapping. We're passed a -c flag we don't use:
    parser.add_argument("-c", type=str, help=argparse.SUPPRESS)

    parsed = parser.parse_args()

    return parsed.input_file, parsed.dry_run


def ingest_json_file(file_path):
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
            return data
    except IOError:
        print("Error: File {} does not exist or could not be read!".format(file_path))
        raise
    except ValueError:
        print("Error: Invalid JSON data!")
        raise


def chunked_iterable(iterable, size):
    """Loop over an iterable and return chunks of @size"""
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, size))
        if not chunk:
            break
        yield chunk


def translate_to_citation(json_record):
    json_key_to_citation_key = {
        "accessURI": "access_uri",
        "alternateURI": "alternate_uri",
        "bibliographicURI": "bibliographic_uri",
        "citationDetail": "citation_detail",
        "formattedCitation": "formatted_citation",
        "otherIdentifier": "identifier",
        "shortTitle": "short_title",
        "type": "type",
    }

    as_citation = {}
    for key, value in json_record.iteritems():
        key = key.strip()
        value = value.strip()
        new_key = json_key_to_citation_key[key]
        if isinstance(value, unicode):
            new_value = value.encode("utf-8")
        else:
            new_value = value

        as_citation[new_key] = new_value

    return as_citation


def diff_citations(model, candidate):
    """Return keys where the values differ after whitespace is stripped.

    Assume both dicts have the same keys.
    """
    return [key for key in model.keys() if model[key].strip() != candidate[key].strip()]


def update_citation(place, index, new_citation_value):
    citations = place.getReferenceCitations()
    citations[index] = new_citation_value

    place.setReferenceCitations(citations)


def update_places_from_json(container, json_data):
    results = {
        "successes": [],
        "problems": [],
    }
    container_url = container.absolute_url()

    for place_id, data in json_data:
        # Do we have a Place with this ID?
        place = container.get(place_id)
        if place is None:
            results["problems"].append(
                {
                    "ID": place_id,
                    "msg": "Place ID not found in {}".format(container_url),
                }
            )
            continue

        # Is there a citation at the expected index?
        expected_index = int(data["ref_position"])
        try:
            citation = place.getReferenceCitations()[expected_index]
        except IndexError:
            results["problems"].append(
                {
                    "ID": place_id,
                    "msg": u"No citation with index {}".format(expected_index),
                }
            )
            continue

        old = translate_to_citation(data["old"])
        new = translate_to_citation(data["new"])

        # Does the current data match what was predicted?
        discrepancies = diff_citations(old, citation)
        if discrepancies:
            # Already updated?
            differences = diff_citations(new, citation)
            if not differences:
                msg = "Citation already matches new data"
            else:
                msg = "Data mismatch on 'old' values: {}".format(discrepancies)
            results["problems"].append({"ID": place_id, "msg": msg})
            continue

        # If we made it this far, update the record and call it a success:
        update_citation(place, expected_index, new)
        results["successes"].append(place_id)

    return results


def show_progress():
    """Add a dot to the console so user can tell we're doing something"""
    sys.stdout.write(".")
    sys.stdout.flush()


def main(app):
    app = spoofRequest(app)
    site = getSite(app)
    input_file, is_dry_run = parse_arguments()
    json_data = ingest_json_file(input_file)

    print("Input File:", input_file)
    print("Dry Run:", is_dry_run)
    print("Ingested {:,} record[s] of JSON 😋".format(len(json_data)))
    results = {"successes": [], "problems": []}

    for batch in chunked_iterable(json_data.items(), size=100):
        batch_results = update_places_from_json(
            container=site["places"], json_data=batch
        )
        results["successes"].extend(batch_results["successes"])
        results["problems"].extend(batch_results["problems"])

        if not is_dry_run and batch_results["successes"]:
            transaction.commit()
            app._p_jar.cacheMinimize()

        show_progress()

    print(
        "Done!\n\n{} record[s] were updated successfully!".format(
            len(results["successes"])
        )
    )
    if results["problems"]:
        print("{} records where skipped:".format(len(results["problems"])))
        for problem in sorted(results["problems"], key=lambda x: int(x["ID"])):
            print("{}: {}".format(problem["ID"], problem["msg"]))
    else:
        print("No records were skipped!")


if __name__ == "__main__":
    main(app)
