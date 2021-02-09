# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import ipaddress
import random
import re
import socket
import time

import requests

from openstack import exceptions as os_exc
from os_vif import objects
from oslo_cache import core as cache
from oslo_config import cfg
from oslo_log import log
from oslo_serialization import jsonutils

from kuryr_kubernetes import clients
from kuryr_kubernetes import constants
from kuryr_kubernetes import exceptions
from kuryr_kubernetes.objects import lbaas as obj_lbaas
from kuryr_kubernetes.objects import vif
from kuryr_kubernetes import os_vif_util

CONF = cfg.CONF
LOG = log.getLogger(__name__)

VALID_MULTI_POD_POOLS_OPTS = {'noop': ['neutron-vif',
                                       'nested-vlan',
                                       'nested-macvlan',
                                       'sriov',
                                       'nested-dpdk'],
                              'neutron': ['neutron-vif'],
                              'nested': ['nested-vlan'],
                              }
DEFAULT_TIMEOUT = 500
DEFAULT_INTERVAL = 1
DEFAULT_JITTER = 3
MAX_BACKOFF = 60
MAX_ATTEMPTS = 10

subnet_caching_opts = [
    cfg.BoolOpt('caching', default=True),
    cfg.IntOpt('cache_time', default=3600),
]

nodes_caching_opts = [
    cfg.BoolOpt('caching', default=True),
    cfg.IntOpt('cache_time', default=3600),
]

CONF.register_opts(subnet_caching_opts, "subnet_caching")
CONF.register_opts(nodes_caching_opts, "nodes_caching")

cache.configure(CONF)
subnet_cache_region = cache.create_region()
MEMOIZE = cache.get_memoization_decorator(
    CONF, subnet_cache_region, "subnet_caching")
cache.configure_cache_region(CONF, subnet_cache_region)

nodes_cache_region = cache.create_region()
MEMOIZE_NODE = cache.get_memoization_decorator(
    CONF, nodes_cache_region, "nodes_caching")
cache.configure_cache_region(CONF, nodes_cache_region)

RESOURCE_MAP = {'Endpoints': 'endpoints',
                'KuryrLoadBalancer': 'kuryrloadbalancers',
                'KuryrNet': 'kuryrnets',
                'KuryrNetPolicy': 'kuryrnetpolicies',
                'KuryrNetwork': 'kuryrnetworks',
                'KuryrNetworkPolicy': 'kuryrnetworkpolicies',
                'KuryrPort': 'kuryrports',
                'Namespace': 'namespaces',
                'NetworkPolicy': 'networkpolicies',
                'Node': 'nodes',
                'Pod': 'pods',
                'Service': 'services',
                'Machine': 'machines'}
API_RE = re.compile(r'v\d+')


def get_res_link(obj):
    """Return selfLink equivalent for provided resource"""
    # First try, if we still have it
    try:
        return obj['metadata']['selfLink']
    except KeyError:
        pass

    # If not, let's proceed with the path assembling.
    try:
        res_type = RESOURCE_MAP[obj['kind']]
    except KeyError:
        LOG.error('Unknown resource kind: %s', obj.get('kind'))
        raise

    namespace = ''
    if obj['metadata'].get('namespace'):
        namespace = f"/namespaces/{obj['metadata']['namespace']}"

    try:
        api = f"/apis/{obj['apiVersion']}"
        if API_RE.match(obj['apiVersion']):
            api = f"/api/{obj['apiVersion']}"
    except KeyError:
        LOG.error("Object doesn't have an apiVersion available: %s", obj)
        raise

    return f"{api}{namespace}/{res_type}/{obj['metadata']['name']}"


def get_api_ver(path):
    """Get apiVersion out of resource path.

    Path usually is something simillar to:

        /api/v1/namespaces/default/pods/pod-5bb648d658-55n76

    in case of core resources, and:

        /apis/openstack.org/v1/namespaces/default/kuryrloadbalancers/lb-324

    in case of custom resoures.
    """
    if path.startswith('/api/'):
        return path.split('/')[2]

    if path.startswith('/apis/'):
        return '/'.join(path.split('/')[2:4])

    raise ValueError('Provided path is not Kubernetes api path: %s', path)


def utf8_json_decoder(byte_data):
    """Deserializes the bytes into UTF-8 encoded JSON.

    :param byte_data: The bytes to be converted into the UTF-8 encoded JSON.
    :returns: The UTF-8 encoded JSON represented by Python dictionary format.
    """
    return jsonutils.loads(byte_data.decode('utf8'))


def convert_netns(netns):
    """Convert /proc based netns path to Docker-friendly path.

    When CONF.docker_mode is set this method will change /proc to
    /CONF.netns_proc_dir. This allows netns manipulations to work when running
    in Docker container on Kubernetes host.

    :param netns: netns path to convert.
    :return: Converted netns path.
    """
    if CONF.cni_daemon.docker_mode:
        return netns.replace('/proc', CONF.cni_daemon.netns_proc_dir)
    else:
        return netns


def get_res_unique_name(resource):
    """Returns a unique name for the resource like pod or CRD.

    It returns a unique name for the resource composed of its name and the
    namespace it is created in or just name for cluster-scoped resources.

    :returns: String with <namespace/>name of the resource
    """
    try:
        return "%(namespace)s/%(name)s" % resource['metadata']
    except KeyError:
        return "%(name)s" % resource['metadata']


def check_suitable_multi_pool_driver_opt(pool_driver, pod_driver):
    return pod_driver in VALID_MULTI_POD_POOLS_OPTS.get(pool_driver, [])


def exponential_sleep(deadline, attempt, interval=DEFAULT_INTERVAL,
                      max_backoff=MAX_BACKOFF, jitter=DEFAULT_JITTER):
    """Sleep for exponential duration.

    :param deadline: sleep timeout duration in seconds.
    :param attempt: attempt count of sleep function.
    :param interval: minimal time interval to sleep
    :param max_backoff: maximum time to sleep
    :param jitter: max value of jitter added to the sleep time
    :return: the actual time that we've slept
    """
    now = time.time()
    seconds_left = deadline - now

    if seconds_left <= 0:
        return 0

    to_sleep = exponential_backoff(attempt, interval, max_backoff=max_backoff,
                                   jitter=jitter)

    if to_sleep > seconds_left:
        to_sleep = seconds_left

    if to_sleep < interval:
        to_sleep = interval

    time.sleep(to_sleep)
    return to_sleep


def exponential_backoff(attempt, interval=DEFAULT_INTERVAL,
                        max_backoff=MAX_BACKOFF, jitter=DEFAULT_JITTER):
    """Return exponential backoff duration with jitter.

    This implements a variation of exponential backoff algorithm [1] (expected
    backoff E(c) = interval * 2 ** attempt / 2).

    [1] https://en.wikipedia.org/wiki/Exponential_backoff
    """

    if attempt >= MAX_ATTEMPTS:
        # No need to calculate very long intervals
        attempt = MAX_ATTEMPTS

    backoff = 2 ** attempt * interval

    if max_backoff is not None and backoff > max_backoff:
        backoff = max_backoff

    if jitter:
        backoff += random.randint(0, jitter)

    return backoff


def get_node_name():
    # leader-elector container based on K8s way of doing leader election is
    # assuming that hostname it sees is the node id. Containers within a pod
    # are sharing the hostname, so this will match what leader-elector returns.
    return socket.gethostname()


def get_leader_name():
    url = 'http://localhost:%d' % CONF.kubernetes.controller_ha_elector_port
    try:
        return requests.get(url).json()['name']
    except Exception:
        LOG.exception('Error when fetching current leader pod name.')
        # NOTE(dulek): Assuming there's no leader when we can't contact leader
        #              elector container.
        return None


@MEMOIZE_NODE
def get_nodes_ips(node_subnets):
    """Get the IPs of the trunk ports associated to the deployment."""
    trunk_ips = []
    os_net = clients.get_network_client()
    tags = CONF.neutron_defaults.resource_tags
    if tags:
        ports = os_net.ports(status='ACTIVE', tags=tags)
    else:
        # NOTE(ltomasbo: if tags are not used, assume all the trunk ports are
        # part of the kuryr deployment
        ports = os_net.ports(status='ACTIVE')
    for port in ports:
        if (port.trunk_details and port.fixed_ips and
                port.fixed_ips[0]['subnet_id'] in node_subnets):
            trunk_ips.append(port.fixed_ips[0]['ip_address'])
    return trunk_ips


@MEMOIZE
def get_subnet(subnet_id):
    os_net = clients.get_network_client()

    n_subnet = os_net.get_subnet(subnet_id)
    n_network = os_net.get_network(n_subnet.network_id)

    subnet = os_vif_util.neutron_to_osvif_subnet(n_subnet)
    network = os_vif_util.neutron_to_osvif_network(n_network)
    network.subnets.objects.append(subnet)
    return network


@MEMOIZE
def get_subnet_cidr(subnet_id):
    os_net = clients.get_network_client()
    try:
        subnet_obj = os_net.get_subnet(subnet_id)
    except os_exc.ResourceNotFound:
        LOG.exception("Subnet %s CIDR not found!", subnet_id)
        raise
    return subnet_obj.cidr


def get_subnet_id(**filters):
    os_net = clients.get_network_client()
    subnets = os_net.subnets(**filters)

    try:
        return next(subnets).id
    except StopIteration:
        return None


@MEMOIZE
def get_subnets_id_cidrs(subnet_ids):
    os_net = clients.get_network_client()
    subnets = os_net.subnets()
    cidrs = [(subnet.id, subnet.cidr) for subnet in subnets
             if subnet.id in subnet_ids]
    if len(cidrs) != len(subnet_ids):
        existing = {subnet.id for subnet in subnets}
        missing = set(subnet_ids) - existing
        LOG.exception("CIDRs of subnets %s not found!", missing)
        raise os_exc.ResourceNotFound()
    return cidrs


def get_subnets_cidrs(subnet_ids):
    return [x[1] for x in get_subnets_id_cidrs(subnet_ids)]


@MEMOIZE
def get_subnetpool_version(subnetpool_id):
    os_net = clients.get_network_client()
    try:
        subnetpool_obj = os_net.get_subnet_pool(subnetpool_id)
    except os_exc.ResourceNotFound:
        LOG.exception("Subnetpool %s not found!", subnetpool_id)
        raise
    return subnetpool_obj.ip_version


def extract_pod_annotation(annotation):
    obj = objects.base.VersionedObject.obj_from_primitive(annotation)
    # FIXME(dulek): This is code to maintain compatibility with Queens. We can
    #               remove it once we stop supporting upgrading from Queens,
    #               most likely in Stein. Note that this requires being sure
    #               that *all* the pod annotations are in new format.
    if obj.obj_name() != vif.PodState.obj_name():
        # This is old format of annotations - single VIF object. We need to
        # pack it in PodState object.
        obj = vif.PodState(default_vif=obj)

    return obj


def has_limit(quota):
    NO_LIMIT = -1
    return quota['limit'] != NO_LIMIT


def is_available(resource, resource_quota):
    availability = resource_quota['limit'] - resource_quota['used']
    if availability <= 3:
        LOG.warning("Neutron quota low for %s. Used %d out of %d limit.",
                    resource, resource_quota['limit'], resource_quota['used'])
    elif availability <= 0:
        LOG.error("Neutron quota exceeded for %s. Used %d out of %d limit.",
                  resource, resource_quota['limit'], resource_quota['used'])
        return False
    return True


def has_kuryr_crd(crd_url):
    k8s = clients.get_kubernetes_client()
    try:
        k8s.get(crd_url, json=False, headers={'Connection': 'close'})
    except exceptions.K8sResourceNotFound:
        LOG.error('CRD %s does not exists.', crd_url)
    except exceptions.K8sClientException:
        LOG.exception('Error fetching CRD %s, assuming it does not exist.',
                      crd_url)
        return False
    return True


def get_lbaas_spec(k8s_object):
    # k8s_object can be service or endpoint
    try:
        annotations = k8s_object['metadata']['annotations']
        annotation = annotations[constants.K8S_ANNOTATION_LBAAS_SPEC]
    except KeyError:
        return None
    obj_dict = jsonutils.loads(annotation)
    obj = obj_lbaas.LBaaSServiceSpec.obj_from_primitive(obj_dict)
    LOG.debug("Got LBaaSServiceSpec from annotation: %r", obj)
    return obj


def set_lbaas_spec(service, lbaas_spec):
    # TODO(ivc): extract annotation interactions
    if lbaas_spec is None:
        LOG.debug("Removing LBaaSServiceSpec annotation: %r", lbaas_spec)
        annotation = None
    else:
        lbaas_spec.obj_reset_changes(recursive=True)
        LOG.debug("Setting LBaaSServiceSpec annotation: %r", lbaas_spec)
        annotation = jsonutils.dumps(lbaas_spec.obj_to_primitive(),
                                     sort_keys=True)
    svc_link = get_res_link(service)
    ep_link = get_endpoints_link(service)
    k8s = clients.get_kubernetes_client()

    try:
        k8s.annotate(ep_link,
                     {constants.K8S_ANNOTATION_LBAAS_SPEC: annotation})
    except exceptions.K8sResourceNotFound as ex:
        LOG.debug("Failed to annotate svc: %s", ex)
        raise exceptions.ResourceNotReady(ep_link)
    except exceptions.K8sClientException:
        LOG.debug("Failed to annotate endpoint %r", ep_link)
        raise
    try:
        k8s.annotate(svc_link,
                     {constants.K8S_ANNOTATION_LBAAS_SPEC: annotation},
                     resource_version=service['metadata']['resourceVersion'])
    except exceptions.K8sResourceNotFound as ex:
        LOG.debug("Failed to annotate svc: %s", ex)
        raise exceptions.ResourceNotReady(svc_link)
    except exceptions.K8sClientException:
        LOG.exception("Failed to annotate svc: %r", svc_link)
        raise


def get_lbaas_state(endpoint):
    try:
        annotations = endpoint['metadata']['annotations']
        annotation = annotations[constants.K8S_ANNOTATION_LBAAS_STATE]
    except KeyError:
        return None
    obj_dict = jsonutils.loads(annotation)
    obj = obj_lbaas.LBaaSState.obj_from_primitive(obj_dict)
    LOG.debug("Got LBaaSState from annotation: %r", obj)
    return obj


def set_lbaas_state(endpoints, lbaas_state):
    # TODO(ivc): extract annotation interactions
    if lbaas_state is None:
        LOG.debug("Removing LBaaSState annotation: %r", lbaas_state)
        annotation = None
    else:
        lbaas_state.obj_reset_changes(recursive=True)
        LOG.debug("Setting LBaaSState annotation: %r", lbaas_state)
        annotation = jsonutils.dumps(lbaas_state.obj_to_primitive(),
                                     sort_keys=True)
    k8s = clients.get_kubernetes_client()
    k8s.annotate(get_res_link(endpoints),
                 {constants.K8S_ANNOTATION_LBAAS_STATE: annotation},
                 resource_version=endpoints['metadata']['resourceVersion'])


def get_endpoints_link(service):
    svc_link = get_res_link(service)
    link_parts = svc_link.split('/')

    if link_parts[-2] != 'services':
        raise exceptions.IntegrityError(
            f"Unsupported service link: {svc_link}")
    link_parts[-2] = 'endpoints'

    return "/".join(link_parts)


def get_service_link(endpoints):
    endpoints_link = get_res_link(endpoints)
    link_parts = endpoints_link.split('/')

    if link_parts[-2] != 'endpoints':
        raise exceptions.IntegrityError(
            f"Unsupported endpoints link: {endpoints_link}")
    link_parts[-2] = 'services'

    return "/".join(link_parts)


def has_port_changes(service, loadbalancer_crd):
    if not loadbalancer_crd:
        return False
    link = get_res_link(service)
    svc_port_set = service['spec'].get('ports')

    for port in svc_port_set:
        port['targetPort'] = str(port['targetPort'])
    spec_port_set = loadbalancer_crd['spec'].get('ports', [])
    if spec_port_set:
        if len(svc_port_set) != len(spec_port_set):
            return True
        pairs = zip(svc_port_set, spec_port_set)
        diff = any(x != y for x, y in pairs)
        if diff:
            LOG.debug("LBaaS spec ports %(spec_ports)s != %(svc_ports)s "
                      "for %(link)s" % {'spec_ports': spec_port_set,
                                        'svc_ports': svc_port_set,
                                        'link': link})
        return diff
    return False


def get_service_ports(service):
    return [{'name': port.get('name'),
             'protocol': port.get('protocol', 'TCP'),
             'port': port['port'],
             'targetPort': str(port['targetPort'])}
            for port in service['spec']['ports']]


@MEMOIZE
def get_service_subnet_version():
    os_net = clients.get_network_client()
    svc_subnet_id = CONF.neutron_defaults.service_subnet
    try:
        svc_subnet = os_net.get_subnet(svc_subnet_id)
    except os_exc.ResourceNotFound:
        LOG.exception("Service subnet %s not found", svc_subnet_id)
        raise
    return svc_subnet.ip_version


def clean_lb_crd_status(loadbalancer_name):
    namespace, name = loadbalancer_name.split('/')
    k8s = clients.get_kubernetes_client()
    try:
        k8s.patch_crd('status', f'{constants.K8S_API_CRD_NAMESPACES}'
                      f'/{namespace}/kuryrloadbalancers/{name}', {})
    except exceptions.K8sResourceNotFound:
        LOG.debug('KuryrLoadbalancer CRD not found %s',
                  name)
    except exceptions.K8sClientException:
        LOG.exception('Error updating KuryrLoadbalancer CRD %s',
                      name)
        raise


def is_kubernetes_default_resource(obj):
    """Check if Object is a resource associated to the API

    Verifies if the Object is on the default namespace
    and has the name kubernetes. Those name and namespace
    are given to Kubernetes Service and Endpoints for the API.

    :param obj: Kubernetes object dict
    :returns: True if is default resource for the API, false
              otherwise.
    """
    return (obj['metadata']['name'] == 'kubernetes' and
            obj['metadata']['namespace'] == 'default')


def get_pod_by_ip(pod_ip, namespace=None):
    k8s = clients.get_kubernetes_client()
    pod = {}
    try:
        if namespace:
            pods = k8s.get(f'{constants.K8S_API_BASE}/namespaces/{namespace}/'
                           f'pods?fieldSelector=status.phase=Running,'
                           f'status.podIP={pod_ip}')
        else:
            pods = k8s.get(f'{constants.K8S_API_BASE}/'
                           f'pods?fieldSelector=status.phase=Running,'
                           f'status.podIP={pod_ip}')
    except exceptions.K8sClientException:
        LOG.exception('Error retrieving Pod with IP %s', pod_ip)
        raise
    if pods.get('items'):
        # Only one Pod should have the IP
        return pods['items'][0]
    return pod


def get_current_endpoints_target(ep, port, spec_ports, ep_name):
    """Retrieve details about one specific Endpoint target

    Defines the details about the Endpoint target, such as the
    target address, name, port value and the Pool ID. In case,
    the Endpoints has no targetRef defined, the name of the
    target will be the same as the Endpoint.

    :param ep: Endpoint on the Endpoints object
    :param port: Endpoint port
    :param spec_ports: dict of port name associated to pool ID
    :param ep_name: Name of the Endpoints object
    :returns: Tuple with target address, target name, port number
              and pool ID.
    """
    target_ref = ep.get('targetRef', {})
    pod_name = ep_name
    # NOTE(maysams): As we don't support dual-stack, we assume
    # only one address is possible on the addresses field.
    address = ep['addresses'][0]
    if target_ref:
        pod_name = target_ref.get('name', '')
    return (address, pod_name, port['port'],
            spec_ports.get(port.get('name')))


def get_subnet_by_ip(nodes_subnets, target_ip):
    ip = ipaddress.ip_address(target_ip)
    for nodes_subnet in nodes_subnets:
        if ip in ipaddress.ip_network(nodes_subnet[1]):
            return nodes_subnet

    return None
