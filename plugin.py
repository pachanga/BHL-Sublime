from __future__ import annotations

from typing import Dict, Optional, Tuple

import sublime
from LSP.plugin import AbstractPlugin, register_plugin, unregister_plugin


class Bhl(AbstractPlugin):

    @classmethod
    def name(cls) -> str:
        return "bhl"

    @classmethod
    def configuration(cls) -> Tuple[sublime.Settings, str]:
        return sublime.load_settings("LSP-bhl.sublime-settings"), "Packages/BHL-Sublime/LSP-bhl.sublime-settings"

    @classmethod
    def additional_variables(cls) -> Dict[str, str]:
        settings = sublime.load_settings("LSP-bhl.sublime-settings")
        executable = settings.get("executablePath") or "bhl"
        force_rebuild = bool(settings.get("forceRebuild", False))
        rebuild = "1" if force_rebuild else ""
        return {
            "bhl": executable,
            "bhl_rebuild": rebuild,
            "bhl_silent": rebuild,
        }

    @classmethod
    def can_start(
        cls,
        window: sublime.Window,
        initiating_view: sublime.View,
        workspace_folders,
        configuration,
    ) -> Optional[str]:
        settings = sublime.load_settings("LSP-bhl.sublime-settings")
        executable = settings.get("executablePath") or "bhl"
        if executable != "bhl":
            import os
            if not os.path.isfile(executable):
                return (
                    f'BHL executable not found at "{executable}". '
                    "Update the executablePath setting."
                )
        return None


def plugin_loaded() -> None:
    register_plugin(Bhl)
    _register_debug_adapter()


def _register_debug_adapter(attempts: int = 0) -> None:
    try:
        from Debugger.modules import dap
    except ImportError:
        print(f"BHL: Debugger not available (attempt {attempts})")
        if attempts < 20:
            sublime.set_timeout(lambda: _register_debug_adapter(attempts + 1), 500)
        return

    print(f"BHL: registering debug adapter (attempt {attempts})")

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

    print(f"BHL: debug adapter registered")


def plugin_unloaded() -> None:
    unregister_plugin(Bhl)
