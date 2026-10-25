# reopen stdout file descriptor with write mode
# and 0 as the buffer size (unbuffered)
import logging
import sys

import f4msgpack

log = logging.getLogger(__name__)
sys.stdin = open(sys.stdin.fileno(), 'rb', 0)
sys.stdout = open(sys.stdout.fileno(), 'wb', 0)

class F4RPCError(Exception):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg
    def __repr__(self):
        return f"F4-RPC Host Error({self.code}) = {self.msg}"

class F4RPC:
    nextID = 1
    SHIFT = 16
    CTRL = 8
    ALT = 2
    def __init__(self):
        self.handlers = {}
        self.pending = {}

    # register maps a method name (e.g. "VFS.ReadDir") to a Lua function.
    def register(self, method, handler):
        self.handlers[method] = handler

    # Internal: Read one complete MessagePack object.
    def read_msg(self):
        # f4msgpack.unpacker needs a function that returns bytes.
        # We use a closure around io.stdin:read(1).
        def readbyte():
            b = sys.stdin.read(1)
            #log.debug("readbyte: %s", b)
            return b
        # unpack_cursor returns (status, result, byte_offset) or just (result)
        # depending on the internal implementation of lua-MessagePack.
        gen = f4msgpack.mp.unpacker(readbyte)
        try:
            first, msg = next(gen)
            log.debug("first:%s msg:%s", first, msg)
        except StopIteration:
            msg = None
        return msg


    # Internal: Route and handle messages.
    def handle_msg(self, msg):
        if msg['t'] == 0:
            log.debug("handle_msg: %s", msg)
            # Request from Core
            handler = self.handlers.get(msg['m'])
            resp = { 't': 1, 'i': msg['i'] }

            if not handler:
                log.debug("no handler for: %s", msg['m'])
                resp['e'] = f"method not found: {msg['m']}"
            else:
                try:
                    res = handler(msg.get('d'))
                    ok = True
                except:
                    log.exception('handler')
                    ok = False
                    res = f"unhandled exception in handler: {msg['m']}"
                if not ok:
                    resp['e'] = str(res)
                else:
                    resp['d'] = res

            log.debug("response: %s", resp)

            sys.stdout.write(f4msgpack.mp.pack(resp))
            sys.stdout.flush()
        elif msg['t'] == 1:
            # Response to a Call we made
            self.pending[msg['i']] = msg

    # call invokes a method on the f4 Core (Host API).
    # This is synchronous: it waits for the response while processing intermediate requests.
    def call(self, method, params):
        id = self.nextID
        self.nextID += 1

        req = {
            't': 0,
            'i': id,
            'm': method,
            'd': params,
        }
        msg = f4msgpack.mp.pack(req)
        sys.stdout.write(msg)
        sys.stdout.flush()

        while True:
            if self.pending.get(id):
                resp = self.pending[id]
                del self.pending[id]
                if resp.get('e') and resp['e']:
                    raise F4RPCError(1, resp.e)
                return resp.get('d')

            try:
                msg = self.read_msg()
            except:
                log.exception('read_msg')
                msg = None
            if not msg:
                raise F4RPCError(2, "Unexpected EOF while waiting for response")
            try:
                self.handle_msg(msg)
            except:
                log.exception('handle_msg')

    # serve enters the main loop, processing requests from f4.
    def serve(self):
        while True:
            msg = self.read_msg()
            if not msg:
                break
            self.handle_msg(msg)
