# BHL Sublime Text Package

Sublime Text package providing BHL language support via the Language Server Protocol.

## Requirements

You need to have the BHL LSP server available. Clone the [BHL repository](https://github.com/bitdotgames/BHL) to some directory and point the package at the `bhl` script (or `bhl.bat` on Windows). The package launches it as `path/to/BHL/bhl lsp` to start the language server.

You also need the **[LSP](https://packagecontrol.io/packages/LSP)** package installed via Package Control.

## Installation

### From GitHub Releases (recommended)

1. Download the latest `BHL-Sublime.sublime-package` from [Releases](../../releases).
2. Copy it into your Sublime Text `Installed Packages` folder:

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Sublime Text/Installed Packages/` |
| Windows | `%APPDATA%\Sublime Text\Installed Packages\` |
| Linux | `~/.config/sublime-text/Installed Packages/` |

Sublime Text picks it up automatically — no restart needed.

### Via command line (macOS)

```sh
cp BHL-Sublime.sublime-package ~/Library/Application\ Support/Sublime\ Text/Installed\ Packages/
```

Or use the Makefile:

```sh
make install
```

## Configuration

Create `Packages/User/LSP-bhl.sublime-settings` to override defaults. The `Packages` directory is at:

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Sublime Text/Packages/` |
| Windows | `%APPDATA%\Sublime Text\Packages\` |
| Linux | `~/.config/sublime-text/Packages/` |

You can also open it via **Preferences → Browse Packages…** in Sublime Text.

| Setting | Default | Description |
|---|---|---|
| `executablePath` | `""` | Path to the `bhl` executable. Leave empty to use `bhl` from `PATH`. On Windows use the `.bat` path, e.g. `C:\BHL\bhl.bat`. |
| `forceRebuild` | `false` | Forces LSP server rebuild on startup by setting `BHL_REBUILD=1`. Useful during active development of an LSP server. |

```json
// Packages/User/LSP-bhl.sublime-settings
{
    "executablePath": "/Users/bob/BHL/bhl",
    "forceRebuild": false
}
```

### Enabling debug logging

Add `--log-file=/tmp/bhlsp.log` to the `command` array:

```json
{
    "executablePath": "/Users/bob/BHL/bhl",
    "command": ["${bhl}", "lsp", "--log-file=/tmp/bhlsp.log"]
}
```

### Enabling semantic highlighting

Add `"semantic_highlighting": true` to your LSP package settings
(**Preferences → Package Settings → LSP → Settings**):

```json
{
    "semantic_highlighting": true
}
```

## Debugging

BHL debugging requires the **[Debugger](https://packagecontrol.io/packages/Debugger)** package installed via Package Control. The BHL debug adapter is bundled in this package and registers with Debugger automatically on startup — no extra configuration is needed.

### Setup

Add a `debugger_configurations` entry to your `.sublime-project` file:

```json
{
    "folders": [
        { "path": "." }
    ],
    "debugger_configurations": [
        {
            "type": "bhl",
            "request": "attach",
            "name": "Attach to BHL",
            "host": "localhost",
            "port": 7777,
            "timeout": 30
        }
    ]
}
```

| Option | Default | Description |
|---|---|---|
| `host` | `"localhost"` | Host where the BHL debug server is running |
| `port` | — | Port the BHL debug server listens on (required) |
| `timeout` | `30` | Seconds to wait for the debug server to become available |

### Usage

1. Start your Unity game — the BHL debug server begins listening on the configured port.
2. Open the Debugger panel: **Debugger → Open**.
3. Select **Attach to BHL** from the configuration list and press **Run**.
4. Set breakpoints by clicking the gutter in any `.bhl` file.

## Usage

Start using the package by opening the directory which contains the **bhl.proj** file
(**Project → Add Folder to Project…**). It must appear as a separate folder entry in the
sidebar. Try opening any `.bhl` file — if everything is correct you should see
**"Indexing BHL scripts"** in the status bar.
