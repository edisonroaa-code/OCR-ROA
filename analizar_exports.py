"""
ROA OCR - FASE 2: ANALIZAR EXPORTS DE LAS DLLs
Ingeniería inversa del motor OCR
"""
import ctypes
import struct
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def analizar_dll(nombre, ruta):
    print(f"\n{'='*60}")
    print(f"  ANALIZANDO: {nombre}")
    print(f"{'='*60}")
    
    if not os.path.exists(ruta):
        print(f"  ❌ Archivo no encontrado: {ruta}")
        return None
    
    tamano = os.path.getsize(ruta)
    print(f"  Tamaño: {tamano/1024/1024:.1f} MB")
    
    try:
        # Cargar DLL
        dll = ctypes.WinDLL(ruta)
        print(f"  ✅ DLL cargada exitosamente")
        
        # Leer el PE header para extraer exports
        with open(ruta, 'rb') as f:
            data = f.read()
        
        # Buscar la tabla de exportación
        # El offset al PE header está en el DOS header offset 0x3C
        pe_offset = struct.unpack('<I', data[0x3C:0x40])[0]
        
        # PE signature
        if data[pe_offset:pe_offset+4] == b'PE\0\0':
            # Machine + NumberOfSections
            num_sections = struct.unpack('<H', data[pe_offset+6:pe_offset+8])[0]
            
            # Optional header
            optional_header_offset = pe_offset + 24
            magic = struct.unpack('<H', data[optional_header_offset:optional_header_offset+2])[0]
            
            if magic == 0x10b:  # PE32
                data_dir_offset = optional_header_offset + 96
            else:  # PE32+
                data_dir_offset = optional_header_offset + 112
            
            # Export directory is the first data directory entry
            export_rva = struct.unpack('<I', data[data_dir_offset:data_dir_offset+4])[0]
            export_size = struct.unpack('<I', data[data_dir_offset+4:data_dir_offset+8])[0]
            
            if export_rva == 0:
                print(f"  ⚠️  Sin tabla de exportación (puede tener solo ordinales)")
                return dll
            
            # Find the section containing the export directory
            section_offset = pe_offset + 24 + 20  # after optional header
            for i in range(num_sections):
                section_start = section_offset + i * 40
                section_name = data[section_start:section_start+8].rstrip(b'\0').decode('ascii', errors='replace')
                virt_addr = struct.unpack('<I', data[section_start+12:section_start+16])[0]
                virt_size = struct.unpack('<I', data[section_start+8:section_start+12])[0]
                raw_addr = struct.unpack('<I', data[section_start+20:section_start+24])[0]
                
                if virt_addr <= export_rva < virt_addr + virt_size:
                    # Found the section
                    export_file_offset = export_rva - virt_addr + raw_addr
                    
                    # Parse export directory
                    num_functions = struct.unpack('<I', data[export_file_offset+20:export_file_offset+24])[0]
                    num_names = struct.unpack('<I', data[export_file_offset+24:export_file_offset+28])[0]
                    addr_of_functions = struct.unpack('<I', data[export_file_offset+28:export_file_offset+32])[0]
                    addr_of_names = struct.unpack('<I', data[export_file_offset+32:export_file_offset+36])[0]
                    addr_of_ordinals = struct.unpack('<I', data[export_file_offset+36:export_file_offset+40])[0]
                    
                    # Convert RVA to file offsets
                    def rva_to_offset(rva):
                        for j in range(num_sections):
                            s_start = section_offset + j * 40
                            s_va = struct.unpack('<I', data[s_start+12:s_start+16])[0]
                            s_raw = struct.unpack('<I', data[s_start+20:s_start+24])[0]
                            if s_va <= rva < s_va + virt_size:
                                return rva - s_va + s_raw
                        return None
                    
                    names_offset = rva_to_offset(addr_of_names)
                    ordinals_offset = rva_to_offset(addr_of_ordinals)
                    functions_offset = rva_to_offset(addr_of_functions)
                    
                    if names_offset and ordinals_offset and functions_offset:
                        exports = []
                        for j in range(num_names):
                            name_rva = struct.unpack('<I', data[names_offset + j*4:names_offset + j*4+4])[0]
                            ordinal = struct.unpack('<H', data[ordinals_offset + j*2:ordinals_offset + j*2+2])[0]
                            
                            # Get function name
                            name_offset = rva_to_offset(name_rva)
                            if name_offset:
                                name_end = data.find(b'\0', name_offset)
                                func_name = data[name_offset:name_end].decode('ascii', errors='replace')
                                exports.append((ordinal, func_name))
                        
                        print(f"  📤 Funciones exportadas con nombre: {len(exports)}")
                        for ord_num, name in sorted(exports, key=lambda x: x[1]):
                            print(f"     [{ord_num}] {name}")
                    
                    print(f"  📤 Total funciones: {num_functions}")
                    break
            else:
                print(f"  ⚠️  No se encontró la sección de exportación")
        
        return dll
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

# Analizar las DLLs principales
analizar_dll("idrsocr15.dll", os.path.join(BASE, "ER296", "idrsocr15.dll"))
analizar_dll("idrskrn15.dll", os.path.join(BASE, "ER296", "idrskrn15.dll"))
analizar_dll("idrsimp15.dll", os.path.join(BASE, "ER296", "idrsimp15.dll"))
analizar_dll("idrsdocout15.dll", os.path.join(BASE, "ER296", "idrsdocout15.dll"))
analizar_dll("idrsprepro15.dll", os.path.join(BASE, "ER296", "idrsprepro15.dll"))

input("\nPresiona Enter para salir...")
