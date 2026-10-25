import io
import f4msgpack
mp = f4msgpack.mp

source = '''\
c2                              # False #
c3                              # True #
c0                              # None #
00                              # 0 # Positive FixNum
cc 00                           # 0 # uint8
cd 00 00                        # 0 # uint16
ce 00 00 00 00                  # 0 # uint32
d0 00                           # 0 # int8
d1 00 00                        # 0 # int16
d2 00 00 00 00                  # 0 # int32
ff                              # -1 # Negative FixNum
d0 ff                           # -1 # int8
d1 ff ff                        # -1 # int16
d2 ff ff ff ff                  # -1 # int32
7f                              # 127 # Positive FixNum
cc 7f                           # 127 # uint8
cd 00 ff                        # 255 # uint16
ce 00 00 ff ff                  # 65535 # uint32
e0                              # -32 # Negative FixNum
d0 e0                           # -32 # int8
d1 ff 80                        # -128 # int16
d2 ff ff 80 00                  # -32768 # int32
ca 00 00 00 00                  # 0.0 # float
ca 80 00 00 00                  # -0.0 # float
a1 61                           # "a" # FixStr
d9 01 61                        # "a" # str 8
da 00 01 61                     # "a" # str 16
db 00 00 00 01 61               # "a" # str 32
a0                              # "" # FixStr
d9 00                           # "" # str 8
da 00 00                        # "" # str 16
db 00 00 00 00                  # "" # str 32
c4 01 61                        # "a" # bin 8
c5 00 01 61                     # "a" # bin 16
c6 00 00 00 01 61               # "a" # bin 32
c4 00                           # "" # bin 8
c5 00 00                        # "" # bin 16
c6 00 00 00 00                  # "" # bin 32
91 00                           # [0] # FixArray
dc 00 01 00                     # [0] # array 16
dd 00 00 00 01 00               # [0] # array 32
90                              # [] # FixArray
dc 00 00                        # [] # array 16
dd 00 00 00 00                  # [] # array 32
80                              # {} # FixMap
de 00 00                        # {} # map 16
df 00 00 00 00                  # {} # map 32
81 a1 61 61                     # {"a": 97} # FixMap
de 00 01 a1 61 61               # {"a": 97} # map 16
df 00 00 00 01 a1 61 61         # {"a": 97} # map 32
91 90                           # [[]] #
91 91 a1 61                     # [["a"]] #

d4 01 01                        # # fixext 1
d5 02 02 01                     # # fixext 2
d6 04 04 03 02 01               # # fixext 4
d7 08 08 07 06 05 04 03 02 01   # # fixext 8
d8 16 10 0f 0e 0d 0c 0b 0a 09 08 07 06 05 04 03 02 01   # # fixext 16
c7 01 08 61                     # # ext 8
c8 00 01 16 61                  # # ext 16
c9 00 00 00 01 32 61            # # ext 32
# 64-bit
cf 00 00 00 00 00 00 00 00      # 0 # uint64
d3 00 00 00 00 00 00 00 00      # 0 # int64
d3 ff ff ff ff ff ff ff ff      # -1 # int64
cf 00 00 00 00 ff ff ff ff      # 4294967295 # uint64
d3 ff ff ff ff 80 00 00 00      # -2147483648 # int64
cb 00 00 00 00 00 00 00 00      # 0.0 # double
cb 80 00 00 00 00 00 00 00      # -0.0 # double
cb 3f f0 00 00 00 00 00 00      # 1.0 # double
cb bf f0 00 00 00 00 00 00      # -1.0 # double
'''

def check():
    lines = io.StringIO(source)
    for line in lines:
        line = line.strip()
        if not line or line[0] == '#':
            continue
        data, cmt, ext = line.split('#')
        t = [int(v, 16) for v in data.split()]
        mpac = bytes(t)
        for ok, val in mp.unpacker(mpac):
            print(ok, data, val, '=>', cmt, ext, '<=', ' '.join(hex(x) for x in mp.pack(val)))

print('*'*20, "blank")
check()

print('*'*20, "set_string 'string'")
mp.set_string('string')
check()

print('*'*20, "set_string 'binary'")
mp.set_string('binary')
check()

print('*'*20, "set_string 'compat'")
mp.set_string('compat')
check()

print('*'*20, "set_integer 'signed'")
mp.set_integer('signed')
check()

print('*'*20, "set_integer 'unsigned'")
mp.set_integer('unsigned')
check()

print('*'*20, "set_number 'float'")
mp.set_number('float')
check()

print('*'*20, "set_array 'with_hole'")
mp.set_array('with_hole')
check()

print('*'*20, "set_array 'without_hole'")
mp.set_array('without_hole')
check()

print('*'*20, "set_array 'always_as_map'")
mp.set_array('always_as_map')
check()
