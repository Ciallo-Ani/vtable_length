import pefile
import capstone

class PEMemory:
    INVALID_ADDRESS = -1

    def __init__(self, file_path: str):
        self.pe = pefile.PE(file_path, fast_load=True)
        self.sig_maker = SigMaker(self.pe)
        # vtable_name : [address]
        self.vtable_cache = {}

    @staticmethod
    def to_ida_pattern(byte_list) -> str:
        if isinstance(byte_list, list):
            return " ".join(f"{int(x, 16):02X}" for x in byte_list)
        return " ".join(f"{x:02X}" for x in byte_list)

    def get_address(self, offset: int, section: pefile.SectionStructure = None):
        if section is not None:
            return self.get_address_with_section(offset, section)

        for section in self.pe.sections:
            section_start = section.VirtualAddress
            section_end = section.VirtualAddress + section.Misc_VirtualSize
            target_addr = section_start + offset
            if section_start <= target_addr < section_end:
                return target_addr
        return PEMemory.INVALID_ADDRESS

    def get_address_with_section(self, offset: int, section: pefile.SectionStructure):
        section_start = section.VirtualAddress
        section_end = section.VirtualAddress + section.Misc_VirtualSize
        target_addr = section_start + offset
        if section_start <= target_addr < section_end:
            return target_addr
        return PEMemory.INVALID_ADDRESS

    def read_address(self, addr: int, bytes_to_read: int = 8, cast_list: bool = True):
        for section in self.pe.sections:
            section_start = section.VirtualAddress
            section_end = section.VirtualAddress + section.Misc_VirtualSize
            if section_start <= addr < section_end:
                offset = addr - section_start
                section_data = section.get_data()
                if offset < len(section_data):
                    return [hex(byte) for byte in section_data[offset: offset + bytes_to_read]] if cast_list \
                        else section_data[offset: offset + bytes_to_read]
                else:
                    return None
        return None

    def get_section(self, name: str):
        for section in self.pe.sections:
            section_name = section.Name.decode('utf-8').rstrip('\x00')
            if section_name == name:
                return section
        return None

    def resolve_relative_address(self, addr: int, offset_register=0x3, offset_next_instruction=0x7) -> int:
        skip_register = addr + offset_register
        relative_addr = int.from_bytes(self.read_address(skip_register, 4, False), byteorder='little')
        next_instruction = addr + offset_next_instruction
        return next_instruction + relative_addr

    def sig_scan(self, sig: str) -> int:
        byte_array = bytes.fromhex(sig)
        for section in self.pe.sections:
            section_data = section.get_data()
            offset = section_data.find(byte_array)
            if offset != -1:
                return section.VirtualAddress + offset
        return PEMemory.INVALID_ADDRESS

    def find_pattern_by_str(self, pattern: str, section: pefile.SectionStructure) -> int:
        encoded_pattern = pattern.encode('utf-8')
        offset = section.get_data().find(encoded_pattern)
        if offset == -1:
            return PEMemory.INVALID_ADDRESS
        return self.get_address(offset, section)

    def find_pattern_by_bytes(self, pattern: bytes, section: pefile.SectionStructure, start_offset: int = 0) -> int:
        offset = section.get_data().find(pattern, start_offset)
        if offset == -1:
            return PEMemory.INVALID_ADDRESS
        return self.get_address(offset, section)

    def get_vtable_by_name(self, vtable_name: str, decorated: bool = False):
        if len(vtable_name) == 0:
            return PEMemory.INVALID_ADDRESS

        runtime_data = self.get_section(".data")
        if runtime_data is None:
            return PEMemory.INVALID_ADDRESS

        readonly_data = self.get_section(".rdata")
        if readonly_data is None:
            return PEMemory.INVALID_ADDRESS

        decorated_table_name = vtable_name if decorated \
            else ".?AV" + vtable_name + "@@"

        type_descriptor_name = self.find_pattern_by_str(decorated_table_name, runtime_data)
        rtti_type_descriptor = type_descriptor_name - 0x10
        rtti_type_descriptor_bytes = rtti_type_descriptor.to_bytes(4, byteorder='little')

        reference = 0
        while (reference := self.find_pattern_by_bytes(rtti_type_descriptor_bytes, readonly_data,
                                                       reference)) != PEMemory.INVALID_ADDRESS:
            val1 = int(self.read_address(reference - 0xC, 1)[0], 16)
            val2 = int(self.read_address(reference - 0x8, 1)[0], 16)
            if val1 == 1 and val2 == 0:
                offset_reference = reference - 0xC + self.pe.OPTIONAL_HEADER.ImageBase
                offset_reference_bytes = offset_reference.to_bytes(8, byteorder='little')
                rtti_complete_object_locator = self.find_pattern_by_bytes(offset_reference_bytes, readonly_data)
                if rtti_complete_object_locator != PEMemory.INVALID_ADDRESS:
                    return rtti_complete_object_locator + 0x8
            reference = reference + 0x4

    def is_valid_vtable_function(self, vtable_fn: int) -> bool:
        if int(self.read_address(vtable_fn)[7], 16) != 0x00:
            return False

        fn_start = int.from_bytes(self.read_address(vtable_fn, cast_list=False),
                                  byteorder='little') - self.pe.OPTIONAL_HEADER.ImageBase
        if int(self.read_address(fn_start, 1)[0], 16) >= 0x0F:
            return True

        return False

    def get_vtable_length(self, vtable_name: str):
        if vtable_name in self.vtable_cache:
            return len(self.vtable_cache[vtable_name])

        fn = self.get_vtable_by_name(vtable_name)
        if fn == PEMemory.INVALID_ADDRESS:
            return -1

        count = 0
        vtable_fns = []
        while self.is_valid_vtable_function(fn):
            vtable_fns.append(fn)
            count += 1
            fn += 8

        self.vtable_cache[vtable_name] = vtable_fns
        return count

    def get_vtable_func_by_offset(self, vtable_name: str, target_offset: int, use_dq_offset: bool = True):
        vtable_len = self.get_vtable_length(vtable_name)
        if target_offset < 0 or target_offset > vtable_len:
            return PEMemory.INVALID_ADDRESS

        fn = self.vtable_cache[vtable_name][target_offset]
        if use_dq_offset:
            dq_offset = int.from_bytes(self.read_address(fn, cast_list=False), byteorder='little')
            return dq_offset - self.pe.OPTIONAL_HEADER.ImageBase
        return fn


class SigMaker:
    def __init__(self, pe: pefile.PE):
        self.pe = pe
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
