# SCPI Command Parser
# Parses SCPI command strings into structured commands

import re


class SCPICommand:
    """Represents a parsed SCPI command."""

    def __init__(self, command_str):
        """
        Parse SCPI command string.

        Args:
            command_str: Raw SCPI command string
        """
        self.raw = command_str.strip()
        self.is_query = self.raw.endswith('?')
        self.keywords = []
        self.channel = None
        self.parameter = None

        self._parse()

    def _parse(self):
        """Parse command into components."""
        cmd = self.raw

        # Remove query marker for parsing
        if self.is_query:
            cmd = cmd[:-1]

        # Split into command and parameter
        parts = cmd.split(None, 1)  # Split on first whitespace
        cmd_part = parts[0] if parts else ""
        self.parameter = parts[1].strip() if len(parts) > 1 else None

        # Split command into keywords
        if cmd_part.startswith('*'):
            # Common command (*IDN?, *RST, etc.)
            self.keywords = [cmd_part.upper()]
        else:
            # Hierarchical command (MEAS:POW1?)
            self.keywords = [k.upper() for k in cmd_part.split(':')]

        # Extract channel number from last keyword
        self._extract_channel()

    def _extract_channel(self):
        """Extract channel number from command keywords."""
        if not self.keywords:
            return

        last_kw = self.keywords[-1]

        # Check for numeric suffix (POW1, POW2)
        if last_kw and last_kw[-1].isdigit():
            self.channel = int(last_kw[-1])
            # Store keyword without channel suffix
            self.keywords[-1] = last_kw[:-1]

    def match(self, pattern):
        """
        Check if command matches pattern.

        Pattern format: "MEAS:POW" or "MEASure:POWer" (short:long forms)
        Uses standard SCPI matching rules.

        Args:
            pattern: Command pattern to match

        Returns:
            True if command matches pattern
        """
        pattern_parts = pattern.upper().split(':')

        if len(self.keywords) != len(pattern_parts):
            return False

        for kw, pat in zip(self.keywords, pattern_parts):
            if not self._keyword_match(kw, pat):
                return False

        return True

    def _keyword_match(self, keyword, pattern):
        """
        Match keyword against pattern using SCPI rules.

        SCPI allows abbreviation to minimum unambiguous form.
        Convention: uppercase letters are required, lowercase optional.
        e.g., "MEASure" matches "MEAS", "MEASU", "MEASUR", "MEASURE"
        """
        # Extract required part (uppercase in pattern)
        required = ''.join(c for c in pattern if c.isupper())
        full = pattern.upper()

        kw = keyword.upper()

        # Check if keyword matches required prefix and is prefix of full
        if len(kw) < len(required):
            return False

        if not full.startswith(kw):
            return False

        return True

    def get_param_float(self, default=None):
        """Get parameter as float."""
        if self.parameter is None:
            return default
        try:
            return float(self.parameter)
        except ValueError:
            return default

    def get_param_int(self, default=None):
        """Get parameter as integer."""
        if self.parameter is None:
            return default
        try:
            return int(float(self.parameter))
        except ValueError:
            return default

    def get_param_str(self, default=None):
        """Get parameter as string."""
        if self.parameter is None:
            return default
        return self.parameter.strip()

    def __repr__(self):
        return "SCPICommand({!r}, query={}, channel={}, param={!r})".format(
            ':'.join(self.keywords), self.is_query, self.channel, self.parameter
        )


class SCPIParser:
    """SCPI command parser and dispatcher."""

    def __init__(self):
        """Initialize parser with empty command registry."""
        self.commands = {}
        self.error_queue = []

    def register(self, pattern, handler, query_handler=None):
        """
        Register command handler.

        Args:
            pattern: Command pattern (e.g., "MEASure:POWer")
            handler: Function to call for command
            query_handler: Function to call for query (optional)
        """
        key = pattern.upper()
        self.commands[key] = {
            'pattern': pattern,
            'handler': handler,
            'query_handler': query_handler or handler,
        }

    def parse(self, command_str):
        """
        Parse command string.

        Args:
            command_str: SCPI command string

        Returns:
            SCPICommand instance
        """
        return SCPICommand(command_str)

    def execute(self, command_str):
        """
        Parse and execute SCPI command.

        Args:
            command_str: SCPI command string

        Returns:
            Response string or None
        """
        try:
            cmd = self.parse(command_str)

            # Find matching handler
            for key, entry in self.commands.items():
                if cmd.match(entry['pattern']):
                    handler = entry['query_handler'] if cmd.is_query else entry['handler']
                    return handler(cmd)

            # No match found
            self.add_error(-100, "Command error: Unknown command")
            return None

        except Exception as e:
            self.add_error(-200, "Execution error: {}".format(e))
            return None

    def add_error(self, code, message):
        """Add error to queue."""
        self.error_queue.append((code, message))
        # Limit queue size
        if len(self.error_queue) > 10:
            self.error_queue.pop(0)

    def get_error(self):
        """Get and remove oldest error."""
        if self.error_queue:
            code, msg = self.error_queue.pop(0)
            return "{},\"{}\"".format(code, msg)
        return "0,\"No error\""

    def clear_errors(self):
        """Clear error queue."""
        self.error_queue.clear()
