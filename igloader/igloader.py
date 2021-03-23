# Upload (JSON encoded) content from HL7 FHIR IG pack tarball to FHIR server.
#
# Optionally uses OAuth bearer token from ACCESS_TOKEN environment variable.
#
# See also:  https://github.com/nmdp-bioinformatics/igloader
#
# Copyright 2020 National Marrow Donor Program (NMDP).
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.

import argparse
import datetime
import json
import os
import re
import requests
import sys
import tarfile
import traceback

PACKAGE_REGEX = re.compile('^package/[^/]+\.json$')

RESOURCE_TYPE_LIST = [
    'CodeSystem',
    'ValueSet',
    'ConceptMap',
    'SearchParameter',
    'OperationDefinition',
    'StructureDefinition',
    'CapabilityStatement',
    'ImplementationGuide'
]


def main():
    """Python main function, intended for usage via command line.
    """

    # parse command-line args
    try:
        args = parse_args()
    except RuntimeError:
        sys.exit(1)
    if getattr(args, 'help'):
        sys.exit(0)

    igpack_filename = getattr(args, 'igpack')
    target_url = getattr(args, 'target')
    if 'ACCESS_TOKEN' in os.environ:
        access_token = os.environ['ACCESS_TOKEN']
    else:
        access_token = None

    # load content from tarfile
    archive_content = load_tarfile(igpack_filename)

    print('Processing JSON content from IGPack ...')
    print('IGPack Filename:  {}'.format(igpack_filename))
    print('Target URL:       {}'.format(target_url))
    print('Access Token:     {}'.format('{}...'.format(access_token[0:3]) if access_token != None else None))
    print(flush=True)

    content_by_type = organize_content_by_type(archive_content)

    # upload to FHIR server
    upload_fhir_resources(target_url, access_token, content_by_type)

    print('Done.')


def parse_args():
    """Parse command-line args.
    """

    parser = argparse.ArgumentParser(description = 'Upload (JSON-encoded) conformance resources from FHIR IGPack tar archive.', add_help = False)
    parser.add_argument('-h', '--help', action = 'store_true', help = 'show this help message and exit')
    parser.add_argument('-i', '--igpack', help = 'IGPack filename (e.g. us-core-v3.1.1-package.tgz)')
    parser.add_argument('-t', '--target', help = 'FHIR API base URL for target server (e.g. http://localhost:8080/r4)')
    args = parser.parse_args()
    usage = False
    error = False
    if getattr(args, 'help'):
        usage = True
    else:
        for arg in vars(args):
            if getattr(args, arg) == None:
                print('Error - missing required argument:  --{}'.format(arg), file=sys.stderr, flush=True)
                error = True
    if usage or error:
        parser.print_help()
        print()
        print('Additionally, if the ACCESS_TOKEN environment variable is defined,')
        print('its value will be used as an OAuth bearer token for the FHIR API.', flush=True)
        if error:
            raise RuntimeError('Command-line argument error.')
    return args


def load_tarfile(igpack_filename):
    """Load tarfile content into memory.
    """

    if not tarfile.is_tarfile(igpack_filename):
        raise RuntimeError("Error - input file is not a tar archive ({}).".format(igpack_filename))

    archive_content = [ ]
    try:
        with tarfile.open(name=igpack_filename) as archive:
            for member in archive.getmembers():
                if member.isfile() and PACKAGE_REGEX.match(member.name):
                    with archive.extractfile(member.name) as file:
                        filedata = file.read().decode('utf-8')
                        archive_content.append( { 'name': member.name, 'data': filedata } )
    except BaseException as exc:
        raise RuntimeError('Error - unable to ingest igpack ({}).'.format(igpack_filename)) from exc

    if len(archive_content) == 0:
        raise RuntimeError('Error - no JSON package files found ({}).'.format(igpack_filename))

    return archive_content


def organize_content_by_type(archive_content):
    """Organize JSON content by resourceType.
    """

    content_by_type = { }
    for item in archive_content:
        if PACKAGE_REGEX.match(item['name']):
            # parse JSON to get resourceType
            parsed_json = json.loads(item['data'])
            if 'resourceType' in parsed_json:
                resource_type = parsed_json['resourceType']
                if not resource_type in content_by_type:
                    content_by_type[resource_type] = [ ]
                item['parsed_json'] = parsed_json
                content_by_type[resource_type].append(item)

    diff = set(iter(content_by_type)).difference(set(RESOURCE_TYPE_LIST))
    if len(diff) > 0:
        unsupported_list = list(diff)
        unsupported_list.sort()
        print('Warning - unsupported resource type(s) detected:  {}'.format(unsupported_list), file=sys.stderr)
        print(flush=True)

    return content_by_type


def upload_fhir_resources(target_url, access_token, content_by_type):
    """Send resources to FHIR server.  RESOURCE_TYPE_LIST defines processing
    order by resourceType.
    """

    request_headers = {
        'Accept': 'application/fhir+json',
        'Content-Type': 'application/fhir+json; charset=utf-8'
    }
    if access_token != None:
        request_headers['Authorization'] = 'Bearer {}'.format(access_token)

    for resource_type in RESOURCE_TYPE_LIST:
        if resource_type not in content_by_type:
            continue
        qty = len(content_by_type[resource_type])
        print('{} ({})'.format(resource_type, qty))
        resource_endpoint = '{}/{}'.format(target_url, resource_type)
        count = 0
        for item in content_by_type[resource_type]:
            count += 1
            print('{}  Uploading {} ({}/{}) : '.format(datetime.datetime.now().isoformat(sep=' '), item['name'], count, qty), end='', flush=True)
            if 'ImplementationGuide' == resource_type:
                print('skipped', flush=True)
                continue

            if 'id' in item['parsed_json']:
                # use provided resource.id
                resource_id = item['parsed_json']['id']
                request_endpoint = "{}/{}".format(resource_endpoint, resource_id)
                request_headers_put = request_headers.copy()
                request_headers_put['If-None-Exist'] = '_id={}'.format(resource_id)
                response = requests.put(
                    request_endpoint,
                    headers = request_headers_put,
                    # Note:  sending the raw data to avoid complications with Python's json parser (e.g. float data type)
                    data = item['data'].encode('utf-8'),
                    allow_redirects = False)
            else:
                # should this be an error?  (resource.id missing)
                print('error', flush=True)
                raise RuntimeError('Error - resource.id missing')
            if response.status_code in { 200, 201 }:
                resource_id = item['parsed_json']['id'] if 'id' in item['parsed_json'] else ''
                print('{}/{} {}'.format(resource_type,resource_id,response.status_code), flush=True)
            else:
                print('{}'.format(response.status_code), flush=True)
                msg = "Error - {} request failed with HTTP status {}".format(request_endpoint, response.status_code)
                print(msg, file=sys.stderr)
                print(response.text, file=sys.stderr, flush=True)
                if response.status_code != 422:   # 422 status indicates this item encountered a validation error or business rule violation
                    raise RuntimeError(msg)


if __name__ == '__main__':
    # if executed as standalone Python program
    main()
