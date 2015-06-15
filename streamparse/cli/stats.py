"""
Display stats about running Storm topologies.
"""

from __future__ import absolute_import, print_function

from argparse import ArgumentDefaultsHelpFormatter as DefaultsHelpFormatter
from itertools import chain

from pkg_resources import parse_version
from prettytable import PrettyTable
from six import iteritems
from six.moves import map, zip

from .common import add_environment
from ..ext.util import (get_env_config, get_ui_json, get_ui_jsons,
                        storm_lib_version)



def display_stats(env_name, topology_name=None, component_name=None,
                  all_components=None):
    env_name = env_name
    if topology_name and all_components:
        _print_all_components(env_name, topology_name)
    elif topology_name and component_name:
        _print_component_status(env_name, topology_name, component_name)
    elif topology_name:
        _print_topology_status(env_name, topology_name)
    else:
        _print_cluster_status(env_name)


def _print_cluster_status(env_name):
    jsons = get_ui_jsons(env_name, ["/api/v1/cluster/summary",
                                    "/api/v1/topology/summary",
                                    "/api/v1/supervisor/summary"])
    # Print Cluster Summary
    ui_cluster_summary = jsons["/api/v1/cluster/summary"]
    columns = ['stormVersion', 'nimbusUptime', 'supervisors', 'slotsTotal',
               'slotsUsed', 'slotsFree', 'executorsTotal', 'tasksTotal']
    _print_stats_dict("Cluster summary", ui_cluster_summary, columns, 'r')
    # Print Topologies Summary
    ui_topologies_summary = jsons["/api/v1/topology/summary"]
    columns = ['name', 'id', 'status', 'uptime', 'workersTotal',
               'executorsTotal', 'tasksTotal']
    _print_stats_dict("Topology summary", ui_topologies_summary['topologies'],
                      columns, 'r')
    # Print Supervisor Summary
    ui_supervisor_summary = jsons["/api/v1/supervisor/summary"]
    columns = ['id', 'host', 'uptime', 'slotsTotal', 'slotsUsed']
    _print_stats_dict("Supervisor summary",
                      ui_supervisor_summary['supervisors'], columns, 'r',
                      {'host': 'l', 'uptime': 'l'})


def _get_topology_ui_detail(env_name, topology_name):
    env_name = get_env_config(env_name)[0]
    topology_id = _get_topology_id(env_name, topology_name)
    detail_url = '/api/v1/topology/%s' % topology_id
    detail = get_ui_json(env_name, detail_url)
    return detail


def _print_topology_status(env_name, topology_name):
    ui_detail = _get_topology_ui_detail(env_name, topology_name)
    # Print topology summary
    columns = ['name', 'id', 'status', 'uptime', 'workersTotal',
               'executorsTotal', 'tasksTotal']
    _print_stats_dict("Topology summary", ui_detail, columns, 'r')
    # Print topology stats
    columns = ['windowPretty', 'emitted', 'transferred', 'completeLatency',
               'acked', 'failed']
    _print_stats_dict("Topology stats", ui_detail['topologyStats'], columns,
                      'r')
    # Print spouts
    if ui_detail.get('spouts'):
        columns = ['spoutId', 'emitted', 'transferred', 'completeLatency',
                   'acked', 'failed']
        _print_stats_dict("Spouts (All time)", ui_detail['spouts'], columns,
                          'r', {'spoutId': 'l'})

    columns = ['boltId', 'executors', 'tasks', 'emitted', 'transferred',
               'capacity', 'executeLatency', 'executed', 'processLatency',
               'acked', 'failed', 'lastError']
    _print_stats_dict("Bolt (All time)", ui_detail['bolts'], columns, 'r',
                      {'boltId': 'l'})


def _get_component_ui_detail(env_name, topology_name, component_names):
    if isinstance(component_names, basestring):
        component_names = [component_names]
    env_name = get_env_config(env_name)[0]
    topology_id = _get_topology_id(env_name, topology_name)
    base_url = '/api/v1/topology/%s/component/%s'
    detail_urls = [base_url % (topology_id, name) for name in component_names]
    detail = get_ui_jsons(env_name, detail_urls)
    if len(detail) == 1:
        return detail.values()[0]
    else:
        return detail


def _print_all_components(env_name, topology_name):
    topology_ui_detail = _get_topology_ui_detail(env_name, topology_name)
    spouts = map(lambda spout: (spout['spoutId'],
                                topology_ui_detail.get('spouts', {})))
    bolts = map(lambda spout: (spout['boltId'],
                               topology_ui_detail.get('bolts', {})))
    ui_details = _get_component_ui_detail(env_name, topology_name, chain(spouts,
                                                                         bolts))
    names_and_keys = zip(map(lambda ui_detail: (ui_detail['name'],
                                                ui_details.values())),
                         ui_details.keys())
    for component_name, key in names_and_keys:
        _print_component_status(env_name, topology_name,
                                component_name, ui_details[key])


def _print_component_status(env_name, topology_name, component_name,
                            ui_detail=None):
    if not ui_detail:
        ui_detail = _get_component_ui_detail(env_name, topology_name,
                                             component_name)
    _print_component_summary(ui_detail)
    if ui_detail.get("componentType") == "spout":
        _print_spout_stats(ui_detail)
        _print_spout_output_stats(ui_detail)
        _print_spout_executors(ui_detail)
    elif ui_detail.get("componentType") == "bolt":
        _print_bolt_stats(ui_detail)
        _print_input_stats(ui_detail)
        _print_bolt_output_stats(ui_detail)


def _print_component_summary(ui_detail):
    columns = ['id', 'name', 'executors', 'tasks']
    _print_stats_dict("Component summary", ui_detail, columns, 'r')


def _print_bolt_stats(ui_detail):
    columns = ['windowPretty', 'emitted', 'transferred', 'executeLatency',
               'executed', 'processLatency', 'acked', 'failed']

    _print_stats_dict("Bolt stats", ui_detail['boltStats'], columns, 'r',
                      {'windowPretty': 'l'})


def _print_input_stats(ui_detail):
    columns = ['component', 'stream', 'executeLatency', 'processLatency',
               'executed', 'acked', 'failed']
    if ui_detail['inputStats']:
        _print_stats_dict("Input stats (All time)", ui_detail['inputStats'],
                          columns, 'r', {'component': 'l'})


def _print_bolt_output_stats(ui_detail):
    if ui_detail['outputStats']:
        columns = ['stream', 'emitted', 'transferred']
        _print_stats_dict("Output stats (All time)", ui_detail['outputStats'],
                          columns, 'r', {'stream': 'l'})


def _print_spout_stats(ui_detail):
    columns = ['windowPretty', 'emitted', 'transferred', 'completeLatency',
               'acked', 'failed']
    data = ui_detail['spoutSummary'][-1].copy()
    _print_stats_dict("Spout stats", data, columns, 'r', {'windowPretty': 'l'})


def _print_spout_output_stats(ui_detail):
    columns = ['stream', 'emitted', 'transferred', 'completeLatency',
               'acked', 'failed']
    _print_stats_dict("Output stats (All time)", ui_detail['outputStats'],
                      columns, 'r', {'stream': 'l'})


def _print_spout_executors(ui_detail):
    columns = ['id', 'uptime', 'host', 'port', 'emitted',
               'transferred', 'completeLatency', 'acked', 'failed']
    _print_stats_dict("Executors (All time)", ui_detail['executorStats'],
                      columns, 'r', {'host': 'l'})


def _print_stats_dict(header, data, columns, default_alignment,
                     custom_alignment=None):
    print("# %s" % header)
    table = PrettyTable(columns)
    table.align = default_alignment
    if isinstance(data, list):
        for row in data:
            table.add_row([row.get(key, "MISSING") for key in columns])
    else:
        table.add_row([data.get(key, "MISSING") for key in columns])
    if custom_alignment:
        for column, alignment in iteritems(custom_alignment):
            table.align[column] = alignment
    print(table)


def _get_topology_id(env_name, topology_name):
    """Get toplogy ID from summary json provided by UI api
    """
    summary_url = '/api/v1/topology/summary'
    topology_summary = get_ui_json(env_name, summary_url)
    for topology in topology_summary["topologies"]:
        if topology_name == topology["name"]:
            return topology["id"]


def subparser_hook(subparsers):
    """ Hook to add subparser for this command. """
    subparser = subparsers.add_parser('stats',
                                      formatter_class=DefaultsHelpFormatter,
                                      description=__doc__,
                                      help=__doc__)
    subparser.set_defaults(func=main)
    subparser.add_argument('--all',
                           action='store_true',
                           help='All available stats.')
    subparser.add_argument('-c', '--components',
                           help='Topology component (bolt/spout) name as '
                                'specified in Clojure topology specification')
    add_environment(subparser)


def main(args):
    """ Display stats about running Storm topologies. """
    import sys
    storm_version = storm_lib_version()
    print('Storm version: {}'.format(storm_version))
    sys.stdout.flush()
    if storm_version >= parse_version('0.9.2-incubating'):
        print('Trying to get stats')
        sys.stdout.flush()
        display_stats(args.environment, topology_name=args.name,
                      component_name=args.component, all_components=args.all)
        print('Ran display_stats')
        sys.stdout.flush()
    else:
        print("ERROR: Storm {0} does not support this command."
              .format(storm_version))
        sys.stdout.flush()
