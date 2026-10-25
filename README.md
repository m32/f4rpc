# f4rpc

[![PyPI version](https://img.shields.io/pypi/v/f4rpc.svg)](https://pypi.org/project/f4rpc/)
[![Python versions](https://img.shields.io/pypi/pyversions/f4rpc)](https://pypi.org/project/f4rpc/)

f4rpc is a library for creating plugins for the F4 file manager.

## Features

- F4RPC: a class with a mechanism for communication via stdin/stdout with F4 file manager

## Installation

Python requirement: **3.11+**

```bash
pip install f4rpc
```

## Quick Start

- Copy the `mydrive-py` directory—which contains the plugin for F4—to any location on your computer (ideally where you store other plugins), and then place the `f4rpc` directory inside it.

- Edit the `manifest.json` file, ensuring that the `entrypoint` parameter correctly points to the `plugin.py` file.

- Grant execution permissions to the `plugin.py` file.

- In the F4 plugin settings, add the plugin and provide the full path to the `plugin.py` file.


## License

MIT

- `LICENSE`
