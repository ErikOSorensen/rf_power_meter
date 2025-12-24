# Minimal mDNS Responder
# Responds to .local hostname and service discovery queries

import usocket as socket
import ustruct as struct
import uasyncio as asyncio
import config

# mDNS constants
MDNS_ADDR = '224.0.0.251'
MDNS_PORT = 5353

# DNS record types
TYPE_A = 1
TYPE_PTR = 12
TYPE_TXT = 16
TYPE_SRV = 33
TYPE_ANY = 255

# DNS classes
CLASS_IN = 1
CLASS_FLUSH = 0x8001


def encode_name(name):
    """Encode DNS name to wire format."""
    result = b''
    for part in name.split('.'):
        if part:
            result += bytes([len(part)]) + part.encode('utf-8')
    result += b'\x00'
    return result


def decode_name(data, offset):
    """Decode DNS name from wire format."""
    parts = []
    while True:
        length = data[offset]
        if length == 0:
            offset += 1
            break
        elif length & 0xC0 == 0xC0:
            # Pointer
            pointer = struct.unpack_from('>H', data, offset)[0] & 0x3FFF
            parts.append(decode_name(data, pointer)[0])
            offset += 2
            break
        else:
            offset += 1
            parts.append(data[offset:offset + length].decode('utf-8'))
            offset += length
    return '.'.join(parts), offset


class MDNSResponder:
    """Minimal mDNS responder for service discovery."""

    def __init__(self, hostname=None, ip_address=None):
        """
        Initialize mDNS responder.

        Args:
            hostname: Local hostname (without .local)
            ip_address: IP address string
        """
        self.hostname = hostname or config.MDNS_HOSTNAME
        self.ip_address = ip_address
        self.socket = None
        self.running = False

        # Service info
        self.service_name = "_scpi-raw._tcp.local"
        self.service_port = config.SCPI_PORT

    def set_ip(self, ip_address):
        """Set IP address."""
        self.ip_address = ip_address

    def _create_socket(self):
        """Create and configure multicast socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', MDNS_PORT))

        # Join multicast group
        mreq = struct.pack('4s4s',
                           socket.inet_aton(MDNS_ADDR),
                           socket.inet_aton('0.0.0.0'))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        sock.setblocking(False)
        return sock

    def _build_response(self, query_name, query_type):
        """
        Build mDNS response packet.

        Args:
            query_name: Queried name
            query_type: Query type

        Returns:
            Response bytes or None
        """
        hostname_local = self.hostname + ".local"
        service_instance = self.hostname + "." + self.service_name

        # Check if query matches our names
        answers = []

        if query_name.lower() == hostname_local.lower():
            if query_type in (TYPE_A, TYPE_ANY):
                # A record response
                answers.append(self._build_a_record(hostname_local))

        elif query_name.lower() == self.service_name.lower():
            if query_type in (TYPE_PTR, TYPE_ANY):
                # PTR record response
                answers.append(self._build_ptr_record())

        elif query_name.lower() == service_instance.lower():
            if query_type in (TYPE_SRV, TYPE_ANY):
                answers.append(self._build_srv_record())
            if query_type in (TYPE_TXT, TYPE_ANY):
                answers.append(self._build_txt_record())

        if not answers:
            return None

        # Build response header
        # Flags: QR=1 (response), AA=1 (authoritative)
        header = struct.pack('>HHHHHH',
                             0,      # Transaction ID
                             0x8400,  # Flags
                             0,      # Questions
                             len(answers),  # Answers
                             0,      # Authority
                             0)      # Additional

        return header + b''.join(answers)

    def _build_a_record(self, name):
        """Build A record."""
        if not self.ip_address:
            return b''

        ip_bytes = socket.inet_aton(self.ip_address)
        name_enc = encode_name(name)

        return (name_enc +
                struct.pack('>HHIH', TYPE_A, CLASS_FLUSH, 120, 4) +
                ip_bytes)

    def _build_ptr_record(self):
        """Build PTR record for service discovery."""
        service_instance = self.hostname + "." + self.service_name
        name_enc = encode_name(self.service_name)
        data = encode_name(service_instance)

        return (name_enc +
                struct.pack('>HHIH', TYPE_PTR, CLASS_IN, 4500, len(data)) +
                data)

    def _build_srv_record(self):
        """Build SRV record."""
        service_instance = self.hostname + "." + self.service_name
        hostname_local = self.hostname + ".local"
        name_enc = encode_name(service_instance)
        target = encode_name(hostname_local)

        # Priority, Weight, Port + target
        data = struct.pack('>HHH', 0, 0, self.service_port) + target

        return (name_enc +
                struct.pack('>HHIH', TYPE_SRV, CLASS_FLUSH, 120, len(data)) +
                data)

    def _build_txt_record(self):
        """Build TXT record."""
        service_instance = self.hostname + "." + self.service_name
        name_enc = encode_name(service_instance)

        # TXT data: key=value pairs
        txt_data = b''
        for item in ["model=" + config.MODEL, "version=" + config.VERSION]:
            txt_data += bytes([len(item)]) + item.encode('utf-8')

        return (name_enc +
                struct.pack('>HHIH', TYPE_TXT, CLASS_FLUSH, 4500, len(txt_data)) +
                txt_data)

    def _parse_query(self, data):
        """
        Parse mDNS query packet.

        Args:
            data: Raw packet data

        Returns:
            List of (name, type) tuples
        """
        if len(data) < 12:
            return []

        # Parse header
        header = struct.unpack_from('>HHHHHH', data, 0)
        flags = header[1]
        questions = header[2]

        # Only process queries (QR=0)
        if flags & 0x8000:
            return []

        queries = []
        offset = 12

        for _ in range(questions):
            try:
                name, offset = decode_name(data, offset)
                qtype, qclass = struct.unpack_from('>HH', data, offset)
                offset += 4
                queries.append((name, qtype))
            except Exception:
                break

        return queries

    async def run(self):
        """Run mDNS responder loop."""
        self.socket = self._create_socket()
        self.running = True

        print("mDNS responder started for {}.local".format(self.hostname))

        while self.running:
            try:
                # Non-blocking receive
                try:
                    data, addr = self.socket.recvfrom(512)
                except OSError:
                    await asyncio.sleep_ms(100)
                    continue

                # Parse queries
                queries = self._parse_query(data)

                for name, qtype in queries:
                    response = self._build_response(name, qtype)
                    if response:
                        self.socket.sendto(response, (MDNS_ADDR, MDNS_PORT))

            except Exception as e:
                print("mDNS error:", e)
                await asyncio.sleep_ms(1000)

            await asyncio.sleep_ms(10)

    def announce(self):
        """Send unsolicited announcement."""
        if not self.socket or not self.ip_address:
            return

        hostname_local = self.hostname + ".local"

        # Build announcement with A, SRV, TXT, PTR records
        answers = [
            self._build_a_record(hostname_local),
            self._build_ptr_record(),
            self._build_srv_record(),
            self._build_txt_record(),
        ]
        answers = [a for a in answers if a]

        if answers:
            header = struct.pack('>HHHHHH',
                                 0,
                                 0x8400,
                                 0,
                                 len(answers),
                                 0,
                                 0)
            packet = header + b''.join(answers)
            self.socket.sendto(packet, (MDNS_ADDR, MDNS_PORT))

    def stop(self):
        """Stop responder."""
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None
