import sqlite3

glossary = [
    # CPU
    ("Procesador: Pines doblados o rotos", "cpu, pines, doblados, rotos, pga, amd", "Daño físico en los conectores del procesador (común en procesadores PGA como los antiguos AMD Ryzen) que impide que encaje o funcione.", "Procesador (CPU)"),
    ("Procesador: Sobrecalentamiento (Thermal Throttling)", "cpu, sobrecalentamiento, thermal throttling, calor, temperatura", "El procesador reduce drásticamente su velocidad para evitar derretirse debido a una mala disipación de calor.", "Procesador (CPU)"),
    ("Procesador quemado", "cpu, quemado, voltaje, fuente", "Daño irreversible por un pico de voltaje extremo o fallo catastrófico de la fuente de alimentación.", "Procesador (CPU)"),
    ("Procesador: Gráficos integrados corruptos", "cpu, graficos, integrados, igpu, video, bsod", "Fallo en la sección del chip que maneja el video (si tiene iGPU), causando pantallas negras o pantallazos azules.", "Procesador (CPU)"),
    ("Procesador: Fallo de memoria caché", "cpu, cache, memoria, cuelgues", "Errores internos en la memoria del procesador que provocan cuelgues constantes del sistema.", "Procesador (CPU)"),
    
    # Motherboard
    ("Tarjeta Madre: Condensadores hinchados o reventados", "motherboard, placa base, condensadores, capacitores, hinchados", "Capacitores que han perdido su líquido electrolítico, causando inestabilidad en la energía que llega a los componentes.", "Tarjeta Madre (Motherboard)"),
    ("Tarjeta Madre: Pines del socket doblados", "motherboard, placa base, pines, socket, intel, am5", "Daño en los pines de la placa base (común en placas Intel y nuevas AMD AM5), lo que impide que el procesador haga contacto correctamente.", "Tarjeta Madre (Motherboard)"),
    ("Tarjeta Madre: Cortocircuito en el VRM", "motherboard, vrm, cortocircuito, voltaje", "Fallo en los módulos de regulación de voltaje, lo que a menudo impide que la computadora encienda o quema el procesador.", "Tarjeta Madre (Motherboard)"),
    ("Tarjeta Madre: Corrupción de BIOS/UEFI", "motherboard, bios, uefi, corrupcion, brickeada", "El software base de la placa se daña (por ejemplo, durante una actualización fallida), dejando la placa inoperativa ('brickeada').", "Tarjeta Madre (Motherboard)"),
    ("Tarjeta Madre: Puertos o ranuras defectuosas", "motherboard, puertos, ram, pcie, usb, sata", "Fallos físicos o lógicos en ranuras de RAM, puertos PCIe, puertos USB o conectores SATA.", "Tarjeta Madre (Motherboard)"),

    # RAM
    ("Memoria RAM: Contactos sucios u oxidados", "ram, sucios, oxidados, pines, estatica", "Acumulación de polvo o estática en los pines dorados que impide que la placa base reconozca el módulo.", "Memoria RAM"),
    ("Memoria RAM: Errores de direccionamiento (Sectores defectuosos)", "ram, sectores, bsod, pantallazo azul", "Fallo físico en los chips de memoria que corrompe los datos y suele ser la causa principal de los temidos 'Pantallazos Azules' (BSOD).", "Memoria RAM"),
    ("Memoria RAM: Inestabilidad por perfil XMP/EXPO", "ram, xmp, expo, inestabilidad, reinicios", "Incapacidad de la memoria o del controlador de la CPU para mantener las velocidades publicitadas, causando reinicios aleatorios.", "Memoria RAM"),
    ("Memoria RAM: Módulo muerto (No POST)", "ram, muerta, no post, pitidos", "La memoria falla por completo y la computadora emite pitidos o enciende luces de error sin dar video.", "Memoria RAM"),

    # GPU
    ("Tarjeta Gráfica: Artefactos visuales (Artifacting)", "gpu, grafica, artefactos, video, vram", "Aparición de cuadros de colores, líneas extrañas o destellos en la pantalla, generalmente indicando que la memoria VRAM o el chip gráfico están fallando.", "Tarjeta Gráfica (GPU)"),
    ("Tarjeta Gráfica: Ventiladores averiados", "gpu, ventiladores, sobrecalentamiento", "Los ventiladores dejan de girar debido a rodamientos desgastados, lo que lleva a un sobrecalentamiento rápido.", "Tarjeta Gráfica (GPU)"),
    ("Tarjeta Gráfica: Ruido eléctrico (Coil Whine)", "gpu, coil whine, ruido, zumbido", "Un zumbido o chillido agudo proveniente de las bobinas de la tarjeta cuando está bajo mucha carga de trabajo.", "Tarjeta Gráfica (GPU)"),
    ("Tarjeta Gráfica: Conector PCIe quemado o dañado", "gpu, pcie, quemado, 12vhpwr, derretido", "Daño en la conexión a la placa base o en los puertos de alimentación (como los cables de 12VHPWR que se derriten por mala conexión).", "Tarjeta Gráfica (GPU)"),
    ("Tarjeta Gráfica: Soldadura fría", "gpu, soldadura, fria, reballing", "Microfracturas en las soldaduras del chip gráfico debido a los constantes cambios de temperatura, lo que requiere un 'Reballing' para solucionarse.", "Tarjeta Gráfica (GPU)"),

    # Storage
    ("HDD: Clic de la muerte", "hdd, disco duro, clic, atascado, cabezal", "Un sonido metálico repetitivo que indica que el cabezal de lectura/escritura está chocando o atascado.", "Almacenamiento"),
    ("HDD: Sectores defectuosos", "hdd, disco duro, sectores, lento, corruptos", "Áreas del disco magnético que ya no pueden retener datos, causando archivos corruptos o un sistema operativo extremadamente lento.", "Almacenamiento"),
    ("HDD: Fallo del motor", "hdd, disco duro, motor, girar", "Los platos del disco dejan de girar.", "Almacenamiento"),
    ("SSD: Desgaste de celdas NAND", "ssd, estado solido, nand, lectura", "La unidad ha alcanzado su límite de ciclos de escritura y entra en modo de 'solo lectura' para evitar la pérdida de datos.", "Almacenamiento"),
    ("SSD: Fallo del controlador", "ssd, controlador, raw, formato", "El chip que organiza los datos se estropea, lo que hace que la unidad desaparezca repentinamente del sistema operativo o pida ser formateada (formato RAW).", "Almacenamiento"),
    ("SSD: Sobrecalentamiento (NVMe)", "ssd, nvme, m2, calor, disipador", "Disminución severa de la velocidad de transferencia porque el SSD M.2 se calienta demasiado al no tener disipador.", "Almacenamiento"),

    # PSU
    ("Fuente de Alimentación: Apagados repentinos bajo carga", "psu, fuente, apagados, carga", "La fuente no puede entregar la energía necesaria cuando la CPU y GPU trabajan al máximo, activando sus protecciones y apagando la PC.", "Fuente de Alimentación (PSU)"),
    ("Fuente de Alimentación: Voltaje inestable (Rizado alto)", "psu, fuente, voltaje, rizado", "La fuente envía energía con variaciones que pueden desgastar o quemar otros componentes a largo plazo.", "Fuente de Alimentación (PSU)"),
    ("Fuente de Alimentación: Fusible interno quemado", "psu, fuente, fusible, descarga", "La fuente se sacrifica para proteger la computadora de una descarga eléctrica externa, quedando inservible.", "Fuente de Alimentación (PSU)"),

    # Coolers
    ("Sistemas de Refrigeración: Bomba de agua muerta", "cooler, refrigeracion, aio, bomba, liquida", "El motor que mueve el líquido refrigerante se descompone, causando que la CPU alcance los 100°C en cuestión de segundos.", "Sistemas de Refrigeración (Coolers)"),
    ("Sistemas de Refrigeración: Fuga de líquido", "cooler, aio, fuga, cortocircuito", "Ruptura en las mangueras o el bloque, con el peligro potencial de crear cortocircuitos en los demás componentes.", "Sistemas de Refrigeración (Coolers)"),
    ("Sistemas de Refrigeración: Pasta térmica seca", "cooler, pasta termica, seca, polvo", "El compuesto que une el procesador con el disipador se vuelve polvo o se endurece, perdiendo su capacidad de transferir calor.", "Sistemas de Refrigeración (Coolers)")
]

def seed():
    conn = sqlite3.connect('taller_prototipo.db')
    c = conn.cursor()
    c.execute("DELETE FROM knowledge_base")
    c.executemany("INSERT INTO knowledge_base (title, keywords, content, category) VALUES (?, ?, ?, ?)", glossary)
    conn.commit()
    conn.close()
    print("Seed exitoso.")

if __name__ == "__main__":
    seed()
