# Copyright (c) 2020 Red Hat, Inc.
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

from pprint import pprint
import sys

from openstack import exceptions as os_exc

from kuryr_kubernetes import clients
from kuryr_kubernetes import config


def gather_network_data(os_net):
    print("Ports:")
    pprint(list(os_net.ports()))
    print("Networks:")
    pprint(list(os_net.networks()))
    print("Subnets:")
    pprint(list(os_net.subnets()))
    print("Security Groups:")
    pprint(list(os_net.security_groups()))
    print("Routers:")
    pprint(list(os_net.routers()))
    print("Trunks:")
    pprint(list(os_net.trunks()))


def main():
    config.init(sys.argv[1:])
    clients.setup_clients()

    try:
        os_net = clients.get_network_client()
        gather_network_data(os_net)
    except os_exc.SDKException as e:
        exc = str(e)
        print(f'Error when retriving network resources: {exc}')

    try:
        lbaas = clients.get_loadbalancer_client()
        print("Load Balancers:")
        pprint(list(lbaas.load_balancers()))
    except os_exc.SDKException as e:
        exc = str(e)
        print(f'Error when retriving load balancers: {exc}')


if __name__ == '__main__':
    main()
