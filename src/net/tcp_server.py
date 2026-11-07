# TCP Server for SCPI Commands
# Async TCP server handling SCPI protocol

import uasyncio as asyncio
import config


class SCPIConnection:
    """Handles a single SCPI client connection."""

    def __init__(self, reader, writer, scpi_handler, conn_id):
        """
        Initialize connection handler.

        Args:
            reader: StreamReader
            writer: StreamWriter
            scpi_handler: SCPI command handler function
            conn_id: Connection identifier
        """
        self.reader = reader
        self.writer = writer
        self.scpi_handler = scpi_handler
        self.conn_id = conn_id
        self.active = True

    async def handle(self):
        """Handle connection - read commands and send responses."""
        try:
            while self.active:
                # Read line (command terminated by \n)
                try:
                    line = await asyncio.wait_for(
                        self.reader.readline(),
                        timeout=300  # 5 minute timeout
                    )
                except asyncio.TimeoutError:
                    break

                if not line:
                    break

                # Decode and strip
                try:
                    command = line.decode('utf-8').strip()
                except UnicodeError:
                    command = line.decode('latin-1').strip()

                if not command:
                    continue

                # Handle multiple commands separated by semicolon
                commands = command.split(';')
                responses = []

                for cmd in commands:
                    cmd = cmd.strip()
                    if cmd:
                        response = await self._process_command(cmd)
                        if response is not None:
                            responses.append(response)

                # Send responses
                if responses:
                    response_text = ';'.join(responses) + '\n'
                    self.writer.write(response_text.encode('utf-8'))
                    await self.writer.drain()

        except Exception as e:
            print("Connection {} error: {}".format(self.conn_id, e))
        finally:
            await self.close()

    async def _process_command(self, command):
        """
        Process a single SCPI command.

        Args:
            command: SCPI command string

        Returns:
            Response string or None
        """
        try:
            return self.scpi_handler(command)
        except Exception as e:
            return "ERROR: {}".format(e)

    async def close(self):
        """Close connection."""
        self.active = False
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass


class TCPServer:
    """Async TCP server for SCPI connections."""

    def __init__(self, scpi_handler, port=None, max_connections=3):
        """
        Initialize TCP server.

        Args:
            scpi_handler: Function to handle SCPI commands
            port: TCP port (default from config)
            max_connections: Maximum simultaneous connections
        """
        self.scpi_handler = scpi_handler
        self.port = port or config.SCPI_PORT
        self.max_connections = max_connections
        self.server = None
        self.connections = {}
        self._conn_counter = 0
        self.running = False

    async def start(self):
        """Start the TCP server."""
        self.running = True
        self.server = await asyncio.start_server(
            self._handle_client,
            '0.0.0.0',
            self.port
        )
        print("SCPI server listening on port {}".format(self.port))
        return self.server

    async def _handle_client(self, reader, writer):
        """Handle new client connection."""
        # Check connection limit
        if len(self.connections) >= self.max_connections:
            writer.write(b"ERROR: Too many connections\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        # Create connection handler
        self._conn_counter += 1
        conn_id = self._conn_counter
        conn = SCPIConnection(reader, writer, self.scpi_handler, conn_id)
        self.connections[conn_id] = conn

        try:
            addr = writer.get_extra_info('peername')
            print("Connection {} from {}".format(conn_id, addr))
            await conn.handle()
        finally:
            if conn_id in self.connections:
                del self.connections[conn_id]
            print("Connection {} closed".format(conn_id))

    async def stop(self):
        """Stop the server."""
        self.running = False

        # Close all connections
        for conn in list(self.connections.values()):
            await conn.close()
        self.connections.clear()

        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

    def get_connection_count(self):
        """Get number of active connections."""
        return len(self.connections)


async def run_server(scpi_handler, port=None):
    """
    Run SCPI server (convenience function).

    Args:
        scpi_handler: SCPI command handler
        port: TCP port

    Returns:
        TCPServer instance
    """
    server = TCPServer(scpi_handler, port)
    await server.start()
    return server
