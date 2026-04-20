from pox.core import core
import pox.openflow.libopenflow_01 as of

log = core.getLogger()

# MAC learning table
mac_to_port = {}

# Path tracking
packet_paths = {}

# To avoid duplicate prints
printed_flows = set()

# Dynamic host naming (h1, h2, ...)
host_map = {}

def mac_to_host(mac):
    mac = str(mac)
    if mac not in host_map:
        host_map[mac] = f"h{len(host_map)+1}"
    return host_map[mac]

def _handle_PacketIn(event):
    packet = event.parsed
    dpid = event.dpid
    in_port = event.port

    src = str(packet.src)
    dst = str(packet.dst)

    # Learn MAC → port
    mac_to_port[(dpid, src)] = in_port

    flow_id = (src, dst)

    # Initialize path
    if flow_id not in packet_paths:
        packet_paths[flow_id] = []

    # Add switch only once
    if f"s{dpid}" not in packet_paths[flow_id]:
        packet_paths[flow_id].append(f"s{dpid}")

    # Forwarding logic
    if (dpid, dst) in mac_to_port:
        out_port = mac_to_port[(dpid, dst)]
    else:
        out_port = of.OFPP_FLOOD

    # Install flow rule
    msg = of.ofp_flow_mod()
    msg.match = of.ofp_match.from_packet(packet)
    msg.actions.append(of.ofp_action_output(port=out_port))
    event.connection.send(msg)

    # ALSO send the packet out immediately
    packet_out = of.ofp_packet_out()
    packet_out.data = event.ofp
    packet_out.actions.append(of.ofp_action_output(port=out_port))
    event.connection.send(packet_out)

    # Print path ONLY once per flow
    if (dpid, dst) in mac_to_port:
        if flow_id not in printed_flows:
            path = " → ".join(packet_paths[flow_id])
            log.info(f"Path: {mac_to_host(src)} → {path} → {mac_to_host(dst)}")
            printed_flows.add(flow_id)

        # Clear path after printing
        del packet_paths[flow_id]

def launch():
    core.openflow.addListenerByName("PacketIn", _handle_PacketIn)
    log.info("Path tracing controller started")
