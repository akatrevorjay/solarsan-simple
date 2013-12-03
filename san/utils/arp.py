""" ARP related functions. """

import logging
log = logging.getLogger(__name__)
import struct
import socket


ETH_BROADCAST = 'ff:ff:ff:ff:ff:ff'
ETH_TYPE_ARP = 0x0806


def ether_aton(addr):
    """Convert a ethernet address in form AA:BB:... to a sequence of
    bytes.
    """
    return ''.join([struct.pack("B", int(nn, 16))
                    for nn in addr.split(':')])


def send_arp(ifname, address):
    """Send out a gratuitous on interface C{ifname}."""
    # Try to get hold of a socket:
    try:
        ether_socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
        ether_socket.bind((ifname, ETH_TYPE_ARP))
        ether_addr = ether_socket.getsockname()[4]
    except socket.error, (errno, msg):
        if errno == 1:
            log.error('ARP messages can only be sent by root')
        raise

    # From Wikipedia:
    #
    # ARP may also be used as a simple announcement protocol. This is
    # useful for updating other hosts' mapping of a hardware address
    # when the sender's IP address or MAC address has changed. Such an
    # announcement, also called a gratuitous ARP message, is usually
    # broadcast as an ARP request containing the sender's protocol
    # address (SPA) in the target field (TPA=SPA), with the target
    # hardware address (THA) set to zero. An alternative is to
    # broadcast an ARP reply with the sender's hardware and protocol
    # addresses (SHA and SPA) duplicated in the target fields
    # (TPA=SPA, THA=SHA).
    gratuitous_arp = [
        # HTYPE
        struct.pack("!h", 1),
        # PTYPE (IPv4)
        struct.pack("!h", 0x0800),
        # HLEN
        struct.pack("!B", 6),
        # PLEN
        struct.pack("!B", 4),
        # OPER (reply)
        struct.pack("!h", 2),
        # SHA
        ether_addr,
        # SPA
        socket.inet_aton(address),
        # THA
        ether_addr,
        # TPA
        socket.inet_aton(address)
    ]
    ether_frame = [
        # Destination address:
        ether_aton(ETH_BROADCAST),
        # Source address:
        ether_addr,
        # Protocol
        struct.pack("!h", ETH_TYPE_ARP),
        # Data
        ''.join(gratuitous_arp)
    ]
    ether_socket.send(''.join(ether_frame))
    ether_socket.close()
