# Builds a COFF .syso with RT_ICON/RT_GROUP_ICON, RT_MANIFEST and RT_VERSION for the Go linker.
import struct, sys
ico_path, manifest_path, out, version, desc, origname = sys.argv[1:7]

def ico_entries(path):
    d = open(path, "rb").read()
    _, typ, n = struct.unpack_from("<HHH", d, 0)
    ents = []
    for i in range(n):
        w,h,cc,res,planes,bpp,size,off = struct.unpack_from("<BBBBHHII", d, 6+16*i)
        ents.append(((w,h,cc,res,planes,bpp,size), d[off:off+size]))
    return ents

def vs_version(version, desc, origname=origname):
    parts = [int(x) for x in version.split(".")] + [0]*4
    ms = (parts[0]<<16)|parts[1]; ls = (parts[2]<<16)|parts[3]
    def s(x): return (x+"\0").encode("utf-16-le")
    def pad(b): return b + b"\0"*((4-len(b)%4)%4)
    def block(key, value=b"", children=b"", vtype=1, vlen=None):
        hdr_key = pad(struct.pack("<HHH",0,0,0)+s(key))
        body = hdr_key + (pad(value) if value else b"") + children
        if vlen is None: vlen = len(value)//2 if vtype==1 else len(value)
        return pad(struct.pack("<HHH", len(body), vlen, vtype) + body[6:])
    def strv(k, v): 
        vb = s(v); return block(k, vb, vtype=1, vlen=len(vb)//2)
    strings = [("CompanyName","MeuLauncher"),("FileDescription",desc),("FileVersion",version),
               ("InternalName",origname.rsplit(".",1)[0]),("LegalCopyright",""),("OriginalFilename",origname),
               ("ProductName","MeuLauncher"),("ProductVersion",version)]
    st = block("041604b0", children=b"".join(strv(k,v) for k,v in strings))
    sfi = block("StringFileInfo", children=st)
    var = block("Translation", struct.pack("<HH",0x0416,1200), vtype=0, vlen=4)
    vfi = block("VarFileInfo", children=var)
    ffi = struct.pack("<13I", 0xFEEF04BD, 0x10000, ms, ls, ms, ls, 0x3F, 0, 0x40004, 1, 0, 0, 0)
    return block("VS_VERSION_INFO", ffi, children=sfi+vfi, vtype=0, vlen=len(ffi))

ents = ico_entries(ico_path)
res = {}  # type -> {id: data}
res[3] = {i+1: data for i,(_,data) in enumerate(ents)}
grp = struct.pack("<HHH",0,1,len(ents))
for i,((w,h,cc,r,pl,bpp,size),_) in enumerate(ents):
    grp += struct.pack("<BBBBHHIH", w,h,cc,r,pl,bpp,size,i+1)
res[14] = {1: grp}
res[24] = {1: open(manifest_path,"rb").read()}
res[16] = {1: vs_version(version, desc)}
LANG = 0x0409

types = sorted(res)
# layout: root dir, type dirs, name dirs, data entries, data
dir_sz = lambda n: 16 + 8*n
off = dir_sz(len(types))
type_off = {}
for t in types: type_off[t] = off; off += dir_sz(len(res[t]))
name_off = {}
for t in types:
    for i in sorted(res[t]): name_off[(t,i)] = off; off += dir_sz(1)
de_off = {}
for t in types:
    for i in sorted(res[t]): de_off[(t,i)] = off; off += 16
data_off = {}
for t in types:
    for i in sorted(res[t]):
        off = (off+7)&~7; data_off[(t,i)] = off; off += len(res[t][i])
buf = bytearray(off)
def wdir(at, entries):
    struct.pack_into("<IIHHHH", buf, at, 0,0,0,0,0,len(entries))
    for k,(eid,target) in enumerate(entries):
        struct.pack_into("<II", buf, at+16+8*k, eid, target)
wdir(0, [(t, 0x80000000|type_off[t]) for t in types])
relocs = []
for t in types:
    wdir(type_off[t], [(i, 0x80000000|name_off[(t,i)]) for i in sorted(res[t])])
    for i in sorted(res[t]):
        wdir(name_off[(t,i)], [(LANG, de_off[(t,i)])])
        struct.pack_into("<IIII", buf, de_off[(t,i)], data_off[(t,i)], len(res[t][i]), 0, 0)
        relocs.append(de_off[(t,i)])
        buf[data_off[(t,i)]:data_off[(t,i)]+len(res[t][i])] = res[t][i]
raw_ptr = 20 + 40
rel_ptr = raw_ptr + len(buf)
sym_ptr = rel_ptr + 10*len(relocs)
o = bytearray()
o += struct.pack("<HHIIIHH", 0x8664, 1, 0, sym_ptr, 1, 0, 0)
o += struct.pack("<8sIIIIIIHHI", b".rsrc", 0, 0, len(buf), raw_ptr, rel_ptr, 0, len(relocs), 0, 0x40000040)
o += buf
for r in relocs: o += struct.pack("<IIH", r, 0, 3)  # IMAGE_REL_AMD64_ADDR32NB
o += struct.pack("<8sIhHBB", b".rsrc", 0, 1, 0, 3, 0)
o += struct.pack("<I", 4)
open(out,"wb").write(o)
print("syso", len(o), "bytes")
