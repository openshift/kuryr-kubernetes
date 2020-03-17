# Copyright (c) 2019 Red Hat, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import argparse
import base64
import copy
import os

from flask import Flask
from flask import jsonify
from flask import request
import jsonpatch

from kuryr_kubernetes import constants
from kuryr_kubernetes import exceptions
from kuryr_kubernetes import k8s_client

app = Flask(__name__)
first_request = True


@app.route('/', methods=['POST'])
def webhook():
    global first_request
    if first_request:
        first_request = False
        host = os.environ['KUBERNETES_SERVICE_HOST']
        port = os.environ['KUBERNETES_SERVICE_PORT']
        api_root = "https://%s:%s" % (host, port)
        k8s = k8s_client.K8sClient(api_root)
        # list of namespaces with operators to delete
        for ns in app.config['ns_to_clear']:
            try:
                pods = k8s.get('{}/namespaces/{}/pods'.format(
                    constants.K8S_API_BASE, ns))
            except (exceptions.K8sClientException,
                    exceptions.K8sResourceNotFound):
                # unexpected exception, ensure it gets retried
                first_request = True
                continue
            for pod in pods.get('items'):
                options = pod['spec'].get('dnsConfig', {}).get('options', [])
                if not [o for o in options if o['name'] == 'use-vc']:
                    try:
                        k8s.delete('{}/namespaces/{}/pods/{}'.format(
                            constants.K8S_API_BASE, ns,
                            pod['metadata']['name']))
                    except (exceptions.K8sClientException,
                            exceptions.K8sResourceNotFound):
                        # unexpected exception, ensure it gets retried
                        first_request = True
                        continue

    request_info = request.json

    obj = request_info['request']['object']
    mod = copy.deepcopy(obj)
    patch_str = ""

    if 'dnsConfig' not in mod['spec']:
        mod['spec']['dnsConfig'] = {}

    if 'options' not in mod['spec']['dnsConfig']:
        mod['spec']['dnsConfig']['options'] = []

    if not [o for o in mod['spec']['dnsConfig']['options']
            if o['name'] == 'use-vc']:
        mod['spec']['dnsConfig']['options'].append(
            {'name': 'use-vc', 'value': ''})

        patch = jsonpatch.JsonPatch.from_diff(obj, mod)
        patch_str = base64.b64encode(str(patch).encode()).decode()

    admission_review = {
        'apiVersion': request_info['apiVersion'],
        'kind': request_info['kind'],
        'response': {
            'allowed': True,
            'uid': request_info['request']['uid'],
        },
    }

    if patch_str:
        admission_review['response'].update({
            'patch': patch_str,
            'patchType': 'JSONPatch',
        })

    return jsonify(admission_review)


def main():
    parser = argparse.ArgumentParser(description='Kuryr DNS webhook')
    parser.add_argument(
        '--port', type=int, default=443, help='Port on which to serve.')
    parser.add_argument(
        '--bind-address', default='0.0.0.0',
        help='The IP address on which to listen for the --port port.')
    parser.add_argument(
        '--tls-cert-file', default='cert.pem',
        help='File containing the default x509 Certificate for HTTPS.')
    parser.add_argument(
        '--tls-private-key-file', default='key.pem',
        help='File containing the default x509 private key matching '
             '--tls-cert-file.')
    parser.add_argument(
        '--ns', action='append',
        help='List of namespaces with pods to delete to ensure right creation '
             'order.')
    args = parser.parse_args()

    app.config['ns_to_clear'] = args.ns
    app.run(host=args.bind_address, port=args.port,
            ssl_context=(args.tls_cert_file, args.tls_private_key_file))


if __name__ == '__main__':
    main()
