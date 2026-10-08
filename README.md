# BHL Sublime Text Package

Sublime Text package providing BHL language support via the Language Server Protocol.

## Requirements

You need the **[LSP](https://packagecontrol.io/packages/LSP)** package installed via Package Control.

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

## BHL language server

The BHL language server is a prebuilt binary from the
[BHL GitHub releases](https://github.com/bitdotgames/BHL/releases) (`lsp-v*` tags). To install, switch to
another version, or remove the download, run **BHL: Manage LSP Versions** from the Command Palette and pick a
release. After installing, reopen the file or run **LSP: Restart Server**.

The first time you open a `.bhl` file and no server is found, the package also offers to download the latest
release for you. Installed versions are never updated automatically.

Downloads are verified against the release's `.sha256` checksum and stored in Sublime's `Package Storage`.

Prefer your own build? Set `executablePath` (see [Configuration](#configuration)) to a `bhl` script from a
[BHL checkout](https://github.com/bitdotgames/BHL) and it will be launched as `bhl lsp` instead.

## Configuration

Open the settings via **Preferences → Package Settings → BHL → Settings** or the Command Palette (**Preferences: BHL Settings**). They live in `Packages/User/LSP-bhl.sublime-settings`, which you can also create by hand to override defaults. The `Packages` directory is at:

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Sublime Text/Packages/` |
| Windows | `%APPDATA%\Sublime Text\Packages\` |
| Linux | `~/.config/sublime-text/Packages/` |

You can also open it via **Preferences → Browse Packages…** in Sublime Text.

| Setting | Default | Description |
|---|---|---|
| `executablePath` | `""` | Path to a custom `bhl` executable. When set, it overrides the downloaded release. Leave empty to use the downloaded release (or `bhl` from `PATH` if none). On Windows use the `.bat` path, e.g. `C:\BHL\bhl.bat`. |
| `forceRebuild` | `false` | Forces LSP server rebuild on startup by setting `BHL_REBUILD=1`. Only meaningful with a custom `bhl` script from a BHL checkout (`executablePath`); useful during active development of an LSP server. |

For example, to use your own BHL checkout instead of the downloaded release:

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

> Sublime Text 4213+ runs plugins on Python 3.14, which Debugger 0.11.6 and older do not support (`RuntimeError: loop … is not the running loop`). Use a newer release (the adapter was checked against 0.12.1), or install Debugger from the `master` branch of [daveleroy/SublimeDebugger](https://github.com/daveleroy/SublimeDebugger) via `git clone` into `Packages/`.

### Setup

A configuration can live in either of two places. Run **Debugger: Add Configuration**, pick `bhl`, then
**BHL: Attach to Debug Server** to insert one into your `.sublime-project` automatically, or write it by hand.

**Per project** — add a `debugger_configurations` entry to your `.sublime-project` file:

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

**Globally** — to have the same configuration in every project (including a lone `.bhl` file with no saved
project), add it to `global_debugger_configurations` in `Packages/User/Debugger.sublime-settings` (open it via
**Preferences → Package Settings → Debugger → Settings**):

```json
{
    "global_debugger_configurations": [
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

Open any `.bhl` file. The package finds the `bhl.proj` for it and starts the language server with that
directory as its root: first the nearest `bhl.proj` in the file's parent directories, otherwise the only
`bhl.proj` found under the folders open in the window. If there are several and none is above the file, the
server falls back to indexing just the file's directory.

To choose explicitly, run **BHL: Select Project File** from the Command Palette: pick one of the found
`bhl.proj` files or browse for one. The server restarts with that project for the current window. The
choice lasts until Sublime exits; pick **Automatic** to go back to detection.

If everything is correct you should see **"Indexing BHL scripts"** in the status bar.
