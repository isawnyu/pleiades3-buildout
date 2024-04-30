from __future__ import print_function
import argparse
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
    parser.add_argument(
        "--just-one",
        type=str,
        default=None,
        help="An optional ID for a single Place you'd like to update",
    )

    parser.add_argument(
        "-c", type=str, help=argparse.SUPPRESS
    )  # SUPPRESS will prevent it from showing in help

    parsed = parser.parse_args()

    return parsed.input_file, parsed.dry_run, parsed.just_one


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


def compare_dicts(model, candidate):
    differences = []

    for key in model:
        if model[key] != candidate[key]:
            differences.append(key)

    return differences


def convert_dict_format(json_record):
    # Define the mapping of old keys to new keys
    key_mapping = {
        u"accessURI": "access_uri",
        u"alternateURI": "alternate_uri",
        u"bibliographicURI": "bibliographic_uri",
        u"citationDetail": "citation_detail",
        u"formattedCitation": "formatted_citation",
        u"otherIdentifier": "identifier",
        u"shortTitle": "short_title",
        u"type": "type",
    }

    translated = {}
    for key, value in json_record.iteritems():
        # Map the old key to the new key
        new_key = key_mapping[key]
        if isinstance(value, unicode):
            new_value = value.encode("utf-8")
        else:
            new_value = value

        translated[new_key] = new_value

    return translated


def compare_citation_to_expectation(expectation, citation):
    translated = convert_dict_format(expectation)
    discrepancies = compare_dicts(translated, citation)

    return discrepancies


def update_citation(place, index, citation, data):
    translated = convert_dict_format(data)
    differences = compare_dicts(citation, translated)
    if not differences:
        return "Citation already matches new data"

    place.getReferenceCitations()[index] = translated


def update_places_from_json(container, json_data, is_dry_run, place_id):
    results = {
        "successes": [],
        "problems": [],
    }
    container_url = container.absolute_url()
    if place_id is not None:
        if place_id in json_data:
            records = {place_id: json_data[place_id]}
        else:
            raise ValueError(
                "You specified a single Place ID, but this ID was not included "
                "in your JSON file!"
            )
    else:
        records = json_data

    print("Working with {} record[s]".format(len(records)))

    for place_id, data in records.items():
        # Do we have a Place with this ID?
        place = container.get(place_id)
        if place is None:
            results["problems"].append(
                {
                    "ID": place_id,
                    "msg": u"Place ID not found in {}".format(container_url),
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

        # Does the current data match what was predicted?
        discrepancies = compare_citation_to_expectation(data["old"], citation)
        if discrepancies:
            results["problems"].append(
                {
                    "ID": place_id,
                    "msg": u"Data mismatch on keys: {}".format(discrepancies),
                }
            )
            continue

        error = update_citation(place, expected_index, citation, data["new"])
        if error:
            results["problems"].append(
                {"ID": place_id, "msg": u"Citation update aborted: {}".format(error)}
            )
        else:
            results["successes"].append(place_id)

    return results


def main(app):
    app = spoofRequest(app)
    site = getSite(app)
    p_jar = site._p_jar

    input_file, is_dry_run, place_id = parse_arguments()
    print("Input File:", input_file)
    print("Dry Run Mode?:", is_dry_run)
    if place_id is not None:
        print("Processing a single Place: {}".format(place_id))

    json_data = ingest_json_file(input_file)

    results = update_places_from_json(
        container=site["places"],
        json_data=json_data,
        is_dry_run=is_dry_run,
        place_id=place_id,
    )
    print("{} record[s] were updated successfully!".format(len(results["successes"])))
    if results["problems"]:
        print("{} records where skipped:".format(len(results["problems"])))
        for problem in results["problems"]:
            print("{}: {}".format(problem["ID"], problem["msg"]))
    else:
        print("No records were skipped!")


if __name__ == "__main__":
    main(app)
