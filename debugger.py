from __future__ import annotations


def plugin_loaded() -> None:
    try:
        from Debugger import dap
    except ImportError:
        return  # Debugger package not installed — skip silently

    class BhlDebugAdapter(dap.AdapterConfiguration):
        type = "bhl"

        @property
        def configuration_snippets(self):
            return [
                {
                    "label": "BHL: Attach to Debug Server",
                    "description": "Attach to a running BHL debug server (e.g. inside Unity)",
                    "body": {
                        "type": "bhl",
                        "request": "attach",
                        "name": "Attach to BHL",
                        "host": "localhost",
                        "port": 7777,
                        "timeout": 30,
                    },
                }
            ]

        async def start(self, log, configuration):
            host = configuration.get("host") or "localhost"
            port = configuration["port"]
            timeout = configuration.get("timeout") or 30
            log.info(f"Connecting to BHL debug server on {host}:{port}")
            return dap.SocketTransport(host=host, port=port, timeout=timeout)
