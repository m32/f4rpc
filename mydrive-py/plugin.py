#!/usr/bin/env python3
import logging
import os

logging.basicConfig(
    filename='/tmp/f4-mydrive-py.log',
    filemode='a',
    format='%(asctime)s,%(msecs)03d %(name)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.DEBUG)

log = logging.getLogger(__name__)
log.debug('start')


from f4rpc import F4RPC

DRIVE = "mydrive-py"

# The contents of the drive, in the order the panel shows them.
files = [
  { "name": "hello.txt", "body": "Hello from mydrive.\n" },
  { "name": "notes.txt", "body": b"Edit plugin.py and restart f4 to see this change.\n" },
]

byName = { rec["name"]:rec for rec in files }

# Plugin.Init is the first thing f4 asks. The drives named here appear in the
# drive menu, on Alt+F1 and Alt+F2.
class Plugin(F4RPC):
    def __init__(self):
        super().__init__()

        # -- Open file handles, so that a read knows which file it belongs to.
        self.handles = {}
        self.nextHandle = 1

        self.register("Plugin.Init", self.Plugin_Init)
        self.register("VFS.ReadDir", self.VFS_ReadDir)
        self.register("VFS.Open", self.VFS_Open)
        self.register("VFS.ReadAt", self.VFS_ReadAt)
        self.register("VFS.CloseFile", self.VFS_CloseFile)

    def Plugin_Init(self, req):
        self.call("Host.Log", DRIVE +" loaded")
        return { "Drives": [DRIVE] }

    def VFS_ReadDir(self, req):
        result = []
        for rec in files:
            result.append({
                "Name": rec['name'],
                "Size": len(rec["body"]),
                "IsDir": False
            })
        return result

    def VFS_Open(self, req):
        name = os.path.basename(req["Path"])
        rec = byName.get(name)
        if not rec:
            raise IOError(1, f"no such file: {req['Path']}")
        id = self.nextHandle
        self.nextHandle += 1
        self.handles[id] = rec['body']
        return { "ID": id, "Size": len(rec['body']) }

    def VFS_ReadAt(self, req):
        body = self.handles.get(req['ID']) or ""
        return body[req['Off'] : req['Off'] + req['Len']]

    def VFS_CloseFile(self, req):
        del self.handles[req['ID']]

# Out of process this enters the read loop; embedded it does nothing. Leave
# it in, and the same file works either way.
log.debug('plugin')
cls = Plugin()
log.debug('serve')
cls.serve()
log.debug('done')
