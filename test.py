import capstone

from pememory import PEMemory
from capstone import *

if __name__ == '__main__':
    #module = "server"
    #game_path = r"E:\Steam\steamapps\common\Counter-Strike Global Offensive\game/"
    #file_path = game_path + r"csgo/bin/win64/" + module + ".dll"
    file_path = r"E:\cs2bins\2024-10-8\server.dll"
    mem = PEMemory(file_path)

    for x in mem.pe.sections:
        print(x.Name.decode('utf-8'))

    sig = "E8 F5 80 20 00"
    fn = mem.sig_scan(sig)
    if fn != PEMemory.INVALID_ADDRESS:
        print(hex(fn))
        jump = mem.resolve_relative_address(fn, 1, 5)
        print(hex(jump))
        ret_bytes = mem.read_address(jump, 16)
        print(PEMemory.to_ida_pattern(ret_bytes))

    addr = mem.get_vtable_by_name("CCSPlayerPawn")
    print(PEMemory.to_ida_pattern(mem.read_address(addr, 16, False)))
    #print(mem.get_vtable_length("CCSPlayerPawn"))

    vtable_fn = mem.get_vtable_func_by_offset("CCSPlayerPawn", 1)
    vtable_fn_end = mem.runtime_functions[vtable_fn]
    vtable_fn2 = mem.get_vtable_func_by_offset("CCSPlayerPawn", 2)
    vtable_fn2_end = mem.runtime_functions[vtable_fn2]
    fn_start_bytes = mem.read_address(vtable_fn, 24, False)
    #print(PEMemory.to_ida_pattern(fn_start_bytes))
    print(mem.sig_maker.make_sig(vtable_fn))

    fn_start_bytes2 = mem.read_address(vtable_fn2, 24, False)
    #print(PEMemory.to_ida_pattern(fn_start_bytes2))
    print(mem.sig_maker.make_sig(vtable_fn2))

    vtable_nullsub = mem.get_vtable_func_by_offset("CCSPlayerPawn", 14)
    print("nullsub: ")
    print(mem.sig_maker.make_sig(vtable_nullsub))

    vtable_noruntime = mem.get_vtable_func_by_offset("CCSPlayerPawn", 92)
    print("vtable_noruntime: ")
    print(mem.sig_maker.make_sig(vtable_noruntime))

    # CODE = fn_start_bytes
    # addr = mem.get_address(vtable_fn)
    #
    # md = Cs(CS_ARCH_X86, CS_MODE_64)
    # md.detail = True
    # instructions = md.disasm(CODE, addr)
    # print(type(instructions))
    # for i in instructions:
    #     print("0x%x:\tmnemonic: %s\top: %s, size: %d" % (i.address, i.mnemonic, i.op_str, i.size))
    #     for x in i.operands:
    #         if isinstance(x, capstone.x86.X86Op):
    #             if x.type == capstone.x86.X86_OP_MEM:  # 检查 x 是否是内存操作数
    #                 mem_operand = x.mem
    #                 print(f"segment: {mem_operand.segment}")
    #                 print(f"base: {mem_operand.base}")
    #                 print(f"index: {mem_operand.index}")
    #                 print(f"scale: {mem_operand.scale}")
    #                 print(f"disp: {mem_operand.disp}")

